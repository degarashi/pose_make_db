import argparse
from contextlib import closing
from pathlib import Path

from common.constants import CocoLandmark as CLm
from common.db_readwrite import add_optional_arguments_to_parser, calc_landmark_dir
from common.log import apply_logging_option
from common.types import TableDef
from common.vec_db import Db
from desc.thigh_dir import Table_Def, init_table_query


class ThighDirDB(Db):
    def __init__(self, dbpath: str, clear_table: bool):
        super().__init__(dbpath, clear_table, row_name=True)

    @property
    def init_query(self) -> str:
        return init_table_query()

    @property
    def table_def(self) -> TableDef:
        return Table_Def

    def calculate(self):
        with closing(self.cursor()) as cur:
            calc_landmark_dir(
                cur,
                (
                    (CLm.left_hip.value, CLm.left_knee.value),
                    (CLm.right_hip.value, CLm.right_knee.value),
                ),
                "MasseThighDir",
            )


def process(database_path: Path, init_db: bool) -> None:
    with ThighDirDB(str(database_path), init_db) as db:
        db.calculate()


if __name__ == "__main__":

    def init_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Calculate thigh direction")
        add_optional_arguments_to_parser(parser)
        return parser

    argv = init_parser().parse_args()
    apply_logging_option(argv)
    process(argv.database_path, argv.init_db)
