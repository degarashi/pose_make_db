import argparse
from contextlib import suppress
from pathlib import Path

from common.argparse_aux import str_to_bool
from common.default_path import DEFAULT_DB_PATH
from common.log import add_logging_args


def add_optional_arguments_to_parser(parser: argparse.ArgumentParser) -> None:
    # データベースファイル
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--database_path",
            type=Path,
            default=DEFAULT_DB_PATH,
            help="SQLite3 database file",
        )
    # データベースを初期化するか
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--init_db", type=str_to_bool, default=False, help="Initialize DB"
        )
    add_logging_args(parser)
