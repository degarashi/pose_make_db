"""
マッスTorsorDirの解析結果を格納しておくデータベース概要
"""

from .types import TableDef


def init_table_query() -> str:
    return """
        CREATE TABLE MasseTorsoDir (
            poseId      INTEGER NOT NULL UNIQUE REFERENCES Pose(id),
            x           REAL NOT NULL,
            y           REAL NOT NULL,
            z           REAL NOT NULL,
            method      TEXT NOT NULL,                                  -- for debug (どのメソッドを使って算出したか)
            score       REAL NOT NULL CHECK(score BETWEEN 0 AND 1),     -- どのくらい自信を持って言えるか
            embedded    BLOB NOT NULL CHECK(LENGTH(embedded) == 4*3),   -- (x,y,z)をバイト列にした物。後の計算用(不要かも)
            CHECK((x*x + y*y + z*z) BETWEEN 0.995 AND 1.005)            -- should be unit vector
        );
        CREATE VIRTUAL TABLE MasseTorsoVec USING vec0(
            poseId      INTEGER NOT NULL UNIQUE,
            torsoDir    float[3]
        );
    """


Table_Def: TableDef = {
    "MasseTorsoDir": {
        "poseId": int,
        "x": float,
        "y": float,
        "z": float,
        "method": str,
        "score": float,
        "embedded": bytes,
    },
    "MasseTorsoVec": None,
}
