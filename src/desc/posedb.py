"""
    BlazePoseの解析結果を格納しておくデータベース概要
"""

from common.types import TableDef

# 座標は右手座標系
# X 右方向+
# Y 上方向-
# Z 奥行き+

# 左手座標系へ変換して格納
# X 右方向+
# Y 上方向+
# Z 奥行き+
# テーブル初期化クエリ文
def init_table_query() -> str:
    return """
         CREATE TABLE File (
            id          INTEGER PRIMARY KEY,
            path        TEXT NOT NULL UNIQUE,
            size        INTEGER NOT NULL,
            timestamp   INTEGER NOT NULL,           -- UnixTime
            hash        BLOB NOT NULL UNIQUE,       -- SHA2(512)
            CHECK(size > 0),
            CHECK(timestamp >= 0),
            CHECK(LENGTH(hash) == 64)               -- SHA2(512)
        );

        -- PoseId = どのファイルの何人目か
        CREATE TABLE Pose (
            id              INTEGER PRIMARY KEY,
            fileId          INTEGER NOT NULL REFERENCES File(id),
            personIndex     INTEGER NOT NULL,
            CHECK(personIndex >= 0),
            UNIQUE(fileId, personIndex)
        );
        -- 全身のバウンディングボックス(0.0 -> 1.0)
        CREATE TABLE PoseRect (
            poseId          INTEGER PRIMARY KEY,
            x0              REAL NOT NULL,
            x1              REAL NOT NULL,
            y0              REAL NOT NULL,
            y1              REAL NOT NULL,
            CHECK (x0 <= x1),
            CHECK (y0 <= y1),
            CHECK (x0 >= 0.0 AND x1 <= 1.0),
            CHECK (y0 >= 0.0 AND y1 <= 1.0)
        );
        -- ランドマークIdと名 (For Debug)
        CREATE TABLE LandmarkName (
            id              INTEGER PRIMARY KEY,
            name            TEXT NOT NULL UNIQUE
        );
        -- Poseに対する各ランドマーク座標
        CREATE TABLE Landmark (
            poseId          INTEGER NOT NULL REFERENCES Pose(id),
            landmarkIndex   INTEGER NOT NULL REFERENCES LandmarkName(id),
            presence        REAL NOT NULL,
            visibility      REAL NOT NULL,

            -- 3D Landmark --
            x               REAL NOT NULL,
            y               REAL NOT NULL,
            z               REAL NOT NULL,
            -- 2D Landmark --
            td_x            REAL NOT NULL,
            td_y            REAL NOT NULL,

            CHECK (presence BETWEEN 0 AND 1),
            CHECK (visibility BETWEEN 0 AND 1),
            PRIMARY KEY(poseId, landmarkIndex)
        );
    """


Table_Def: TableDef = {
    "File": {
        "id": int,
        "path": str,
        "size": int,
        "timestamp": int,
        "hash": bytes
    },
    "Pose": {
        "id": int,
        "fileId": int,
        "personIndex": int
    },
    "Landmark": {
        "poseId": int,
        "landmarkIndex": int,
        "presence": float,
        "visibility": float,
        "x": float,
        "y": float,
        "z": float,
        "td_x": float,
        "td_y": float,
    },
    "LandmarkName": {
        "id": int,
        "name": str
    },
    "PoseRect": {
        "poseId": int,
        "x0": float,
        "x1": float,
        "y0": float,
        "y1": float
    }
}
