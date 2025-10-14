import argparse
import logging
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from common.constants import CocoLandmark as CLm
from common.db_readwrite import add_optional_arguments_to_parser
from common.log import apply_logging_option
from common.serialize import vec_serialize
from common.types import TableDef
from common.vec_db import VecDb
from desc.spinedir import Table_Def, init_table_query


@dataclass
class DirRow:
    pose_id: int
    x: float
    y: float
    z: float


@dataclass
class VecRow:
    pose_id: int
    dir_bytes: bytes


class SpineDirDB(VecDb):
    def __init__(self, dbpath: str, clear_table: bool) -> None:
        super().__init__(dbpath, clear_table, row_name=True)
        self._logger = logging.getLogger(__name__)

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def calculate(self) -> None:
        with closing(self.cursor()) as cur:
            # PoseId列挙
            cur.execute("SELECT id FROM Pose")
            pose_ids: list[int] = [row[0] for row in cur.fetchall()]
            total = len(pose_ids)
            print(f"[INFO] {total} poses found. Start calculation...")

            dir_rows: list[DirRow] = []
            vec_rows: list[VecRow] = []

            for idx, pose_id in enumerate(pose_ids, start=1):
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
                        CLm.left_hip.value,
                        CLm.right_hip.value,
                        CLm.left_shoulder.value,
                        CLm.right_shoulder.value,
                    ),
                )
                rows: list[tuple[int, float, float, float]] = cur.fetchall()
                if len(rows) != 4:
                    # 警告ログを出力
                    found_indices = {r[0] for r in rows}
                    expected_indices = {
                        CLm.left_hip.value,
                        CLm.right_hip.value,
                        CLm.left_shoulder.value,
                        CLm.right_shoulder.value,
                    }
                    missing = sorted(expected_indices - found_indices)
                    self._logger.warning(
                        "Pose %d: insufficient landmark data (%d/4). Missing indices: %s. Skipped.",
                        pose_id,
                        len(rows),
                        missing,
                    )
                    continue

                lm: dict[int, tuple[float, float, float]] = {
                    idx: (x, y, z) for idx, x, y, z in rows
                }

                # 腰と肩の中心
                hip_center: tuple[float, float, float] = (
                    (lm[CLm.left_hip.value][0] + lm[CLm.right_hip.value][0]) / 2,
                    (lm[CLm.left_hip.value][1] + lm[CLm.right_hip.value][1]) / 2,
                    (lm[CLm.left_hip.value][2] + lm[CLm.right_hip.value][2]) / 2,
                )
                shoulder_center: tuple[float, float, float] = (
                    (lm[CLm.left_shoulder.value][0] + lm[CLm.right_shoulder.value][0]) / 2,
                    (lm[CLm.left_shoulder.value][1] + lm[CLm.right_shoulder.value][1]) / 2,
                    (lm[CLm.left_shoulder.value][2] + lm[CLm.right_shoulder.value][2]) / 2,
                )

                # ベクトル計算
                dx = shoulder_center[0] - hip_center[0]
                dy = shoulder_center[1] - hip_center[1]
                dz = shoulder_center[2] - hip_center[2]
                norm = (dx * dx + dy * dy + dz * dz) ** 0.5
                if norm == 0:
                    # 警告ログを出力
                    self._logger.warning(
                        "Pose %d: spine direction vector norm is zero. Skipped.",
                        pose_id,
                    )
                    continue
                dx /= norm
                dy /= norm
                dz /= norm

                # バッチ用に追加
                dir_rows.append(DirRow(pose_id, dx, dy, dz))
                vec_rows.append(VecRow(pose_id, vec_serialize([dx, dy, dz])))

                # 進捗表示
                if idx % 50 == 0 or idx == total:
                    percent = (idx / total) * 100
                    print(
                        f"[PROGRESS] {idx}/{total} ({percent:.1f}%) processed",
                        file=sys.stderr,
                    )

            # MasseSpineDirへ保存（UPSERT）
            cur.executemany(
                """
                INSERT INTO MasseSpineDir(poseId, x, y, z)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(poseId) DO UPDATE SET x=excluded.x, y=excluded.y, z=excluded.z
                """,
                [(r.pose_id, r.x, r.y, r.z) for r in dir_rows],
            )

            # MasseSpineVecへ保存（vec0 用）
            # 既存のposeIdがあれば削除
            cur.executemany(
                "DELETE FROM MasseSpineVec WHERE poseId = ?",
                [(r.pose_id,) for r in dir_rows],
            )
            # 新規INSERT
            cur.executemany(
                "INSERT INTO MasseSpineVec(poseId, dir) VALUES (?, ?)",
                [(r.pose_id, r.dir_bytes) for r in vec_rows],
            )

            print(f"[INFO] Calculation finished. {len(dir_rows)} entries updated.")


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
