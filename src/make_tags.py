import argparse
import logging as L
from contextlib import suppress
from pathlib import Path

from common import log
from common.argparse_aux import str_to_bool
from common.db import Db
from common.default_path import DEFAULT_DB_PATH
from common.log import add_logging_args, apply_logging_option
from common.tags_desc import Table_Def, init_table_query
from common.types import TableDef


class TagsDB(Db):
    def __init__(self, dbpath: str, clear_db: bool = False) -> None:
        """
        Args:
            dbpath (str): データベースファイルのパス
        """
        super().__init__(dbpath, clear_db, False)

    @property
    def init_query(self) -> str:
        # テーブル定義に基づいて初期化クエリを返す
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        # テーブル定義を返す
        return Table_Def

    def _register_tag(self, name: str) -> int:
        cursor = self.cursor()
        cursor.execute("SELECT id FROM TagInfo WHERE name=?", (name,))
        id = cursor.fetchone()
        if id is None:
            cursor.execute("INSERT INTO TagInfo(name) VALUES (?)", (name,))
            return cursor.lastrowid
        assert type(id[0]) is int
        return id[0]

    def add_tags(self, tags: list[tuple[str, str]]) -> None:
        cursor = self.cursor()
        for tag in tags:
            dir_name, tag_name = tag
            tag_id = self._register_tag(tag_name)

            # タグに合致する画像を一括取得
            cursor.execute(
                """
                SELECT Pose.id
                FROM Pose
                INNER JOIN File
                    ON Pose.fileId = File.id
                WHERE File.path LIKE ? OR File.path LIKE ?
                """,
                (f"%/{dir_name}/%", f"{dir_name}/%"),
            )
            res_a = cursor.fetchall()
            if len(res_a) == 0:
                # 該当なし
                continue

            exec_l: list[tuple[int, int]] = []
            for res in res_a:
                pose_id: int = res[0]
                exec_l.append((pose_id, tag_id))

            cursor.executemany("INSERT INTO Tags VALUES (?,?)", exec_l)


class ExtendAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, []) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


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
    # ディレクトリキーワードとタグ名の対応付け
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--tags",
            nargs="+",
            action=ExtendAction,
            default=[],
            help="Map directory keywords to tag names (key=tagname)",
        )
    add_logging_args(parser)


def process(database_path: Path, init_db: bool, tags: list[str]) -> None:
    # [key=value, ...]の形になっているのでtupleに分離
    tags_t: list[tuple[str, str]] = divide_to_tuple(tags)

    with TagsDB(database_path, init_db) as db:
        db.add_tags(tags_t)


# [key=value, ...]の形になっているのでtupleに分離
def divide_to_tuple(tags: list[str]) -> list[tuple[str, str]]:
    parsed_tags: list[tuple[str, str]] = []
    for tag_str in tags:
        if "=" in tag_str:
            # (valueがスペースを含んでいる場合でも動く筈)
            key, value = tag_str.split("=", 1)
            parsed_tags.append((key, value))
        else:
            L.warning(
                f"Skipping malformed tag: {tag_str}. Expected format 'key=value'."
            )
    return parsed_tags


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="Calculate reliability of each joint"
        )
        add_optional_arguments_to_parser(parser)
        return parser

    args = init_parser().parse_args()
    apply_logging_option(args)

    # パースされた引数に基づいてロギング設定を適用
    log.apply_logging_option(args)

    process(args.database_path, args.init_db, args.tags)
