"""资源路径解析。

打包后（PyInstaller / Nuitka）相对路径 `open('settings.yaml')` 会失败，
必须基于 exe/解压目录定位资源。本模块统一导出 BASE_DIR，其它文件应使用
`from common.paths import BASE_DIR` 并用 `os.path.join(BASE_DIR, ...)`。
"""
import os
import sys


def _resolve_base_dir() -> str:
    if getattr(sys, "frozen", False):
        # PyInstaller COLLECT 模式：数据文件在 sys._MEIPASS 下
        if hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        # Nuitka standalone / onefile：数据文件在 exe 同目录
        return os.path.dirname(os.path.abspath(sys.executable))
    # 开发模式：源码目录（settings.py 同级）
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))


BASE_DIR = _resolve_base_dir()
