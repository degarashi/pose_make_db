"""
SQL Table正当性チェックの例外クラス
"""

import textwrap


# ベース例外クラス
class ValidityCheckFailed(Exception):
    """テーブルの正当性チェックに失敗した場合の基底例外クラス"""

    _table_name: str

    def __init__(self, table_name: str):
        self._table_name = table_name
        super().__init__(f"テーブル '{self._table_name}' の正当性チェックに失敗")


# カラムの数、名前が一致しない例外クラス
class VCFColumnMismatch(ValidityCheckFailed):
    """
    テーブルのカラム数またはカラム名が期待値と一致しない場合に発生する例外クラス
    """

    _expected_columns: dict[str, type]
    _actual_columns: list[str]

    def __init__(
        self,
        table_name: str,
        expected_columns: dict[str, type],
        actual_columns: list[str],
    ):
        """
        Args:
            table_name (str): テーブル名
            expected_columns (dict[str, type]): 期待されるカラム名と型
            actual_columns (list[str]): 実際に見つかったカラム名
        """
        self._expected_columns = expected_columns
        self._actual_columns = actual_columns
        super().__init__(table_name)

    def __str__(self):
        return textwrap.dedent(
            f"""
            カラムの不一致 (テーブル: '{self._table_name}')
                期待されるカラム:
                {self._expected_columns}
                実際に見つかったカラム:
                {self._actual_columns}
            """
        )


class VCFInvalidRow(ValidityCheckFailed):
    """
    テーブルの行データに不正な型が含まれている場合に発生する例外クラス
    """
    _expected_schema: dict[str, type]
    _actual_row_data_with_types: dict[str, tuple[any, type]]

    def __init__(
        self,
        table_name: str,
        expected_schema: dict[str, type],
        actual_row_data: dict[str, any],
    ):
        """
        Args:
            table_name (str): テーブル名
            expected_schema (dict[str, type]): 期待されるカラム名と型
            actual_row_data (dict[str, any]): 実際のエラーが発生した行のデータ
        """
        self._expected_schema = expected_schema
        # 実際のエラー発生行のデータを (値, 型) のタプルに変換して保持
        self._actual_row_data_with_types = {
            col_name: (value, type(value))
            for col_name, value in actual_row_data.items()
        }
        super().__init__(table_name)

    def __str__(self):
        return textwrap.dedent(
            f"""
            不正な行データ (テーブル: '{self._table_name}')
                期待されるスキーマ:
                {self._expected_schema}
                実際のエラー発生行データ (値, 型):
                {self._actual_row_data_with_types}
            """
        )


class VCFTableNotFound(ValidityCheckFailed):
    """
    指定されたテーブルが存在しない場合に発生する例外クラス
    """

    def __init__(self, table_name: str):
        """
        Args:
            table_name (str): 存在しないテーブル名
        """
        self._table_name = table_name
        super().__init__(table_name)

    def __str__(self):
        return f"テーブル '{self._table_name}' が見つかりませんでした"
