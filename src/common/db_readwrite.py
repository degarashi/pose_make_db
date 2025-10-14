import argparse
import math
from contextlib import suppress
from pathlib import Path

from common.argparse_aux import str_to_bool
from common.default_path import DEFAULT_DB_PATH
from common.log import add_logging_args


def add_optional_arguments_to_parser(parser: argparse.ArgumentParser) -> None:
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
    add_logging_args(parser)


def calc_landmark_dir(
    cur, input_index: tuple[tuple[int, int], tuple[int, int]], result_table: str
) -> None:
    # PoseId列挙
    cur.execute("SELECT id FROM Pose")
    pose_ids = [row[0] for row in cur.fetchall()]

    for pose_id in pose_ids:
        for is_right, (APos_idx, BPos_idx) in enumerate(input_index):
            # APos, BPos の座標を取得
            cur.execute(
                """
                SELECT x, y, z FROM Landmark
                WHERE poseId = ? AND landmarkIndex = ?
            """,
                (pose_id, APos_idx),
            )
            APos_row = cur.fetchone()

            cur.execute(
                """
                SELECT x, y, z FROM Landmark
                WHERE poseId = ? AND landmarkIndex = ?
            """,
                (pose_id, BPos_idx),
            )
            BPos_row = cur.fetchone()

            if not APos_row or not BPos_row:
                continue  # データ不足

            # ベクトル計算 (BPos - APos)
            vx = BPos_row[0] - APos_row[0]
            vy = BPos_row[1] - APos_row[1]
            vz = BPos_row[2] - APos_row[2]

            # 正規化
            length = math.sqrt(vx * vx + vy * vy + vz * vz)
            if length == 0:
                continue
            vx /= length
            vy /= length
            vz /= length

            # ResultTable に保存（UPSERT）
            cur.execute(
                f"""
                INSERT INTO {result_table} (poseId, is_right, x, y, z)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(poseId, is_right) DO UPDATE
                SET x=excluded.x, y=excluded.y, z=excluded.z
                """,
                (pose_id, is_right, vx, vy, vz),
            )
