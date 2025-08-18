import sqlite3


def EnableForeignKeys(cur: sqlite3.Cursor) -> None:
    """Foreign keys機能を有効化"""
    cur.execute("PRAGMA foreign_keys = ON")


def HasTable(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """指定されたテーブルが存在するかどうかを確認"""
    # sqlite_masterテーブルをクエリして、指定された名前(大文字小文字を区別しない)のテーブルが存在するかを確認
    ret = cursor.execute(
        """
            SELECT COUNT(*) FROM sqlite_master
                WHERE type='table' AND LOWER(name)=?
        """,
        (table_name.lower(),),  # テーブル名を小文字に変換
    )
    # 結果の最初のカラム(COUNT(*)の結果)が0より大きい場合、テーブルは存在
    return ret.fetchone()[0] > 0


def DropTableIfExists(cursor: sqlite3.Cursor, table: str | list[str]) -> bool:
    """指定されたテーブルが存在する場合に削除"""
    # 引数が単一のテーブル名(文字列)の場合
    if isinstance(table, str):
        if HasTable(cursor, table):
            # テーブルが存在する場合、DROP TABLE文を実行して削除
            cursor.execute(f"DROP TABLE {table}")
            return True
        return False

    # 引数がテーブル名のリストの場合リスト内の各テーブル名に対して再帰的に処理
    res: bool = False
    for t in table:
        # いずれかのテーブルが削除された場合(Trueが返された場合)、結果はTrue
        res |= DropTableIfExists(cursor, t)
    return res


def Execute(cur: sqlite3.Cursor, query_string: str) -> None:
    """
    複数文の実行に対応
    クエリ文字列をセミコロンで分割し、各部分を個別に実行
    """
    for q in query_string.split(";"):
        # 空の文字列(最後のセミコロンの後など)はスキップ
        if q.strip():
            cur.execute(q)
