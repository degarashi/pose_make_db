def init_table_query() -> str:
    return """
        CREATE TABLE Reliability (
            poseId              INTEGER NOT NULL UNIQUE REFERENCES Pose(id),
            torsoHalfMin        REAL NOT NULL CHECK(torsoHalfMin BETWEEN 0 AND 1),  -- 左右半身の信頼性で低い方
            faceDetect          REAL NOT NULL CHECK(faceDetect BETWEEN 0 AND 1)  -- 顔がどのくらい検出出来ているか
        );
    """

Table_Def: dict[str, dict[str, type] | None] = {
    "Reliability": {
        "poseId": int,
        "torsoHalfMin": float,
        "faceDetect": float
    }
}
