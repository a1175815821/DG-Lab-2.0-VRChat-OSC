"""资源路径解析。

打包后（Nuitka onefile / PyInstaller）相对路径 `open('settings.yaml')` 会失败，
必须基于 exe/解压目录定位资源。

关键区分：
- 只读资源（frontend/out, data 等）：打包后被解压到临时目录，从解压目录读取
- 用户配置（settings.yaml）：必须从 exe 真实所在目录读写，用户可见可编辑

Nuitka onefile 模式特性：
- `sys.executable` 指向临时解压目录里的 exe 副本
- `sys.argv[0]` 指向用户运行的真实 exe 路径
- `__file__` 指向临时解压目录

PyInstaller onefile 模式特性：
- `sys._MEIPASS` 指向解压目录
- `sys.executable` 指向真实 exe 路径
"""
import os
import sys


def _is_packaged() -> bool:
    """是否处于打包模式（Nuitka 或 PyInstaller）"""
    return getattr(sys, "frozen", False) or "__compiled__" in dir(sys)


def _resolve_resources_dir() -> str:
    """只读资源目录（frontend/out, data, patterns）。
    打包后指向解压目录；开发模式指向项目根目录。
    """
    # PyInstaller：数据文件在 sys._MEIPASS 下
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    # Nuitka onefile / standalone：__file__ 在解压后的临时目录里
    if _is_packaged():
        return os.path.dirname(os.path.abspath(__file__))
    # 开发模式：源码目录（common/ 的上级）
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))


def _resolve_user_data_dir() -> str:
    """用户配置目录（settings.yaml）。
    打包后指向 exe 真实所在目录（用户下载解压的目录）；开发模式指向项目根目录。
    """
    if _is_packaged():
        # Nuitka onefile：sys.argv[0] 是用户运行的原始 exe 路径
        # PyInstaller：sys.executable 也是真实 exe 路径
        # 两者用 sys.argv[0] 都能拿到真实路径，更稳妥
        if sys.argv and sys.argv[0]:
            return os.path.dirname(os.path.abspath(sys.argv[0]))
        # 兜底：sys.executable（PyInstaller 可靠，Nuitka onefile 可能是临时目录）
        return os.path.dirname(os.path.abspath(sys.executable))
    # 开发模式：源码目录
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))


# 只读资源目录（frontend/out, data 等）
BASE_DIR = _resolve_resources_dir()
# 用户配置目录（settings.yaml）
USER_DATA_DIR = _resolve_user_data_dir()
