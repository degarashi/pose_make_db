"""
下腿屈曲の解析結果を格納しておくデータベース概要
"""

from common.types import TableDef
import math


# [dotProduct]
# 下腿は1方向にしか曲がらないので、DPが1.0が伸展,そこから下がるにつれ屈曲でOK
# 1.0 = 伸展
# 0 = 90度曲がった状態
# -1.0 = 屈曲
def init_table_query() -> str:
    return """
        CREATE TABLE CrusFlexion (
            poseId      INTEGER REFERENCES Pose(id),
            is_right    INTEGER NOT NULL CHECK(is_right IN (0,1)),  -- 0 = L, 1 = R
            angleRad    REAL CHECK(angleRad BETWEEN 0.0 AND {pi}),
            PRIMARY KEY(poseId, is_right)
        );
    """.format(pi=math.pi)


Table_Def: TableDef = {
    "CrusFlexion": {
        "poseId": int,
        "is_right": int,
        "angleRad": float,
    },
}
