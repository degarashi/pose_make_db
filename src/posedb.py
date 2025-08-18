import logging as L
from hashlib import sha512
from pathlib import Path

from tqdm import tqdm

from common.db import Db, TableDef
from common.posedb_desc import Table_Def, init_table_query
from pose_estimate import Estimate, EstimateFailed, Landmark


class PoseDB(Db):
    _model_path: str

    def __init__(self, dbpath: str, clear_table: bool, model_path: str, row_name: bool = False):
        super().__init__(dbpath, clear_table, row_name)
        self._model_path = model_path

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def post_table_initialized(self):
        # ランドマーク名のリストを作成
        cur = self.cursor()
        NAMES: list[str] = [
            "nose",
            "left_eye_inner",
            "left_eye",
            "left_eye_outer",
            "right_eye_inner",
            "right_eye",
            "right_eye_outer",
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
            "left_foot_index", "right_foot_index"
        ]
        assert len(NAMES) == 33

        names2: list[tuple[str,...]] = []
        for n in NAMES:
            names2.append((n,))
        cur.executemany("INSERT INTO LandmarkName(name) VALUES (?)", names2)

    def register_imagefile(self, path: Path) -> tuple[bool, int]:
        L.debug(f"register_imagefile: {path}")
        stat = path.stat()
        cur = self.cursor()

        # 既に登録した画像は計算を省く
        cur.execute(
            "SELECT size, timestamp, id FROM File WHERE path=?",
            (str(path),)
        )
        ent = cur.fetchone()
        if ent is not None:
            if stat.st_size == ent[0] and \
                    stat.st_mtime == ent[1]:
                # 前に登録したファイルであると判断 -> idを返す
                L.debug("already registered file(size and time)")
                return False, ent[2]

        # ハッシュ値計算
        hash = sha512()
        with path.open("rb") as img:
            for chunk in iter(lambda: img.read(2048 * hash.block_size), b""):
                hash.update(chunk)
        checksum: bytes = hash.digest()

        # あるいは、ファイルが移動した場合を考える
        cur.execute("SELECT id FROM File WHERE hash=?", (checksum,))
        ent = cur.fetchone()
        if ent is not None:
            # パスの更新だけする
            cur.execute("UPDATE File SET path=? WHERE hash=?", (str(path), checksum))
            L.debug("already registered file(moved file)")
            return False, ent[0]
        else:
            L.debug("generating FileId")

        # テーブルに格納
        cur.execute(
            "INSERT INTO File(path, size, timestamp, hash) VALUES (?,?,?,?)",
            (str(path), stat.st_size, stat.st_mtime, checksum)
        )
        file_id: int = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
        return True, file_id

    def _remove_file(self, path: Path):
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
            cur.execute("DELETE FROM Landmark WHERE poseId=?", (pose_id,))
        cur.execute("DELETE FROM Pose WHERE fileId=?", (file_id,))
        # ---- Pose End ----
        cur.execute("DELETE FROM File WHERE id=?", (file_id,))
        # ---- File End ----
        L.debug("done")

    def _load_image(self, estimate: Estimate, path: Path):
        (b_id_created, image_id) = self.register_imagefile(path)
        L.debug(f"fileId={image_id}")

        # 新たにファイルが登録されてないなら姿勢推定の必要なし (ランドマーク座標は既に登録されている)
        if not b_id_created:
            return

        L.debug("Estimating pose...")
        try:
            # 姿勢推定
            marks: list[Landmark] = estimate.estimate(str(path))

            # PersonIdを作成
            cur = self.cursor()
            # Personはとりあえず0固定
            cur.execute("INSERT INTO Pose(fileId, personIndex) VALUES (?,?)",
                        (image_id, 0))
            pose_id: int = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
            L.debug(f"poseId={pose_id}")

            # テーブルに格納
            lms = []
            index = 0
            for m in marks:
                pos = m.pos
                # Y軸は反転
                lms.append((pose_id, index, m.presence, m.visibility, pos[0], -pos[1], pos[2]))
                index += 1
            cur.executemany("INSERT INTO Landmark VALUES (?,?,?,?,?,?,?)", lms)

            L.debug("Success")
        except EstimateFailed:
            L.debug("Failed")
            raise

    def load_images(self, path_list: list[Path]):
        with Estimate(self._model_path) as estimate:
            # tqdmを使用して進捗バーを表示
            for path in tqdm(path_list, desc="Processing images"):
                try:
                    self._load_image(estimate, path)
                except EstimateFailed:
                    # 次回更新時に無駄な探査をしないようFileエントリだけのこしておく
                    pass
