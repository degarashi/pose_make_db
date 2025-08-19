import argparse
import logging as L
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from common import log
from common.argparse_aux import str_to_bool
from pose_estimate import Estimate, EstimateFailed, Landmark
from posedb import PoseDB

TEST_DATA_PATH = Path("test_data")
DEFAULT_DB_PATH = TEST_DATA_PATH / "pose_db.sqlite3"
# MediaPipe Pose Landmarkerのモデルファイルパス
DEFAULT_MODEL_PATH = TEST_DATA_PATH / "pose_landmarker_heavy.task"


# 姿勢推定
def _estimate_proc(path: str, model_path: str) -> list[Landmark]:
    L.debug("Estimating pose...")
    with Estimate(model_path) as e:
        return e.estimate(path)


if __name__ == "__main__":

    def init_parser():
        parser = argparse.ArgumentParser(
            description="Extract joints position by using BlazePose"
        )
        # SQLite3データベースファイル
        parser.add_argument(
            "--database_path",
            type=Path,
            default=DEFAULT_DB_PATH,
            help="SQLite3 database file",
        )
        # データベースを初期化するか
        parser.add_argument(
            "--init_db", type=str_to_bool, default=False, help="Initialize DB"
        )
        # 処理対象の画像ディレクトリ
        parser.add_argument("target_dir", type=Path, help="Images directory")

        # モデルデータパス
        parser.add_argument(
            "--model_path",
            type=Path,
            default=DEFAULT_MODEL_PATH,
            help="Model data path",
        )
        # workerの数を指定するオプション
        # デフォルト値をCPUコア数に設定
        parser.add_argument(
            "--workers",
            type=int,
            default=os.cpu_count(),  # os.cpu_count() を使用してCPUコア数を取得
            help="Number of worker processes",
        )
        # ロギング関連の引数を追加
        # --verbose や --quiet などのオプションが利用可能
        log.add_logging_args(parser)

        return parser.parse_args()

    args = init_parser()

    model_path: Path = args.model_path
    assert model_path.exists(), f"モデルファイルが見つかりません: {model_path}"

    database_path: Path = args.database_path
    assert (
        database_path.exists()
    ), f"データベースファイルが見つかりません: {database_path}"

    # パースされた引数に基づいてロギング設定を適用
    log.apply_logging_option(args)

    # PoseDB オブジェクトを初期化し、データベースファイルを開く
    # args.init_db が True の場合、初期化される
    with PoseDB(args.database_path, args.init_db) as db:
        # 処理対象のディレクトリ
        t_dir: Path = args.target_dir

        # 指定されたディレクトリ (target_dir) 内のすべてのファイルを再帰的に検索し、
        # ファイル名が .jpg または .jpeg で終わるもの（大文字小文字を区別しない）をリストアップ
        image_paths = [
            p
            for p in t_dir.glob("**/*")
            if re.search(R"\.(jpg|jpeg)$", str(p), re.IGNORECASE)
        ]

        # 見つかった画像ファイルのパスをデータベースにロード、保存
        max_workers: int = args.workers
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
