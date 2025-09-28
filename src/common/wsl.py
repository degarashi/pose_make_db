import subprocess
from pathlib import Path
import os


def is_wsl_environment() -> bool:
    """
    @brief WSL環境かどうかの判定

    判定基準
    - WSL_DISTRO_NAME 環境変数の存在
    - WSL_INTEROP 環境変数の存在

    @return True の場合は WSL 環境
    """
    wsl_keys = ["WSL_DISTRO_NAME", "WSL_INTEROP"]
    return any(key in os.environ for key in wsl_keys)


def posix_to_windows(path: str) -> str:
    R"""
    @brief POSIXパスをWindowsパスに変換

    汎用的な変換関数
    優先順位
    1. WSL 環境なら wslpath を利用 (最も正確)
    2. /mnt/<drive> プレフィックスを手動変換
    3. それ以外は入力をそのまま返す

    @param path POSIX形式のパス文字列
    @return Windows形式のパス文字列
    """
    # 1. Try wslpath if available
    if "WSL_INTEROP" in os.environ or "WSL_DISTRO_NAME" in os.environ:
        try:
            result = subprocess.run(
                ["wslpath", "-w", path], capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except Exception:
            pass  # fallback to manual conversion

    # 2. Manual conversion for /mnt/<drive>
    p = Path(path)
    parts = p.parts
    if len(parts) > 2 and parts[1] == "mnt":
        drive_letter = parts[2].upper() + ":"
        rest = "\\".join(parts[3:])
        return f"{drive_letter}\\{rest}" if rest else drive_letter + "\\"

    # 3. Fallback: return as-is
    return path
