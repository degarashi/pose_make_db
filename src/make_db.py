import argparse
import logging as L
from pathlib import Path
from typing import Callable, Any, List, Tuple

import make_pose_db as mp
import make_tags as tag
import reliability_db as rel
import torsodir_db as tor
import spine_dir as spine
import thigh_dir as thigh
import thigh_flexion as th_flex
from common.log import apply_logging_option


class ModuleTask:
    """個別モジュールの実行タスクを表すクラス"""

    def __init__(
        self,
        name: str,
        module: Any,
        args_fn: Callable[[argparse.Namespace], Tuple[Any, ...]],
        check_result: bool = False,
    ) -> None:
        self.name = name
        self.module = module
        self.args_fn = args_fn
        self.check_result = check_result

    def add_args(self, parser: argparse.ArgumentParser) -> None:
        """モジュール固有の引数を parser に追加"""
        if hasattr(self.module, "add_optional_arguments_to_parser"):
            self.module.add_optional_arguments_to_parser(parser)

    def run(self, args: argparse.Namespace) -> bool:
        """モジュールの実行と結果のチェック"""
        L.info(f"Processing {self.name}")
        try:
            result = self.module.process(*self.args_fn(args))
            if self.check_result and not result:
                L.error(f"{self.name} processing failed. Result was False.")
                return False
            return True
        except Exception:
            L.exception(f"An error occurred during {self.name} processing")
            return False


def build_modules() -> List[ModuleTask]:
    """実行対象モジュールのリストを構築"""
    return [
        ModuleTask(
            "Pose Estimate",
            mp,
            lambda a: (
                a.target_dir,
                a.model_path,
                a.database_path,
                a.init_db,
                a.max_workers,
            ),
            check_result=True,
        ),
        ModuleTask("Reliability", rel, lambda a: (a.database_path, a.init_db)),
        ModuleTask("TorsoDir", tor, lambda a: (a.database_path, a.init_db)),
        ModuleTask(
            "Tag", tag, lambda a: (a.database_path, a.init_db, a.tags, a.auto_tag)
        ),
        ModuleTask("SpineDir", spine, lambda a: (a.database_path, a.init_db)),
        ModuleTask("ThighDir", thigh, lambda a: (a.database_path, a.init_db)),
        ModuleTask("ThighFlex", th_flex, lambda a: (a.database_path, a.init_db)),
    ]


def init_parser(modules: List[ModuleTask]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate pose from images and write various data to the database"
    )
    parser.add_argument("target_dir", type=Path, help="Images directory")

    for module in modules:
        module.add_args(parser)

    return parser


def main() -> None:
    modules = build_modules()
    parser = init_parser(modules)
    args = parser.parse_args()

    apply_logging_option(args)

    for module in modules:
        if not module.run(args):
            exit(1)


if __name__ == "__main__":
    main()
