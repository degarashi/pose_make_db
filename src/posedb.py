import logging as L
from hashlib import sha512
from pathlib import Path

from common.db import Db, TableDef
from common.posedb_desc import Table_Def, init_table_query
from pose_estimate import Landmark


class PoseDB(Db):
    def __init__(
        self, dbpath: str, clear_table: bool, row_name: bool = False
    ):
        super().__init__(dbpath, clear_table, row_name)

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def post_table_initialized(self) -> None:
        # ランドマーク名のリストを作成し、データベースに挿入する
        cur = self.cursor()
        NAMES: list[str] = [
            "nose",
            "left_eye_inner", "left_eye", "left_eye_outer",
            "right_eye_inner", "right_eye", "right_eye_outer",
            "left_ear", "right_ear",
            "mouth_left", "mouth_right",
            "left_shoulder", "right_shoulder",
            "left_elbow", "right_elbow",
            "left_wrist", "right_wrist",
            "left_pinky", "right_pinky",
            "left_index", "right_index",
            "left_thumb", "right_thumb",
            "left_hip", "right_hip",
            "left_knee", "right_knee",
            "left_ankle", "right_ankle",
            "left_heel", "right_heel",
            "left_foot_index", "right_foot_index",
        ]
        assert len(NAMES) == 33  # ランドマーク名の数が33であることを確認

        names2: list[tuple[str, ...]] = []
        for n in NAMES:
            names2.append((n,))
        # ランドマーク名をデータベースに挿入
        cur.executemany("INSERT INTO LandmarkName(name) VALUES (?)", names2)

    def register_imagefile(self, path: Path) -> tuple[bool, int]:
        L.debug(f"register_imagefile: {path}")
        stat = path.stat()  # ファイルの更新時刻を取得
        cur = self.cursor()

        # 既に登録した画像は計算を省く
        cur.execute("SELECT size, timestamp, id FROM File WHERE path=?", (str(path),))
        ent = cur.fetchone()
        if ent is not None:
            # ファイルサイズと更新時刻が一致する場合、既に登録済みと判断
            if stat.st_size == ent[0] and stat.st_mtime == ent[1]:
                L.debug("already registered file(size and time)")
                return False, ent[2]  # 登録済みフラグとファイルIDを返す

        # ハッシュ値計算
        hash = sha512()
        with path.open("rb") as img:
            for chunk in iter(lambda: img.read(2048 * hash.block_size), b""):
                hash.update(chunk)
        checksum: bytes = hash.digest()  # ファイルのハッシュ値を計算

        # あるいは、ファイルが移動した場合を考える
        cur.execute("SELECT id FROM File WHERE hash=?", (checksum,))
        ent = cur.fetchone()
        if ent is not None:
            # ハッシュ値が一致する場合、ファイルが移動したと判断し、パスを更新
            cur.execute("UPDATE File SET path=? WHERE hash=?", (str(path), checksum))
            L.debug("already registered file(moved file)")
            return False, ent[0]  # 登録済みフラグとファイルIDを返す
        else:
            L.debug("generating FileId")

        # テーブルに格納
        cur.execute(
            "INSERT INTO File(path, size, timestamp, hash) VALUES (?,?,?,?)",
            (str(path), stat.st_size, stat.st_mtime, checksum),
        )
        file_id: int = cur.execute("SELECT last_insert_rowid()").fetchone()[
            0
        ]  # 新規ファイルIDを取得
        return True, file_id  # 新規登録フラグとファイルIDを返す

    def _remove_file(self, path: Path) -> None:
        # 指定されたパスのファイルをデータベースから削除する
        L.debug(f"removing file entry '{path}'")

        cur = self.cursor()
        # ---- File ----
        cur.execute("SELECT id FROM File WHERE path=?", (str(path),))
        ent = cur.fetchone()
        if ent is None:
            L.debug("not found")
            return
        file_id: int = ent[0]

        # ---- Pose ----
        cur.execute("SELECT id FROM Pose WHERE fileId=?", (file_id,))
        for ent in cur.fetchall():
            pose_id = ent[0]
            # ---- Landmark ----
            # 関連するランドマークを削除
            cur.execute("DELETE FROM Landmark WHERE poseId=?", (pose_id,))
        # 関連する姿勢推定結果を削除
        cur.execute("DELETE FROM Pose WHERE fileId=?", (file_id,))
        # ---- Pose End ----
        # ファイル情報を削除
        cur.execute("DELETE FROM File WHERE id=?", (file_id,))
        # ---- File End ----
        L.debug("done")

    def write_landmarks(self, image_id: int, marks: list[Landmark]) -> None:
        # PersonIdを作成
        cur = self.cursor()
        # Personはとりあえず0固定
        cur.execute(
            "INSERT INTO Pose(fileId, personIndex) VALUES (?,?)", (image_id, 0)
        )
        pose_id: int = cur.execute("SELECT last_insert_rowid()").fetchone()[
            0
        ]  # 新規姿勢推定IDを取得
        L.debug(f"poseId={pose_id}")

        # ランドマーク情報をテーブルに格納
        # (poseId, landmarkIndex, presence, visibility, x, y, z)
        lms: list[tuple[int, int, float, float, float, float, float]] = []
        mark_index: int = 0
        for m in marks:
            pos = m.pos
            # Y軸は反転
            lms.append(
                (
                    pose_id,
                    mark_index,
                    m.presence,
                    m.visibility,
                    pos[0], -pos[1], pos[2],
                )
            )
            mark_index += 1
        cur.executemany("INSERT INTO Landmark VALUES (?,?,?,?,?,?,?)", lms)

        L.debug("Success")
