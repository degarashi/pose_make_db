import argparse
import math
from contextlib import closing
from pathlib import Path

from common.constants import BlazePoseLandmark as BPL
from common.log import apply_logging_option
from common.types import TableDef
from common.vec_db import VecDb
from desc.crus_dir import Table_Def, init_table_query
from common.db_readwrite import add_optional_arguments_to_parser


class CrusDirDB(VecDb):
    def __init__(self, dbpath: str, clear_table: bool):
        super().__init__(dbpath, clear_table, row_name=True)

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def calculate(self):
        with closing(self.cursor()) as cur:
            # PoseId列挙
            cur.execute("SELECT id FROM Pose")
            pose_ids = [row[0] for row in cur.fetchall()]

            for pose_id in pose_ids:
                for is_right, (knee_idx, ankle_idx) in enumerate(
                    [(BPL.left_knee.value, BPL.left_ankle.value), (BPL.right_knee.value, BPL.right_ankle.value)]
                ):
                    # knee, ankle の座標を取得
                    cur.execute(
                        """
                        SELECT x, y, z FROM Landmark
                        WHERE poseId = ? AND landmarkIndex = ?
                    """,
                        (pose_id, knee_idx),
                    )
                    knee_row = cur.fetchone()

                    cur.execute(
                        """
                        SELECT x, y, z FROM Landmark
                        WHERE poseId = ? AND landmarkIndex = ?
                    """,
                        (pose_id, ankle_idx),
                    )
                    ankle_row = cur.fetchone()

                    if not knee_row or not ankle_row:
                        continue  # データ不足

                    # ベクトル計算 (knee→ankle)
                    vx = ankle_row[0] - knee_row[0]
                    vy = ankle_row[1] - knee_row[1]
                    vz = ankle_row[2] - knee_row[2]

                    # 正規化
                    length = math.sqrt(vx * vx + vy * vy + vz * vz)
                    if length == 0:
                        continue
                    vx /= length
                    vy /= length
                    vz /= length

                    # MasseCrusDir に保存（UPSERT）
                    cur.execute(
                        """
                        INSERT INTO MasseCrusDir (poseId, is_right, x, y, z)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(poseId, is_right) DO UPDATE
                        SET x=excluded.x, y=excluded.y, z=excluded.z
                    """,
                        (pose_id, is_right, vx, vy, vz),
                    )


def process(database_path: Path, init_db: bool) -> None:
    with CrusDirDB(str(database_path), init_db) as db:
        db.calculate()


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Calculate crus direction")
        add_optional_arguments_to_parser(parser)
        return parser

    argv = init_parser().parse_args()
    apply_logging_option(argv)
    process(argv.database_path, argv.init_db)
