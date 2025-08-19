from common.db import Db
from common.reliability_desc import Table_Def, init_table_query
from common.types import TableDef


class ReliabilityDB(Db):
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

    def calculate_reliability(self):
        """
        PoseId毎に(Face, Half)のReliabilityを算出
        信頼性=(presence値の二乗)の平均
        """
        base_query = """
             SELECT Pose.id, AVG(lm.presence*lm.presence) FROM Pose
             JOIN Landmark AS lm ON lm.poseId = Pose.id
             WHERE {}
             GROUP BY Pose.id
             ORDER BY Pose.id ASC
        """

        cursor = self.cursor()
        # 顔の信頼性を計算 (landmarkIndex <= 10)
        cursor.execute(base_query.format("landmarkIndex <= 10"))
        face_reliability_data: list[tuple[int, float]] = cursor.fetchall()
        # 左半身の信頼性を計算 (landmarkIndex: 肩、肘、大腿、膝)
        cursor.execute(base_query.format("landmarkIndex IN (11, 13, 23, 25)"))
        left_half_reliability_data: list[tuple[int, float]] = cursor.fetchall()
        # 右半身の信頼性を計算 (landmarkIndex: 肩、肘、大腿、膝)
        cursor.execute(base_query.format("landmarkIndex IN (12, 14, 24, 26)"))
        right_half_reliability_data: list[tuple[int, float]] = cursor.fetchall()

        # 集約関数を使っているので、各リストの長さはポーズの数と一致するはず
        assert (
            len(face_reliability_data)
            == len(left_half_reliability_data)
            == len(right_half_reliability_data)
        )

        reliability_data_to_write: list[tuple[int, float, float]] = []
        # 各ポーズの信頼性を集計
        for face_data, left_data, right_data in zip(
            face_reliability_data,
            left_half_reliability_data,
            right_half_reliability_data,
        ):
            pose_id = face_data[0]
            # ソート済みの筈なのでポーズIdは一緒
            assert pose_id == left_data[0] == right_data[0]
            reliability_data_to_write.append(
                (
                    pose_id,  # poseId
                    min(
                        left_data[1], right_data[1]
                    ),  # torso_half_min (左右の信頼性の最小値)
                    face_data[1],  # face_detect (顔の信頼性)
                )
            )

        # 計算した信頼性値をデータベースに書き込む
        cursor.executemany(
            """
            INSERT INTO Reliability VALUES(?,?,?)
            """,
            reliability_data_to_write,
        )
