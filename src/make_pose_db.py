import argparse
import logging as L
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import closing, suppress
from dataclasses import dataclass
from hashlib import sha512
from pathlib import Path

from tqdm import tqdm

from common import default_path, log
from common.argparse_aux import str_to_bool
from common.constants import BLAZEPOSE_TO_COCO, CocoLandmark
from common.db import Db
from common.rect import Rect2D
from common.types import TableDef
from common.wsl import is_wsl_environment, posix_to_windows
from desc.posedb import Table_Def, init_table_query
from pose_estimate_blazepose import Estimate, EstimateFailed, Landmark

# MediaPipe Pose Landmarkerのモデルファイルパス
DEFAULT_MODEL_PATH = default_path.TEST_DATA_PATH / "pose_landmarker_heavy.task"


@dataclass
class ImageTask:
    path: Path
    image_id: int


@dataclass
class LandmarkData:
    pose_id: int
    landmark_index: int
    confidence: float
    x: float
    y: float
    z: float
    x_2d: float
    y_2d: float


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
        # ランドマーク名のリストを作成し、データベースに挿入する（COCO準拠）
        with closing(self.cursor()) as cur:
            index = 0
            for n in CocoLandmark:
                cur.execute(
                    "INSERT INTO LandmarkName(id, name) VALUES (?,?)",
                    (
                        index,
                        n.name,
                    ),
                )
                index += 1

    def register_imagefile(self, path: Path) -> tuple[bool, int]:
        L.debug(f"register_imagefile: {path}")
        stat = path.stat()  # ファイルの更新時刻を取得
        # たまにintでない事があるので明示的に変換
        st_mtime = int(stat.st_mtime)
        with closing(self.cursor()) as cur:
            # 既に登録した画像は計算を省く
            cur.execute(
                "SELECT size, timestamp, id FROM File WHERE path=?", (path.as_posix(),)
            )
            ent = cur.fetchone()
            if ent is not None:
                # ファイルサイズと更新時刻が一致する場合、既に登録済みと判断
                if stat.st_size == ent[0] and st_mtime == ent[1]:
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

            path_to_write = (
                path.as_posix()
                if not is_wsl_environment()
                else posix_to_windows(str(path))
            )
            if ent is not None:
                # ハッシュ値が一致する場合、ファイルが移動したと判断し、パスを更新
                cur.execute(
                    "UPDATE File SET path=? WHERE hash=?", (path_to_write, checksum)
                )
                L.debug("already registered file(moved file)")
                return False, ent[0]  # 登録済みフラグとファイルIDを返す
            else:
                L.debug("generating FileId")

            # テーブルに格納
            cur.execute(
                "INSERT INTO File(path, size, timestamp, hash) VALUES (?,?,?,?)",
                (
                    path_to_write,
                    stat.st_size,
                    st_mtime,
                    checksum,
                ),
            )
            # 新規登録フラグとファイルIDを返す
            return True, cur.lastrowid

    def _remove_file(self, path: Path) -> None:
        # 指定されたパスのファイルをデータベースから削除する
        L.debug(f"removing file entry '{path}'")

        with closing(self.cursor()) as cur:
            # ---- File ----
            cur.execute("SELECT id FROM File WHERE path=?", (path.as_posix(),))
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

    def write_landmarks(
        self, file_id: int, person_id: int, marks: list[Landmark]
    ) -> None:
        """
        marksはBlazePoseの33点を想定。COCOの17点へ射影して保存する。
        """
        with closing(self.cursor()) as cur:
            # PoseIdを作成
            cur.execute(
                "INSERT INTO Pose(fileId, personIndex) VALUES (?,?)",
                (file_id, person_id),
            )
            # 新規姿勢推定IDを取得
            pose_id: int = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
            L.debug(f"poseId={pose_id}")

            # COCOランドマークを抽出してテーブルに格納
            lms: list[LandmarkData] = []
            for blaze_idx, coco_idx in BLAZEPOSE_TO_COCO.items():
                m = marks[blaze_idx.value]
                lms.append(
                    LandmarkData(
                        pose_id=pose_id,
                        landmark_index=coco_idx.value,
                        confidence=m.visibility,
                        x=m.pos[0],
                        y=-m.pos[1],  # Y軸は反転
                        z=m.pos[2],
                        x_2d=m.pos_2d[0],  # 2d_x
                        y_2d=m.pos_2d[1],  # 2d_y
                    )
                )
            cur.executemany(
                "INSERT INTO Landmark VALUES (?,?,?,?,?,?,?,?)",
                [
                    (
                        lm.pose_id,
                        lm.landmark_index,
                        lm.confidence,
                        lm.x,
                        lm.y,
                        lm.z,
                        lm.x_2d,
                        lm.y_2d,
                    )
                    for lm in lms
                ],
            )

            # bboxはCOCOの2Dランドマークから算出
            xs = [lm.x_2d for lm in lms]
            ys = [lm.y_2d for lm in lms]
            min_x = min(xs)
            max_x = max(xs)
            min_y = min(ys)
            max_y = max(ys)

            bbox = Rect2D(
                min_x,
                min_y,
                max_x,
                max_y,
            )
            # 矩形にマージンを加えるが、頭部は余裕を持たせる
            RECT_MARGIN = 0.1
            ADDITIONAL_MARGIN = 0.1
            # COCOのnoseはインデックス0
            nose_index = CocoLandmark.nose.value
            nose_y = lms[nose_index].y_2d
            should_margin = nose_y <= min_y + 0.05
            bbox = bbox.add_margin_sides(
                RECT_MARGIN,
                RECT_MARGIN,
                RECT_MARGIN,
                RECT_MARGIN + (ADDITIONAL_MARGIN if should_margin else 0.0),
            ).clip_0_1()

            L.debug(f"bbox={bbox}")
            cur.execute(
                "INSERT INTO PoseRect VALUES(?,?,?,?,?)",
                (pose_id, bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max),
            )

            L.debug("Success")


# 姿勢推定
def _estimate_proc(path: str, model_path: str) -> list[list[Landmark]]:
    L.debug("Estimating pose...")
    with Estimate(model_path, 3) as e:
        return e.estimate(path)


def process(
    target_dir: Path,
    model_path: Path,
    database_path: Path,
    init_db: bool,
    max_workers: int,
) -> bool:
    # モデルファイルの存在チェック
    if not model_path.exists():
        L.error(f"モデルファイルが見つかりません: {model_path}")
        return False

    # init_db が True の場合、既存のデータが削除されるのでここで確認を出し、noと答えたらすぐ終了
    if init_db:
        confirm = input(
            "データベースを初期化します。既存のデータは削除されます。続行しますか？ (y/N): "
        )
        if confirm.lower() != "y":
            L.info("処理を中断しました。")
            return False

    # データベースファイルの存在チェック（init_dbがFalseの場合のみ）
    if not init_db and not database_path.exists():
        L.error(f"データベースファイルが見つかりません: {database_path}")
        return False

    # worker数が0以下の場合のエラーハンドリング
    if max_workers <= 0:
        L.error("ワーカー数は正の整数である必要があります")
        return False

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
            futures: dict[any, ImageTask] = {}
            for path in image_paths:
                path = path.absolute()
                # 画像ファイルが既に登録されてるか確認
                (b_id_created, image_id) = db.register_imagefile(path)
                L.debug(f"fileId={image_id}")
                # 新規登録された場合のみ推定を実行
                if b_id_created:
                    futures[
                        executor.submit(
                            _estimate_proc, path.as_posix(), str(model_path)
                        )
                    ] = ImageTask(path=path, image_id=image_id)

            # tqdmで進捗を表示しつつFutureを処理
            for future in tqdm(
                as_completed(futures), total=len(futures), desc="Processing images"
            ):
                param = futures[future]

                # _estimate_procの実行結果を取得
                try:
                    marks: list[list[Landmark]] = future.result()
                    # 複数人物に対応するためループ処理
                    for index, person_marks in enumerate(marks):
                        db.write_landmarks(param.image_id, index, person_marks)
                except EstimateFailed:
                    L.warning(f"Pose estimation failed for {param.path}. Skipping.")
                except Exception as exc:
                    # その他の予期せぬ例外
                    L.error(f"{param.path} generated an exception: {exc}")

        db.commit()
    return True


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
            description="Extract joints position by using BlazePose (stored as COCO)"
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
