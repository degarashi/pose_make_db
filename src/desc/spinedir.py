"""
マッスSpineDirの解析結果を格納しておくデータベース概要
"""

from common.types import TableDef


def init_table_query() -> str:
    return """
        CREATE TABLE MasseSpineDir (
            poseId      INTEGER PRIMARY KEY REFERENCES Pose(id),
            x           REAL NOT NULL,
            y           REAL NOT NULL,
            z           REAL NOT NULL,
            CHECK((x*x + y*y + z*z) BETWEEN 0.995 AND 1.005)            -- should be unit vector
        );
        CREATE VIRTUAL TABLE MasseSpineVec USING vec0(
            poseId      INTEGER NOT NULL UNIQUE,
            dir         float[3]
        );
    """


Table_Def: TableDef = {
    "MasseSpineDir": {
        "poseId": int,
        "x": float,
        "y": float,
        "z": float,
    },
    "MasseSpineVec": None,
}
