import argparse
import logging as L
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import suppress
from hashlib import sha512
from pathlib import Path

from tqdm import tqdm

from common import default_path, log
from common.argparse_aux import str_to_bool
from common.constants import BLAZEPOSE_LANDMARK_LEN
from common.db import Db
from common.posedb_desc import Table_Def, init_table_query
from common.types import TableDef
from pose_estimate import Estimate, EstimateFailed, Landmark

# MediaPipe Pose Landmarkerのモデルファイルパス
DEFAULT_MODEL_PATH = default_path.TEST_DATA_PATH / "pose_landmarker_heavy.task"


class PoseDB(Db):
    def __init__(self, dbpath: str, clear_table: bool, row_name: bool = False):
        super().__init__(dbpath, clear_table, row_name)

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def post_table_initialized(self) -> None:
        # ランドマーク名のリストを作成し、データベースに挿入する
        cur = self.cursor()
        NAMES: list[str] = [
            "nose",
            "left_eye_inner",
            "left_eye",
            "left_eye_outer",
            "right_eye_inner",
            "right_eye",
            "right_eye_outer",
            "left_ear",
            "right_ear",
            "mouth_left",
            "mouth_right",
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist",
            "left_pinky",
            "right_pinky",
            "left_index",
            "right_index",
            "left_thumb",
            "right_thumb",
            "left_hip",
            "right_hip",
            "left_knee",
            "right_knee",
            "left_ankle",
            "right_ankle",
            "left_heel",
            "right_heel",
            "left_foot_index",
            "right_foot_index",
        ]
        assert (
            len(NAMES) == BLAZEPOSE_LANDMARK_LEN
        )  # ランドマーク名の数が一致することを確認

        names2: list[tuple[str, ...]] = []
        for n in NAMES:
            names2.append((n,))
        # ランドマーク名をデータベースに挿入
        cur.executemany("INSERT INTO LandmarkName(name) VALUES (?)", names2)

    def register_imagefile(self, path: Path) -> tuple[bool, int]:
        L.debug(f"register_imagefile: {path}")
        stat = path.stat()  # ファイルの更新時刻を取得
        cur = self.cursor()

        # 既に登録した画像は計算を省く
        cur.execute("SELECT size, timestamp, id FROM File WHERE path=?", (str(path),))
        ent = cur.fetchone()
        if ent is not None:
            # ファイルサイズと更新時刻が一致する場合、既に登録済みと判断
            if stat.st_size == ent[0] and stat.st_mtime == ent[1]:
                L.debug("already registered file(size and time)")
                return False, ent[2]  # 登録済みフラグとファイルIDを返す

        # ハッシュ値計算
        hash = sha512()
        with path.open("rb") as img:
            for chunk in iter(lambda: img.read(2048 * hash.block_size), b""):
                hash.update(chunk)
        checksum: bytes = hash.digest()  # ファイルのハッシュ値を計算

        # あるいは、ファイルが移動した場合を考える
        cur.execute("SELECT id FROM File WHERE hash=?", (checksum,))
        ent = cur.fetchone()
        if ent is not None:
            # ハッシュ値が一致する場合、ファイルが移動したと判断し、パスを更新
            cur.execute("UPDATE File SET path=? WHERE hash=?", (str(path), checksum))
            L.debug("already registered file(moved file)")
            return False, ent[0]  # 登録済みフラグとファイルIDを返す
        else:
            L.debug("generating FileId")

        # テーブルに格納
        cur.execute(
            "INSERT INTO File(path, size, timestamp, hash) VALUES (?,?,?,?)",
            (str(path), stat.st_size, stat.st_mtime, checksum),
        )
        file_id: int = cur.execute("SELECT last_insert_rowid()").fetchone()[
            0
        ]  # 新規ファイルIDを取得
        return True, file_id  # 新規登録フラグとファイルIDを返す

    def _remove_file(self, path: Path) -> None:
        # 指定されたパスのファイルをデータベースから削除する
        L.debug(f"removing file entry '{path}'")

        cur = self.cursor()
        # ---- File ----
        cur.execute("SELECT id FROM File WHERE path=?", (str(path),))
        ent = cur.fetchone()
        if ent is None:
            L.debug("not found")
            return
        file_id: int = ent[0]

        # ---- Pose ----
        cur.execute("SELECT id FROM Pose WHERE fileId=?", (file_id,))
        for ent in cur.fetchall():
            pose_id = ent[0]
            # ---- Landmark ----
            # 関連するランドマークを削除
            cur.execute("DELETE FROM Landmark WHERE poseId=?", (pose_id,))
        # 関連する姿勢推定結果を削除
        cur.execute("DELETE FROM Pose WHERE fileId=?", (file_id,))
        # ---- Pose End ----
        # ファイル情報を削除
        cur.execute("DELETE FROM File WHERE id=?", (file_id,))
        # ---- File End ----
        L.debug("done")

    def write_landmarks(self, image_id: int, marks: list[Landmark]) -> None:
        # PersonIdを作成
        cur = self.cursor()
        # Personはとりあえず0固定
        cur.execute("INSERT INTO Pose(fileId, personIndex) VALUES (?,?)", (image_id, 0))
        pose_id: int = cur.execute("SELECT last_insert_rowid()").fetchone()[
            0
        ]  # 新規姿勢推定IDを取得
        L.debug(f"poseId={pose_id}")

        # ランドマーク情報をテーブルに格納
        # (poseId, landmarkIndex, presence, visibility, x, y, z)
        lms: list[tuple[int, int, float, float, float, float, float]] = []
        mark_index: int = 0
        for m in marks:
            pos = m.pos
            # Y軸は反転
            lms.append(
                (
                    pose_id,
                    mark_index,
                    m.presence,
                    m.visibility,
                    pos[0],
                    -pos[1],
                    pos[2],
                )
            )
            mark_index += 1
        cur.executemany("INSERT INTO Landmark VALUES (?,?,?,?,?,?,?)", lms)

        L.debug("Success")


# 姿勢推定
def _estimate_proc(path: str, model_path: str) -> list[Landmark]:
    L.debug("Estimating pose...")
    with Estimate(model_path) as e:
        return e.estimate(path)


def process(
    target_dir: Path,
    model_path: Path,
    database_path: Path,
    init_db: bool,
    max_workers: int,
) -> None:
    # モデルファイルの存在チェック
    if not model_path.exists():
        L.error(f"モデルファイルが見つかりません: {model_path}")
        exit(1)

    # データベースファイルの存在チェック（init_dbがFalseの場合のみ）
    if not init_db and not database_path.exists():
        L.error(f"データベースファイルが見つかりません: {database_path}")
        exit(1)

    # worker数が0以下の場合のエラーハンドリング
    if max_workers <= 0:
        L.error("ワーカー数は正の整数である必要があります")
        exit(1)

    # PoseDB オブジェクトを初期化し、データベースファイルを開く
    # init_db が True の場合、初期化される
    with PoseDB(database_path, init_db) as db:
        # 処理対象のディレクトリ
        t_dir: Path = target_dir

        # 指定されたディレクトリ (target_dir) 内のすべてのファイルを再帰的に検索し、
        # ファイル名が .jpg または .jpeg で終わるもの（大文字小文字を区別しない）をリストアップ
        image_paths = [
            p
            for p in t_dir.glob("**/*")
            if re.search(R"\.(jpg|jpeg)$", str(p), re.IGNORECASE)
        ]

        # 見つかった画像ファイルのパスをデータベースにロード、保存
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 各ファイルに対して_estimate_proc関数を呼び出すFutureオブジェクトを作成
            # estimateオブジェクトは各プロセスで生成
            futures: dict[any, tuple[Path, int]] = {}
            for path in image_paths:
                # 画像ファイルが既に登録されてるか確認
                (b_id_created, image_id) = db.register_imagefile(path)
                L.debug(f"fileId={image_id}")
                # 新たにファイルが登録されてないなら姿勢推定の必要なし (ランドマーク座標は既に登録されている)
                if b_id_created:
                    futures[
                        executor.submit(_estimate_proc, str(path), str(model_path))
                    ] = (
                        path,
                        image_id,
                    )

            # tqdmで進捗を表示するために、完了したFutureを順番に処理
            for future in tqdm(
                as_completed(futures), total=len(image_paths), desc="Processing images"
            ):
                param = futures[future]

                # _load_imageの実行結果を取得（例外が発生した場合もここで捕捉される）
                try:
                    marks: list[Landmark] = future.result()
                    db.write_landmarks(param[1], marks)
                except EstimateFailed:
                    L.warning(f"Pose estimation failed for {param[0]}. Skipping.")
                except Exception as exc:
                    # その他の予期せぬ例外
                    L.error(f"{param[0]} generated an exception: {exc}")

        db.commit()


def add_optional_arguments_to_parser(parser: argparse.ArgumentParser) -> None:
    # SQLite3データベースファイル
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--database_path",
            type=Path,
            default=default_path.DEFAULT_DB_PATH,
            help="SQLite3 database file",
        )

    # データベースを初期化するか
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--init_db", type=str_to_bool, default=False, help="Initialize DB"
        )

    # モデルデータパス
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--model_path",
            type=Path,
            default=DEFAULT_MODEL_PATH,
            help="Model data path",
        )
    # workerの数を指定するオプション
    # デフォルト値をCPUコア数に設定
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--max_workers",
            type=int,
            default=os.cpu_count(),  # os.cpu_count() を使用してCPUコア数を取得
            help="Number of worker processes",
        )
    # ロギング関連の引数を追加
    # --verbose や --quiet などのオプションが利用可能
    log.add_logging_args(parser)


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="Extract joints position by using BlazePose"
        )
        # 処理対象の画像ディレクトリ
        parser.add_argument("target_dir", type=Path, help="Images directory")
        add_optional_arguments_to_parser(parser)
        return parser

    args = init_parser().parse_args()
    # パースされた引数に基づいてロギング設定を適用
    log.apply_logging_option(args)

    process(
        args.target_dir,
        args.model_path,
        args.database_path,
        args.init_db,
        args.max_workers,
    )
