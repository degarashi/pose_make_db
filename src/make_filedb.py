import argparse
import re
from pathlib import Path

from common import log
from common.argparse_aux import str_to_bool
from posedb import PoseDB

TEST_DATA_PATH = Path("test_data")
DEFAULT_DB_PATH = TEST_DATA_PATH / "pose_db.sqlite3"
# MediaPipe Pose Landmarkerのモデルファイルパス
DEFAULT_MODEL_PATH = TEST_DATA_PATH / "pose_landmarker_heavy.task"

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
        # ロギング関連の引数を追加
        # --verbose や --quiet などのオプションが利用可能
        log.add_logging_args(parser)

        return parser.parse_args()

    args = init_parser()

    # パースされた引数に基づいてロギング設定を適用
    log.apply_logging_option(args)

    # PoseDB オブジェクトを初期化し、データベースファイルを開く
    # args.init_db が True の場合、初期化される
    with PoseDB(args.database_path, args.init_db, args.model_path) as db:
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
        db.load_images(image_paths)
        db.commit()
