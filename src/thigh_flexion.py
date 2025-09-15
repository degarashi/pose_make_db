import argparse
from contextlib import closing
from pathlib import Path

from common.db import Db
from common.log import apply_logging_option
from common.types import TableDef
from desc.thigh_flexion import Table_Def, init_table_query

# オプションは同じなので使いまわし
from reliability_db import add_optional_arguments_to_parser


class ThighFlexionDB(Db):
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
        MasseTorsoDir（胴体方向）と MasseThighDir（大腿方向）の内積から
        股関節の屈曲角度を計算し、MasseSpineDirとの内積で符号を決定して
        ThighFlexion に格納する
        """
        query_str = """
            WITH DotCalc AS (
                SELECT
                    p.id AS poseId,
                    mth.is_right,
                    -- 胴体と大腿の内積
                    (mtd.x * mth.x + mtd.y * mth.y + mtd.z * mth.z) AS dot_torso_thigh,
                    -- 大腿と脊柱の内積（符号判定用）
                    (mth.x * msd.x + mth.y * msd.y + mth.z * msd.z) AS dot_thigh_spine
                FROM Pose AS p
                INNER JOIN MasseTorsoDir AS mtd ON mtd.poseId = p.id
                INNER JOIN MasseThighDir AS mth ON mth.poseId = p.id
                INNER JOIN MasseSpineDir AS msd ON msd.poseId = p.id
            )
            INSERT INTO ThighFlexion (poseId, is_right, dotBody, angleRad, dotSpine)
            SELECT
                poseId,
                is_right,
                dot_torso_thigh,
                CASE
                    WHEN dot_torso_thigh IS NULL THEN NULL
                    WHEN dot_torso_thigh >  1.0 THEN CASE WHEN dot_thigh_spine < 0 THEN ACOS( 1.0) ELSE -ACOS( 1.0) END
                    WHEN dot_torso_thigh < -1.0 THEN CASE WHEN dot_thigh_spine < 0 THEN ACOS(-1.0) ELSE -ACOS(-1.0) END
                    ELSE CASE WHEN dot_thigh_spine < 0 THEN ACOS(dot_torso_thigh) ELSE -ACOS(dot_torso_thigh) END
                END AS angleRad,
                dot_thigh_spine
            FROM DotCalc;
        """

        with closing(self.cursor()) as cur:
            cur.execute(query_str)


def process(database_path: Path, init_db: bool) -> None:
    with ThighFlexionDB(database_path, init_db) as db:
        db.calculate_flexion()


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="Calculate thigh extension (-1.0 -> 1.0)"
        )
        add_optional_arguments_to_parser(parser)
        return parser

    argv = init_parser().parse_args()
    apply_logging_option(argv)
    process(argv.database_path, argv.init_db)
