import argparse
from typing import Union, Set

# 許容される真偽値を表す文字列を定数として定義
TRUE_STRINGS: Set[str] = {"yes", "true", "t", "y", "1"}
FALSE_STRINGS: Set[str] = {"no", "false", "f", "n", "0"}
ALL_ACCEPTED_STRINGS: Set[str] = TRUE_STRINGS | FALSE_STRINGS


def str_to_bool(v: Union[str, bool]) -> bool:
    """
    コマンドライン引数として渡された文字列を真偽値に変換する。

    Args:
        v (str or bool): 変換対象の文字列または真偽値。

    Returns:
        bool: 変換された真偽値。

    Raises:
        argparse.ArgumentTypeError: 有効な真偽値の文字列でない場合に発生する。
    """
    if isinstance(v, bool):
        return v

    # 入力値を小文字に変換して比較する
    v_lower: str = v.lower()

    if v_lower in TRUE_STRINGS:
        return True
    elif v_lower in FALSE_STRINGS:
        return False
    else:
        # 有効な文字列のリストをエラーメッセージに含める
        error_message: str = (
            f"Boolean value expected, but got '{v}'. "
            f"Accepted values are: {', '.join(sorted(ALL_ACCEPTED_STRINGS))}"
        )
        raise argparse.ArgumentTypeError(error_message)
