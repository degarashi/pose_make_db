import argparse
from pathlib import Path

from common.argparse_aux import str_to_bool
from common.default_path import DEFAULT_DB_PATH
from common.log import add_logging_args, apply_logging_option
from reliabilitydb import ReliabilityDB

if __name__ == "__main__":

    def init_parser():
        parser = argparse.ArgumentParser(
            description="Extract joints position by using BlazePose"
        )
        # データベースファイル
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
        add_logging_args(parser)
        return parser.parse_args()

    argv = init_parser()
    apply_logging_option(argv)
    with ReliabilityDB(argv.database_path, argv.init_db) as db:
        db.calculate_reliability()
