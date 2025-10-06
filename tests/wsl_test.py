import builtins
import os
import sys
from pathlib import PurePosixPath, PureWindowsPath

import pytest
from src.common.wsl import (
    PathConversionError,
    WslVariant,
    _get_kernel_release,
    _manual_mnt_drive_convert,
    _wsl_unc_fallback,
    get_wsl_variant,
    is_wsl_environment,
    posix_to_windows,
)


class DummyUname:
    def __init__(self, release: str):
        self.release = release


def test_get_kernel_release_from_uname(monkeypatch):
    monkeypatch.setattr(os, "uname", lambda: DummyUname("5.15.0-91-generic"))
    assert _get_kernel_release() == "5.15.0-91-generic"


def test_get_kernel_release_from_proc(monkeypatch, tmp_path):
    monkeypatch.delattr(os, "uname", raising=False)
    fake_proc = tmp_path / "osrelease"
    fake_proc.write_text("4.4.0-19041-Microsoft\n", encoding="utf-8")
    monkeypatch.setattr(
        builtins, "open", lambda *a, **k: fake_proc.open("r", encoding="utf-8")
    )
    assert _get_kernel_release() == "4.4.0-19041-Microsoft"


def test_get_wsl_variant_wsl1(monkeypatch):
    monkeypatch.setattr(
        "src.common.wsl._get_kernel_release", lambda: "4.4.0-19041-Microsoft"
    )
    get_wsl_variant.cache_clear()
    assert get_wsl_variant() == WslVariant.WSL1


def test_get_wsl_variant_wsl2(monkeypatch):
    monkeypatch.setattr(
        "src.common.wsl._get_kernel_release",
        lambda: "5.15.167.4-microsoft-standard-WSL2",
    )
    get_wsl_variant.cache_clear()
    assert get_wsl_variant() == WslVariant.WSL2


def test_get_wsl_variant_none(monkeypatch):
    monkeypatch.setattr(
        "src.common.wsl._get_kernel_release", lambda: "5.15.0-91-generic"
    )
    get_wsl_variant.cache_clear()
    assert get_wsl_variant() is None


def test_is_wsl_environment_with_variant(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("src.common.wsl.get_wsl_variant", lambda: WslVariant.WSL2)
    monkeypatch.setattr(os.path, "isdir", lambda p: True)
    is_wsl_environment.cache_clear()
    assert is_wsl_environment() is True


def test_is_wsl_environment_with_env(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("src.common.wsl.get_wsl_variant", lambda: None)
    monkeypatch.setattr(os.path, "isdir", lambda p: True)
    monkeypatch.setitem(os.environ, "WSL_DISTRO_NAME", "Ubuntu")
    is_wsl_environment.cache_clear()
    assert is_wsl_environment() is True


def test_is_wsl_environment_false(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    is_wsl_environment.cache_clear()
    assert is_wsl_environment() is False


def test_manual_mnt_drive_convert_valid():
    p = PurePosixPath("/mnt/c/Users/test")
    result = _manual_mnt_drive_convert(p)
    assert result.startswith("C:")


def test_manual_mnt_drive_convert_invalid():
    p = PurePosixPath("/home/user")
    assert _manual_mnt_drive_convert(p) is None


def test_wsl_unc_fallback(monkeypatch):
    monkeypatch.setitem(os.environ, "WSL_DISTRO_NAME", "Ubuntu")
    p = PurePosixPath("/home/user")
    result = _wsl_unc_fallback(p)
    assert result.startswith(r"\\wsl$\Ubuntu")


def test_wsl_unc_fallback_none(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    p = PurePosixPath("/home/user")
    assert _wsl_unc_fallback(p) is None


def test_posix_to_windows_non_wsl(monkeypatch):
    monkeypatch.setattr("src.common.wsl.is_wsl_environment", lambda: False)
    path = "/home/user"
    assert posix_to_windows(path) == path


def test_posix_to_windows_manual(monkeypatch):
    monkeypatch.setattr("src.common.wsl.is_wsl_environment", lambda: True)
    monkeypatch.setattr(
        "src.common.wsl._run_wslpath",
        lambda p: (_ for _ in ()).throw(PathConversionError("fail")),
    )
    path = "/mnt/c/Users/test/kusoge.jpg"
    result = posix_to_windows(path)
    assert result.startswith("C:")


def test_posix_to_windows_unc(monkeypatch):
    monkeypatch.setattr("src.common.wsl.is_wsl_environment", lambda: True)
    monkeypatch.setattr(
        "src.common.wsl._run_wslpath",
        lambda p: (_ for _ in ()).throw(PathConversionError("fail")),
    )
    monkeypatch.setitem(os.environ, "WSL_DISTRO_NAME", "Ubuntu")
    path = "/home/user"
    result = posix_to_windows(path, allow_unc_fallback=True)
    assert result.startswith(r"\\wsl$")


def test_posix_to_windows_strict_failure(monkeypatch):
    monkeypatch.setattr("src.common.wsl.is_wsl_environment", lambda: True)
    monkeypatch.setattr(
        "src.common.wsl._run_wslpath",
        lambda p: (_ for _ in ()).throw(PathConversionError("fail")),
    )
    monkeypatch.setattr("src.common.wsl._manual_mnt_drive_convert", lambda p: None)
    monkeypatch.setattr("src.common.wsl._wsl_unc_fallback", lambda p: None)
    with pytest.raises(PathConversionError):
        posix_to_windows("/home/user", strict=True)


TEST_PATH = "/mnt/e/test_dir/test.jpg"


def test_posix_to_windows_test_path_manual(monkeypatch):
    monkeypatch.setattr("src.common.wsl.is_wsl_environment", lambda: True)
    monkeypatch.setattr(
        "src.common.wsl._run_wslpath",
        lambda p: (_ for _ in ()).throw(PathConversionError("fail")),
    )
    result = posix_to_windows(TEST_PATH)
    assert result.startswith("E:\\")
    assert "\\test_dir\\" in result
    assert result.endswith("test.jpg")


def test_posix_to_windows_test_path_unc(monkeypatch):
    monkeypatch.setattr("src.common.wsl.is_wsl_environment", lambda: True)
    monkeypatch.setattr(
        "src.common.wsl._run_wslpath",
        lambda p: (_ for _ in ()).throw(PathConversionError("fail")),
    )
    monkeypatch.setattr("src.common.wsl._manual_mnt_drive_convert", lambda p: None)
    monkeypatch.setitem(os.environ, "WSL_DISTRO_NAME", "Ubuntu")
    result = posix_to_windows(TEST_PATH, allow_unc_fallback=True)
    assert result.startswith(r"\\wsl$\Ubuntu")
    assert "\\mnt\\e\\test_dir\\" in result


def test_posix_to_windows_test_path_non_wsl(monkeypatch):
    monkeypatch.setattr("src.common.wsl.is_wsl_environment", lambda: False)
    assert posix_to_windows(TEST_PATH) == TEST_PATH


def test_manual_mnt_drive_convert_valid_root_drive():
    p = PurePosixPath("/mnt/c")
    result = _manual_mnt_drive_convert(p)
    # ドライブ直下は "C:\" になる
    assert result == "C:\\"


def test_manual_mnt_drive_convert_valid_with_subdirs():
    p = PurePosixPath("/mnt/d/Projects/code")
    result = _manual_mnt_drive_convert(p)
    # Windows パス形式に変換される
    assert result.startswith("D:")
    assert r"\Projects\code" in result
    # PureWindowsPath で再構築して比較
    expected = str(PureWindowsPath("D:\\", "Projects", "code"))
    assert result == expected


def test_manual_mnt_drive_convert_invalid_drive_letter():
    # ドライブ文字が数字 → 無効
    p = PurePosixPath("/mnt/1/Users/test")
    assert _manual_mnt_drive_convert(p) is None

    # ドライブ文字が2文字以上 → 無効
    p = PurePosixPath("/mnt/ab/Users/test")
    assert _manual_mnt_drive_convert(p) is None


def test_manual_mnt_drive_convert_not_mnt_path():
    # /home 以下は対象外
    p = PurePosixPath("/home/user")
    assert _manual_mnt_drive_convert(p) is None

    # ルート直下も対象外
    p = PurePosixPath("/c/Users/test")
    assert _manual_mnt_drive_convert(p) is None


def test_manual_mnt_drive_convert_relative_path():
    # 相対パスは対象外
    p = PurePosixPath("mnt/c/Users/test")
    assert _manual_mnt_drive_convert(p) is None
