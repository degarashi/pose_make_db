import argparse
import logging as L
from pathlib import Path
from typing import Callable, Any, List, Tuple

import make_pose_db as mp
import make_tags as tag
import reliability_db as rel
import torsodir_db as tor
import spine_dir as spine
from common.log import apply_logging_option


class ModuleTask:
    def __init__(
        self,
        name: str,
        module: Any,
        args_fn: Callable[[argparse.Namespace], Tuple[Any, ...]],
        check_result: bool = False,
    ) -> None:
        """
        :param name: ログ出力用の処理名
        :param module: add_optional_arguments_to_parser と process を持つモジュール
        :param args_fn: argparse.Namespace を受け取り、process に渡す引数タプルを返す関数
        :param check_result: True の場合、process の戻り値が False なら終了
        """
        self.name: str = name
        self.module: Any = module
        self.args_fn: Callable[[argparse.Namespace], Tuple[Any, ...]] = args_fn
        self.check_result: bool = check_result

    def add_args(self, parser: argparse.ArgumentParser) -> None:
        """モジュール固有の引数を parser に追加"""
        self.module.add_optional_arguments_to_parser(parser)

    def run(self, arg: argparse.Namespace) -> bool:
        """モジュールの実行と結果のチェック"""
        L.info(f"Processing {self.name}")
        try:
            result: Any = self.module.process(*self.args_fn(arg))
            if self.check_result and not result:
                L.error(f"{self.name} processing failed. Result was False.")
                return False
            return True
        except Exception as e:
            L.error(
                f"An error occurred during {self.name} processing: {e}", exc_info=True
            )
            return False


MODULES: List[ModuleTask] = [
    ModuleTask(
        "Pose Estimate",
        mp,
        lambda arg: (
            arg.target_dir,
            arg.model_path,
            arg.database_path,
            arg.init_db,
            arg.max_workers,
        ),
        check_result=True,
    ),
    ModuleTask("Reliability", rel, lambda arg: (arg.database_path, arg.init_db)),
    ModuleTask("TorsoDir", tor, lambda arg: (arg.database_path, arg.init_db)),
    ModuleTask(
        "Tag", tag, lambda arg: (arg.database_path, arg.init_db, arg.tags, arg.auto_tag)
    ),
    ModuleTask("SpineDir", spine, lambda arg: (arg.database_path, arg.init_db)),
]


def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate pose from images and write various data to the database"
    )
    parser.add_argument("target_dir", type=Path, help="Images directory")

    for m in MODULES:
        m.add_args(parser)

    return parser


if __name__ == "__main__":
    arg: argparse.Namespace = init_parser().parse_args()
    apply_logging_option(arg)

    for m in MODULES:
        if not m.run(arg):
            exit(1)
