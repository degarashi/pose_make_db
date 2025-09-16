"""
大腿の方向
"""

from common.types import TableDef


def init_table_query() -> str:
    return """
        CREATE TABLE MasseThighDir (
            poseId      INTEGER REFERENCES Pose(id),
            is_right    INTEGER NOT NULL CHECK(is_right IN (0,1)),  -- 0 = L, 1 = R
            x           REAL NOT NULL,
            y           REAL NOT NULL,
            z           REAL NOT NULL,
            PRIMARY KEY(poseId, is_right)
        );
        CREATE VIRTUAL TABLE MasseThighVec USING vec0(
            poseId      INTEGER NOT NULL UNIQUE,
            is_right    INTEGER NOT NULL CHECK(is_right IN (0,1)),  -- 0 = L, 1 = R
            dir         float[3]
        );
    """


Table_Def: TableDef = {
    "MasseThighDir": {
        "poseId": int,
        "is_right": int,
        "x": float,
        "y": float,
        "z": float,
    },
    "MasseThighVec": None,
}
