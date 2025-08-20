import argparse
import logging
from contextlib import suppress
from typing import Dict

# ログレベル名から数値へのマッピング
NUM_TO_LOGLEVEL: Dict[str, int] = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def add_logging_args(parser: argparse.ArgumentParser) -> None:
    """
    argparse.ArgumentParser にログレベル設定のための引数を追加

    Args:
        parser (argparse.ArgumentParser): 引数を追加するパーサーオブジェクト
    """
    with suppress(argparse.ArgumentError):
        parser.add_argument(
            "--log_level",
            type=str,
            default="WARNING",
            help="log level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        )


def apply_logging_option(args: argparse.Namespace) -> None:
    """
    コマンドライン引数で指定されたログレベルを適用する関数

    Args:
        args (argparse.Namespace): コマンドライン引数を格納したオブジェクト
                                   'log_level' 属性を持つことを想定
    """
    # 指定されたログレベル文字列を小文字に変換し、対応する数値ログレベルを取得
    # 取得したログレベルで基本的なロギング設定を行う
    log_level_str: str = args.log_level.lower()

    # ログレベル文字列が NUM_TO_LOGLEVEL に存在するかチェック
    if log_level_str not in NUM_TO_LOGLEVEL:
        # 存在しない場合は、デフォルトのWARNINGレベルを使用
        print(
            f"Error: Invalid log level '{args.log_level}'. Accepted values are: {', '.join(NUM_TO_LOGLEVEL.keys())}"
        )
        level_to_apply = logging.WARNING
    else:
        level_to_apply: int = NUM_TO_LOGLEVEL[log_level_str]

    logging.basicConfig(
        format="%(levelname)s:%(message)s",  # ログメッセージのフォーマットを指定
        level=level_to_apply,  # 指定されたログレベルを適用
    )
