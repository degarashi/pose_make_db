import subprocess
import os
import sys
import shutil
import logging
import functools
from enum import Enum
from typing import Optional, Union
from pathlib import PurePosixPath, PureWindowsPath


logger = logging.getLogger(__name__)


class WslVariant(Enum):
    WSL1 = "wsl1"
    WSL2 = "wsl2"


class PathConversionError(Exception):
    """WSL関連のパス変換に失敗した場合の例外"""


def _get_kernel_release() -> str:
    """
    @brief カーネルリリース文字列を取得する

    os.uname().release を優先し、失敗時は /proc/sys/kernel/osrelease を参照。
    いずれも取得できない場合は空文字列を返す。

    例:
        - WSL1: "4.4.0-19041-Microsoft"
        - WSL2: "5.15.167.4-microsoft-standard-WSL2"
        - Ubuntu (22.04 LTS など): "5.15.0-91-generic"

    備考:
        - WSL1 は実カーネルが存在しないため、Windows ビルド番号に対応した
          固定的な文字列が返る
        - WSL2 は Microsoft が配布する Linux カーネルのバージョンが返る
        - Ubuntu はディストリ標準のカーネルで、末尾に "-generic" が付く
    """
    try:
        return os.uname().release
    except Exception:
        try:
            with open("/proc/sys/kernel/osrelease", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""


@functools.lru_cache(maxsize=1)
def get_wsl_variant() -> Optional[WslVariant]:
    """
    @brief WSLのバリアントを識別する

    判定基準:
    - リリース文字列に "microsoft-standard" を含む場合は WSL2
    - リリース文字列に "microsoft" を含む場合は WSL1
    - 上記以外は None
    """
    release = _get_kernel_release().lower()
    if "microsoft-standard" in release:
        return WslVariant.WSL2
    if "microsoft" in release:
        return WslVariant.WSL1
    return None


@functools.lru_cache(maxsize=1)
def is_wsl_environment() -> bool:
    """
    @brief WSL環境であるかを判定する

    判定基準:
    - Linux系プラットフォームであること
    - WSLのバリアントが検出できること、もしくは WSL_DISTRO_NAME/WSL_INTEROP が存在すること
    - /mnt/c が存在する場合は肯定判定を補強
    """
    platform_flag = sys.platform.startswith("linux")
    if not platform_flag:
        return False

    env_flag = any(key in os.environ for key in ("WSL_DISTRO_NAME", "WSL_INTEROP"))
    variant = get_wsl_variant()
    mnt_c_exists = os.path.isdir("/mnt/c")

    if variant is not None:
        return True
    if env_flag and mnt_c_exists:
        return True
    return False


def _run_wslpath(path_str: str) -> str:
    """
    @brief wslpath を用いて POSIX → Windows 変換を実施

    実行に失敗した場合は PathConversionError を送出
    """
    wslpath_cmd = shutil.which("wslpath")
    if not wslpath_cmd:
        raise PathConversionError("wslpath が見つからないため変換不可")

    try:
        result = subprocess.run(
            [wslpath_cmd, "-w", path_str],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # 一部の失敗ケースでは標準出力に結果が入る可能性に配慮
        if e.stdout and e.stdout.strip():
            return e.stdout.strip()
        detail = e.stderr.strip() if e.stderr else str(e)
        raise PathConversionError(f"wslpath 実行失敗: {detail}") from e
    except FileNotFoundError as e:
        raise PathConversionError(f"wslpath 実行不可: {e}") from e


def _manual_mnt_drive_convert(posix_abs: PurePosixPath) -> Optional[str]:
    """
    @brief /mnt/<drive> 形式のパスを手動で Windows ドライブ形式に変換

    対象でない場合は None を返す
    """
    parts = posix_abs.parts
    if len(parts) == 0 or parts[0] != "/":
        return None

    # parts 例: ('/', 'mnt', 'c', 'Users', 'name')
    idx_mnt = 1 if len(parts) > 1 and parts[0] == "/" else 0
    if len(parts) > idx_mnt + 1 and parts[idx_mnt] == "mnt":
        drive_letter = parts[idx_mnt + 1].upper()
        if len(drive_letter) != 1 or not drive_letter.isalpha():
            return None
        drive = f"{drive_letter}:\\"
        rest_parts = parts[idx_mnt + 2 :]
        if rest_parts:
            win_path = PureWindowsPath(drive, *rest_parts)
            return str(win_path)
        return drive
    return None


def _wsl_unc_fallback(posix_abs: PurePosixPath) -> Optional[str]:
    """
    @brief \\wsl$\\<distro> UNC 経路へのフォールバック生成

    WSL_DISTRO_NAME が存在し、絶対パスの場合のみ生成
    """
    distro = os.environ.get("WSL_DISTRO_NAME")
    if not distro or not posix_abs.is_absolute():
        return None

    parts = list(posix_abs.parts)
    # 先頭の "/" を除去し Windows 区切りに変換
    if parts and parts[0] == "/":
        parts = parts[1:]
    tail = "\\".join(parts) if parts else ""
    return f"\\\\wsl$\\{distro}\\{tail}"


def posix_to_windows(
    path: Union[str, os.PathLike],
    *,
    strict: bool = True,
    allow_unc_fallback: bool = True,
) -> str:
    R"""
    @brief POSIXパスをWindowsパスに変換する

    優先順位
    1. WSL環境なら wslpath を利用
    2. /mnt/<drive> の手動変換
    3. WSL UNC 経路へのフォールバック (任意)
    4. 非WSL環境では入力をそのまま返す

    strict=True の場合、WSL環境で変換不能なら PathConversionError を送出
    """
    if not isinstance(path, (str, os.PathLike)):
        raise TypeError(f"PathLike または str が必要: {type(path)}")

    path_str = os.fspath(path)

    # ~ 展開
    if "~" in path_str:
        path_str = os.path.expanduser(path_str)

    in_wsl = is_wsl_environment()

    # 1. wslpath 試行
    if in_wsl:
        try:
            return _run_wslpath(path_str)
        except PathConversionError as e:
            logger.debug("wslpath 失敗: %s", e)

    # 2. /mnt/<drive> 手動変換
    posix = PurePosixPath(path_str)
    if in_wsl and posix.is_absolute():
        manual = _manual_mnt_drive_convert(posix)
        if manual is not None:
            return manual

    # 3. UNC フォールバック
    if in_wsl and allow_unc_fallback and posix.is_absolute():
        unc = _wsl_unc_fallback(posix)
        if unc is not None:
            return unc

    # 4. 非WSL環境、または変換不能時の扱い
    if in_wsl and strict:
        raise PathConversionError(f"WSL環境でパス変換に失敗 | 入力: {path_str}")
    return path_str
