from .types import TableDef


def init_table_query() -> str:
    return """
        CREATE TABLE TagInfo (
            id                  INTEGER PRIMARY KEY,
            name                TEXT NOT NULL UNIQUE
        );
        CREATE TABLE Tags (
            poseId              INTEGER NOT NULL REFERENCES Pose(id),
            tagId               INTEGER NOT NULL REFERENCES TagInfo(id),
            PRIMARY KEY (poseId, tagId)
        );
    """


Table_Def: TableDef = {
    "TagInfo": {
        "id": int,
        "name": str,
    },
    "Tags": {
        "poseId": int,
        "tagId": int,
    },
}
