import argparse
import logging as L
from contextlib import suppress
from pathlib import Path

from common import log
from common.argparse_aux import str_to_bool
from common.convert import divide_to_tuple
from common.db import Db
from common.default_path import DEFAULT_DB_PATH
from common.log import add_logging_args, apply_logging_option
from desc.tags import Table_Def, init_table_query
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

    def add_tags_auto(self, tag_root: str) -> None:
        # tag_rootをPathに変換し、それが有効なディレクトリか判定
        tag_root_path = Path(tag_root).absolute()
        if not tag_root_path.is_dir():
            L.error(f"Invalid directory path: {tag_root}")
            return

        cursor = self.cursor()
        cursor.execute(
            """
            SELECT Pose.id, File.path
            FROM Pose
            INNER JOIN File
                ON Pose.fileId = File.id
            """
        )
        exec_l: list[tuple[int, int]] = []
        while True:
            ent = cursor.fetchone()
            if ent is None:
                break
            pose_id: int = ent[0]
            file_path = Path(ent[1])
            try:
                # tag_root_pathを基準に相対パスを構築
                file_path = file_path.relative_to(tag_root_path)
                for i in range(len(file_path.parts) - 1):
                    tag_name = file_path.parts[i]
                    tag_id = self._register_tag(tag_name)
                    exec_l.append((pose_id, tag_id))
            except ValueError:
                # 無効なファイルパス
                pass
        if len(exec_l) > 0:
            cursor2 = self.cursor()
            cursor2.executemany(
                "INSERT INTO Tags (poseId, tagId) VALUES (?, ?)",
                exec_l,
            )

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
    # 自動タグ付けルートディレクトリ
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--auto_tag",
            type=str,
            default=None,
            help="automatic tagging root directory path",
        )
    add_logging_args(parser)


def process(
    database_path: Path, init_db: bool, tags: list[str], auto_tag: str | None
) -> None:
    """
    タグ処理を実行

    Args:
        database_path (Path): データベースファイルのパス
        init_db (bool): データベースを初期化するかどうか
        tags (list[str]): ディレクトリ名とタグ名のペアのリスト(["key=value", ...])
        auto_tag (str|None): 自動タグ付けルートディレクトリパス
    """
    # ["key=value", ...]の形になっているのでtupleに分離
    tags_t: list[tuple[str, str]] = divide_to_tuple(tags)

    with TagsDB(database_path, init_db) as db:
        db.add_tags(tags_t)
        if auto_tag is not None:
            db.add_tags_auto(auto_tag)


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

    process(args.database_path, args.init_db, args.tags, args.auto_tag)
