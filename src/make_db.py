# (make_pose_db.py, reliability_db.py, torsodir_db.py)
# これらを統合した物

import argparse
from pathlib import Path

import make_pose_db as mp
import reliability_db as rel
import torsodir_db as tor
from common.log import apply_logging_option

if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="Estimate pose from images and write various data to the database"
        )
        # 処理対象の画像ディレクトリ
        parser.add_argument("target_dir", type=Path, help="Images directory")

        mp.add_optional_arguments_to_parser(parser)
        rel.add_optional_arguments_to_parser(parser)
        tor.add_optional_arguments_to_parser(parser)
        return parser

    arg = init_parser().parse_args()
    apply_logging_option(arg)

    database_path: Path = arg.database_path
    init_db: bool = arg.init_db
    mp.process(arg.target_dir, arg.model_path, database_path, init_db, arg.max_workers)
    rel.process(database_path, False)
    tor.process(database_path, False)
