import argparse
from contextlib import suppress
from pathlib import Path

from common import log
from common.argparse_aux import str_to_bool
from common.convert import divide_to_tuple
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
        """テーブル定義に基づく初期化クエリ"""
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        """テーブル定義"""
        return Table_Def

    def _register_tag(self, name: str) -> int:
        """タグ名を登録し、そのIDを返す"""
        cursor = self.cursor()
        cursor.execute("SELECT id FROM TagInfo WHERE name=?", (name,))
        id_row = cursor.fetchone()
        if id_row is None:
            cursor.execute("INSERT INTO TagInfo(name) VALUES (?)", (name,))
            return cursor.lastrowid
        assert isinstance(id_row[0], int)
        return id_row[0]

    def add_tags(self, tags: list[tuple[str, str]]) -> None:
        """
        ディレクトリ名とタグ名のペアを元にタグを追加

        Args:
            tags (list[tuple[str, str]]): ディレクトリ名とタグ名のペアのリスト
        """
        cursor = self.cursor()
        for tag in tags:
            dir_name, tag_name = tag
            tag_id = self._register_tag(tag_name)

            # タグに合致するファイルパスを持つ画像を一括取得
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
    """ArgParseで使用する、引数リストを拡張するアクション"""

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, []) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


def add_optional_arguments_to_parser(parser: argparse.ArgumentParser) -> None:
    """オプション引数をパーサーに追加"""
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
    """
    タグ処理を実行

    Args:
        database_path (Path): データベースファイルのパス
        init_db (bool): データベースを初期化するかどうか
        tags (list[str]): ディレクトリ名とタグ名のペアのリスト(["key=value", ...])
    """
    # ["key=value", ...]の形になっているのでtupleに分離
    tags_t: list[tuple[str, str]] = divide_to_tuple(tags)

    with TagsDB(database_path, init_db) as db:
        db.add_tags(tags_t)


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
