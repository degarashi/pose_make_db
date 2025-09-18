import argparse
from contextlib import closing
from pathlib import Path

from common.db import Db
from common.log import apply_logging_option
from common.types import TableDef
from desc.crus_flexion import Table_Def, init_table_query

# オプションは同じなので使いまわし
from reliability_db import add_optional_arguments_to_parser


class CrusFlexionDB(Db):
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

    def calculate_flexion(self):
        """
        MasseThighDir（大腿方向）と MasseCrusDir（下腿方向）の内積から
        膝関節の屈曲角度を計算して CrusFlexion に格納する
        """
        query_str = """
            INSERT INTO CrusFlexion (poseId, is_right, angleRad)
            SELECT
                t.poseId,
                t.is_right,
                acos(
                    t.x * c.x +
                    t.y * c.y +
                    t.z * c.z
                ) AS angleRad
            FROM MasseThighDir AS t
            JOIN MasseCrusDir  AS c
              ON t.poseId   = c.poseId
             AND t.is_right = c.is_right

            -- 既に CrusFlexion に同じキーがある場合は更新
            ON CONFLICT(poseId, is_right) DO UPDATE
            SET angleRad = excluded.angleRad;
        """

        with closing(self.cursor()) as cur:
            cur.execute(query_str)


def process(database_path: Path, init_db: bool) -> None:
    with CrusFlexionDB(database_path, init_db) as db:
        db.calculate_flexion()


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="Calculate crus extension (-1.0 -> 1.0)"
        )
        add_optional_arguments_to_parser(parser)
        return parser

    argv = init_parser().parse_args()
    apply_logging_option(argv)
    process(argv.database_path, argv.init_db)
