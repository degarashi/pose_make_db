import sqlite3
from pathlib import Path
from typing import Any, Optional

from common import sql
from common.table_check import check_validity
from common.table_check_exception import VCFTableNotFound

from .types import TableDef


class Db:
    @property
    def init_query(self) -> str:
        """
        データベースの初期化クエリを返す
        このメソッドはサブクラスで実装される必要がある
        """
        assert False, "This method must be implemented"

    @property
    def table_def(self) -> TableDef:
        """
        テーブル定義を辞書形式で返す
        キーはテーブル名、値はカラム定義(カラム名: 型)の辞書
        このメソッドはサブクラスで実装される必要がある
        """
        assert False, "This method must be implemented"

    _db_path: str
    _clear_table: bool
    _row_name: bool
    conn: Optional[sqlite3.Connection]

    def __init__(self, dbpath: str, clear_table: bool, row_name: bool = False):
        """
        Dbクラスのコンストラクタ

        Args:
            dbpath (str): データベースファイルのパス
            clear_table (bool): Trueの場合、既存のデータベースファイルがあっても新しく作り直す
            row_name (bool): Trueの場合、結果セットのカラムに名前でアクセス可能にする
                                       デフォルトはFalse
        """
        self._db_path = dbpath
        self._clear_table = clear_table
        self._row_name = row_name
        self.conn = None

    def post_conn_created(self) -> None:
        """
        データベース接続が作成された後に実行されるメソッド
        サブクラスで必要に応じてオーバーライドして、接続後の処理を記述する
        """
        pass

    def post_table_initialized(self) -> None:
        """
        テーブルの初期化(作成またはクリア後)が完了した後に実行されるメソッド
        サブクラスで必要に応じてオーバーライドして、初期化後の処理を記述する
        """
        pass

    def __enter__(self) -> "Db":
        """
        コンテキストマネージャのエントリポイント
        データベース接続を確立し、テーブルの初期化または検証を行う
        """
        file_exists: bool = Path(self._db_path).exists()
        self.conn = conn = sqlite3.connect(self._db_path)
        if self._row_name:
            # row_factoryを設定することで、結果セットのカラムに名前でアクセスできるようになる
            self.conn.row_factory = sqlite3.Row
        self.post_conn_created()

        cur = conn.cursor()
        tdef = self.table_def
        # データベースが初期化済みか、またはテーブルをクリアする場合
        should_initialized: bool = not file_exists or self._clear_table
        if should_initialized:
            # テーブルの初期化(既存テーブルがあれば削除し、再作成)
            sql.DropTableIfExists(cur, tdef.keys())
            sql.Execute(cur, self.init_query)
            self.post_table_initialized()
        else:
            # 既存データベースの場合はテーブルの正当性をチェックする(Pre-check)
            try:
                check_validity(conn, tdef)
            except VCFTableNotFound:
                # 一部のテーブルだけ先に作成されていた場合などを考慮し、
                # テーブル定義と一致しない場合は再初期化する
                sql.DropTableIfExists(cur, tdef.keys())
                sql.Execute(cur, self.init_query)
                self.post_table_initialized()

        # 外部キー制約を有効にする
        sql.EnableForeignKeys(cur)
        return self

    def __exit__(
        self,
        e_type: Optional[type],
        e_value: Optional[Exception],
        traceback: Optional[Any],
    ) -> bool:
        """
        コンテキストマネージャのエグジットポイント
        コミット、クローズ処理を行うエラーが発生した場合の処理も行う
        """
        if e_type is None:
            # エラーが発生しなかった場合、テーブルの正当性をチェックする(Post-check)
            try:
                check_validity(self.conn, self.table_def)
            except VCFTableNotFound:
                # テーブルが見つからない場合は無視する
                pass
        if self.conn is not None:
            # 変更をコミットして接続を閉じる
            self.conn.commit()
            self.conn.close()
        return False

    def cursor(self) -> sqlite3.Cursor:
        """
        データベースカーソルを取得する
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        return self.conn.cursor()

    def commit(self) -> None:
        """
        現在のトランザクションの変更をコミットする
        """
        if self.conn is not None:
            self.conn.commit()
        else:
            raise RuntimeError("Database connection is not established.")
