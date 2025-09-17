# 既に読み込まれたBlazePoseのランドマーク座標から胴体の向きを算出

import argparse
import logging as L
from pathlib import Path
from typing import Optional

import numpy as np

from common.constants import BLAZEPOSE_LANDMARK_LEN
from common.constants import BlazePoseLandmark as BPL
from common.db_readwrite import add_optional_arguments_to_parser
from common.log import apply_logging_option
from common.serialize import vec_deserialize, vec_serialize
from common.types import TableDef
from common.vec_db import VecDb
from desc.torsodir import Table_Def, init_table_query


class MasseTorsoDB(VecDb):
    def __init__(self, dbpath: str, clear_table: bool):
        super().__init__(dbpath, clear_table, row_name=True)

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def _test_fetch_vec(self, dir_v: list[float], limit: int) -> None:
        cur = self.cursor()
        cur.execute(
            """
            SELECT poseId, dir, distance FROM MasseTorsoVec
            WHERE dir MATCH ?
            ORDER BY distance
            LIMIT ?
                """,
            (vec_serialize(dir_v), limit),
        )
        for ent in cur.fetchall():
            deserialized_torsoDir = vec_deserialize(ent["dir"])
            print(f"Distance: {ent['distance']}, TorsoDir: {deserialized_torsoDir}")

    def _test_fetch_vec2(self, dir_v: list[float], limit: int) -> None:
        cur = self.cursor()
        cur.execute(
            """
            WITH knn_match AS (
                SELECT poseId, dir, distance
                FROM MasseTorsoVec
                WHERE dir MATCH ?
                ORDER BY distance
                LIMIT ?
            )
            SELECT pose.id, knn.distance, file.path, mt.x, mt.y, mt.z, mt.method, mt.score
            FROM MasseTorsoDir AS mt
            JOIN knn_match AS knn
                ON (mt.poseId = knn.poseId)
            JOIN Pose AS pose
                ON (pose.id = mt.poseId)
            JOIN File AS file
                ON (file.id = pose.fileId)
            WHERE mt.score >= 0.5
            ORDER BY distance ASC
            """,
            (vec_serialize(dir_v), limit),
        )
        for ent in cur.fetchall():
            print(
                ent["method"],
                [ent["x"], ent["y"], ent["z"]],
                ent["path"],
                ent["score"],
                ent["distance"],
            )

    def calc_torsodir(self) -> None:
        cur = self.cursor()
        curL = self.cursor()
        dir_data: list[tuple[int, float, float, float, str, float, bytes]] = []
        dir_vec_data: list[tuple[int, bytes, bytes]] = []
        cur.execute("SELECT id FROM Pose")
        while True:
            ent = cur.fetchone()
            if ent is None:
                break

            pose_id: int = ent[0]
            curL.execute(
                """
                    SELECT *
                    FROM Landmark
                    WHERE poseId=?
                    ORDER BY landmarkIndex
                """,
                (pose_id,),
            )
            landmark: list = curL.fetchall()
            assert len(landmark) == BLAZEPOSE_LANDMARK_LEN
            L.debug(f"pose_id={pose_id}")

            # -- log ---
            curL.execute(
                """
                SELECT File.path FROM File
                    INNER JOIN Pose ON File.id = Pose.fileId
                    WHERE Pose.id=?
             """,
                (pose_id,),
            )
            L.debug(curL.fetchone()["path"])
            # -- log end ---

            lmLS, lmRS, lmLH, lmRH = (
                landmark[BPL.left_shoulder.value],
                landmark[BPL.right_shoulder.value],
                landmark[BPL.left_hip.value],
                landmark[BPL.right_hip.value],
            )
            assert lmLS["landmarkIndex"] == BPL.left_shoulder.value
            assert lmRS["landmarkIndex"] == BPL.right_shoulder.value
            assert lmLH["landmarkIndex"] == BPL.left_hip.value
            assert lmRH["landmarkIndex"] == BPL.right_hip.value

            posLS, posRS, posLH, posRH = (
                np.array([lmLS["x"], lmLS["y"], lmLS["z"]]),
                np.array([lmRS["x"], lmRS["y"], lmRS["z"]]),
                np.array([lmLH["x"], lmLH["y"], lmLH["z"]]),
                np.array([lmRH["x"], lmRH["y"], lmRH["z"]]),
            )
            TH_PRESENCE = 0.9
            psLS, psRS, psLH, psRH = (
                lmLS["presence"] >= TH_PRESENCE,
                lmRS["presence"] >= TH_PRESENCE,
                lmLH["presence"] >= TH_PRESENCE,
                lmRH["presence"] >= TH_PRESENCE,
            )

            used_method: str = "invalid"

            # 計算に使えるランドマークをカウント
            # 胴体の向きを算出
            def four_points() -> Optional[np.ndarray]:
                nonlocal used_method
                if psLS and psRS and psLH and psRH:
                    used_method = "4pt"
                    dir_vA = np.cross(posLH - posLS, posRS - posLS)
                    dir_vA /= np.linalg.norm(dir_vA)
                    dir_vB = np.cross(posLS - posRS, posRH - posRS)
                    dir_vB /= np.linalg.norm(dir_vB)
                    dir_v = dir_vA + dir_vB
                    return dir_v / np.linalg.norm(dir_v)
                return None

            def three_points() -> Optional[np.ndarray]:
                nonlocal used_method
                dir_v = None
                # 両方の肩と片方のヒップ
                if psLS and psRS:
                    if psLH:
                        used_method = "3pt: A"
                        dir_v = np.cross(posLH - posLS, posRS - posLS)
                    elif psRH:
                        used_method = "3pt: B"
                        dir_v = np.cross(posLS - posRS, posRH - posRS)

                if dir_v is None:
                    # 両方のヒップと片方の肩
                    if psLH and psRH:
                        if psLS:
                            used_method = "3pt: C"
                            dir_v = np.cross(posLS - posLH, posRH - posLH)
                        elif psRS:
                            used_method = "3pt: D"
                            dir_v = np.cross(posRS - posRH, posLH - posRH)

                if dir_v is not None:
                    dir_v /= np.linalg.norm(dir_v)
                    return dir_v
                return None

            def two_points() -> Optional[np.ndarray]:
                nonlocal used_method
                base_z = None
                shoulder_to_hip = None
                # 対角線
                if psLS and psRH:
                    base_z = np.array([0, 0, 1] if posLS[0] < posRH[0] else [0, 0, -1])
                    shoulder_to_hip = posRH - posLS
                    used_method = "2pt: A"
                elif psLH and psRS:
                    base_z = np.array([0, 0, 1] if posLH[0] < posRS[0] else [0, 0, -1])
                    shoulder_to_hip = posLH - posRS
                    used_method = "2pt: B"

                if base_z is not None and shoulder_to_hip is not None:
                    dir_v = np.cross(shoulder_to_hip, base_z)
                    dir_v /= np.linalg.norm(dir_v)
                    return dir_v
                return None

            dir_v_np: Optional[np.ndarray] = four_points()
            if dir_v_np is None:
                dir_v_np = three_points()
                if dir_v_np is None:
                    dir_v_np = two_points()

            if dir_v_np is not None:
                assert len(dir_v_np) == 3, "dir_v_np must be a numpy array of length 3"
                # 姿勢検出の時の確かさの度合いを取得
                curL.execute(
                    "SELECT torsoHalfMin FROM Reliability WHERE poseId=?", (pose_id,)
                )
                half_min: float = curL.fetchone()[0]

                # yaw_vecは、dir_v_npのx, z成分を抜き出して正規化したものを代入
                xz = dir_v_np[[0, 2]]
                norm_xz = np.linalg.norm(xz)
                if norm_xz > 0:
                    yaw_vec = (xz / norm_xz).tolist()
                else:
                    yaw_vec = [0.0, 0.0]

                # pitch: XZ 平面に対する上下角
                # np.arctan2(y, 水平方向の長さ) で求める
                pitch_rad = float(np.arctan2(dir_v_np[1], norm_xz))
                # -π/2 ～ +π/2 を -1 ～ +1 に線形マッピング
                pitch_norm = float(pitch_rad / (np.pi / 2))
                # 念のため範囲外をクリップ
                pitch_norm = max(-1.0, min(1.0, pitch_norm))

                # 結果を格納
                dir_data.append(
                    (
                        pose_id,  # poseId
                        dir_v_np[0],
                        dir_v_np[1],
                        dir_v_np[2],  # x,y,z
                        used_method,  # method
                        half_min,  # score (とりあえずhalf_minをそのまま入力)
                        yaw_vec[0],  # yaw_x
                        yaw_vec[1],  # yaw_z
                        pitch_norm,  # pitch
                    )
                )
                dir_vec_data.append(
                    (
                        pose_id,
                        vec_serialize(dir_v_np.tolist()),
                        vec_serialize(yaw_vec),
                    )
                )

        assert len(dir_data) == len(dir_vec_data)

        # 既に存在するposeIdを削除
        curL.execute(
            """
            DELETE FROM MasseTorsoDir
            WHERE poseId IN (SELECT id FROM Pose)
            """
        )
        curL.execute(
            """
            DELETE FROM MasseTorsoVec
            WHERE poseId IN (SELECT id FROM Pose)
            """
        )
        # テーブルに書きこむ
        curL.executemany(
            "INSERT INTO MasseTorsoDir VALUES(?,?,?,?,?,?,?,?,?)", dir_data
        )

        # KNNサーチ用テーブルの書き込み
        curL.executemany(
            """
            INSERT INTO MasseTorsoVec(poseId, dir, yaw)
           VALUES(?,?,?)
        """,
            dir_vec_data,
        )


def process(database_path: Path, init_db: bool) -> None:
    with MasseTorsoDB(str(database_path), init_db) as db:
        db.calc_torsodir()
        db.commit()
        # normalized_vector = np.array([-1, -1, -1]) / np.linalg.norm([-1, -1, -1])
        # db._test_fetch_vec(normalized_vector.tolist(), 10)


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Calculate body-direction")
        add_optional_arguments_to_parser(parser)
        return parser

    argv = init_parser().parse_args()
    apply_logging_option(argv)
    process(argv.database_path, argv.init_db)
