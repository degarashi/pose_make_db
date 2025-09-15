"""
大腿屈曲の解析結果を格納しておくデータベース概要
"""

from common.types import TableDef
import math


# [dotProduct]
# 1.0 = 屈曲
# 0 = 正位
# -1.0 = 伸展
def init_table_query() -> str:
    return """
        CREATE TABLE ThighFlexion (
            poseId      INTEGER REFERENCES Pose(id),
            is_right    INTEGER NOT NULL CHECK(is_right IN (0,1)),  -- 0 = L, 1 = R
            dotBody  REAL CHECK(dotBody BETWEEN -1.0 AND 1.0),
            angleRad    REAL CHECK(angleRad BETWEEN -{pi} AND {pi}),
            dotSpine  REAL CHECK(dotSpine BETWEEN -1.0 AND 1.0),
            PRIMARY KEY(poseId, is_right)
        );
    """.format(pi=math.pi)


Table_Def: TableDef = {
    "ThighFlexion": {
        "poseId": int,
        "is_right": int,
        "dotBody": float,
        "angleRad": float,
        "dotSpine": float,
    },
}
