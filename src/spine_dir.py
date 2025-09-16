import argparse
from pathlib import Path

from common.constants import BlazePoseLandmark as BPL
from common.log import apply_logging_option
from common.serialize import vec_serialize
from common.types import TableDef
from common.vec_db import VecDb
from desc.spinedir import Table_Def, init_table_query
from torsodir_db import add_optional_arguments_to_parser


class SpineDirDB(VecDb):
    def __init__(self, dbpath: str, clear_table: bool):
        super().__init__(dbpath, clear_table, row_name=True)

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def calculate(self):
        cur = self.conn.cursor()

        # PoseId列挙
        cur.execute("SELECT id FROM Pose")
        pose_ids = [row[0] for row in cur.fetchall()]

        for pose_id in pose_ids:
            # 必要なランドマークを取り出す
            cur.execute(
                """
                SELECT landmarkIndex, x, y, z
                FROM Landmark
                WHERE poseId = ?
                  AND landmarkIndex IN (?, ?, ?, ?)
                """,
                (
                    pose_id,
                    BPL.left_hip.value,
                    BPL.right_hip.value,
                    BPL.left_shoulder.value,
                    BPL.right_shoulder.value,
                ),
            )
            rows = cur.fetchall()
            if len(rows) != 4:
                continue  # データ不足ならskip

            lm = {idx: (x, y, z) for idx, x, y, z in rows}

            # 腰と肩の中心
            hip_center = (
                (lm[BPL.left_hip.value][0] + lm[BPL.right_hip.value][0]) / 2,
                (lm[BPL.left_hip.value][1] + lm[BPL.right_hip.value][1]) / 2,
                (lm[BPL.left_hip.value][2] + lm[BPL.right_hip.value][2]) / 2,
            )
            shoulder_center = (
                (lm[BPL.left_shoulder.value][0] + lm[BPL.right_shoulder.value][0]) / 2,
                (lm[BPL.left_shoulder.value][1] + lm[BPL.right_shoulder.value][1]) / 2,
                (lm[BPL.left_shoulder.value][2] + lm[BPL.right_shoulder.value][2]) / 2,
            )

            # ベクトル計算
            dx = shoulder_center[0] - hip_center[0]
            dy = shoulder_center[1] - hip_center[1]
            dz = shoulder_center[2] - hip_center[2]
            norm = (dx * dx + dy * dy + dz * dz) ** 0.5
            if norm == 0:
                continue
            dx /= norm
            dy /= norm
            dz /= norm

            # MasseSpineDirへ保存（UPSERT）
            cur.execute(
                """
                INSERT INTO MasseSpineDir(poseId, x, y, z)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(poseId) DO UPDATE SET x=excluded.x, y=excluded.y, z=excluded.z
                """,
                (pose_id, dx, dy, dz),
            )

            # MasseSpineVecへ保存（vec0 用）
            # 既存のposeIdがあれば削除
            cur.execute("DELETE FROM MasseSpineVec WHERE poseId = ?", (pose_id,))
            # 新規INSERT
            cur.execute(
                "INSERT INTO MasseSpineVec(poseId, dir) VALUES (?, ?)",
                (pose_id, vec_serialize([dx, dy, dz])),
            )
        self.conn.commit()


def process(database_path: Path, init_db: bool) -> None:
    with SpineDirDB(str(database_path), init_db) as db:
        db.calculate()


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Calculate spine-direction")
        add_optional_arguments_to_parser(parser)
        return parser

    argv = init_parser().parse_args()
    apply_logging_option(argv)
    process(argv.database_path, argv.init_db)
