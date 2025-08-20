from common.db import Db
import sqlite_vec


class VecDb(Db):
    def post_conn_created(self):
        super().post_conn_created()
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
