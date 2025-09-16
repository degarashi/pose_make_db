"""
マッスTorsorDirの解析結果を格納しておくデータベース概要
"""

from common.types import TableDef


def init_table_query() -> str:
    return """
        CREATE TABLE MasseTorsoDir (
            poseId      INTEGER PRIMARY KEY REFERENCES Pose(id),
            x           REAL NOT NULL,
            y           REAL NOT NULL,
            z           REAL NOT NULL,
            method      TEXT NOT NULL,                                  -- for debug (どのメソッドを使って算出したか)
            score       REAL NOT NULL CHECK(score BETWEEN 0 AND 1),     -- どのくらい自信を持って言えるか
            embedded    BLOB NOT NULL CHECK(LENGTH(embedded) == 4*3),   -- (x,y,z)をバイト列にした物。後の計算用(不要かも)
            yaw_x       REAL NOT NULL,
            yaw_z       REAL NOT NULL,
            embedded_yaw BLOB NOT NULL CHECK(LENGTH(embedded_yaw) == 4*2),   -- (yaw_x,yaw_z)をバイト列にした物
            pitch       REAL NOT NULL CHECK(pitch BETWEEN -1.0 AND 1.0),
            CHECK((x*x + y*y + z*z) BETWEEN 0.995 AND 1.005)            -- should be unit vector
            CHECK((yaw_x*yaw_x + yaw_z*yaw_z) BETWEEN 0.995 AND 1.005)  -- should be unit vector
        );
        CREATE VIRTUAL TABLE MasseTorsoVec USING vec0(
            poseId      INTEGER NOT NULL UNIQUE,
            dir         float[3],
            yaw         float[2]
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
        "yaw_x": float,
        "yaw_z": float,
        "embedded_yaw": bytes,
        "pitch": float,
    },
    "MasseTorsoVec": None,
}
