"""
    SQL Tableの正当性チェック
"""
import sqlite3

from common import sql
from common.table_check_exception import (
    VCFColumnMismatch,
    VCFInvalidRow,
    VCFTableNotFound,
)


# テーブルが存在するか、カラムの型が合っているかのチェック
def check_validity(
        conn: sqlite3.Connection,
        table_def: dict[str, dict[str, type] | None]
):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    for table_name, column_types in table_def.items():
        # テーブルの存在確認
        if not sql.HasTable(cur, table_name):
            raise VCFTableNotFound(table_name)

        if column_types is None:
            continue
        cur.execute(f"SELECT * FROM {table_name}")
        # カラム名(数)のチェック
        actual_cname = [tup[0] for tup in cur.description]
        err = False
        if (len(actual_cname) != len(column_types)):
            err = True
        else:
            for acn in actual_cname:
                if acn not in column_types:
                    err = True
                    break
        if err:
            raise VCFColumnMismatch(
                table_name,
                column_types,
                actual_cname
            )

        # 値の型チェック
        res = cur.fetchall()
        for row in res:
            err = False
            for i, val in enumerate(row):
                if column_types[actual_cname[i]] is not type(val):
                    err = True
                    break
            if err:
                raise VCFInvalidRow(
                    table_name,
                    column_types,
                    {actual_cname[i]: val for i, val in enumerate(row)}
                )
