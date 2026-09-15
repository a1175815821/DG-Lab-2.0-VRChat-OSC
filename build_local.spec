# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec 文件用于本地测试构建 osc-toys.exe
# 使用方式: pyinstaller build_local.spec

import os

block_cipher = None

# 项目根目录
PROJECT_ROOT = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        # 只读资源（前端静态文件、patterns、配置示例）
        ('frontend/out', 'frontend/out'),
        ('data', 'data'),
        ('settings.yaml', '.'),
    ],
    excludes=[
        # 只排除与本项目无关的「非 Windows」GUI 后端，以及被它们拖进来的重型依赖。
        # ⚠️ 注意：webview.platforms.winforms 是 Windows 上 pywebview 的**唯一入口**
        # （edgechromium/WebView2 由 winforms 模块内部承载，见 platforms/winforms.py
        # 的 `from . import edgechromium as Chromium`），绝不能排除——否则 pywebview
        # 会抛 "You must have pythonnet installed in order to use pywebview."。
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'matplotlib', 'IPython', 'numpy', 'pandas', 'scipy', 'cv2', 'PIL',
        'webview.platforms.qt', 'webview.platforms.gtk', 'webview.platforms.cocoa',
        'webview.platforms.cef',
    ],
    hiddenimports=[
        # uvicorn 子模块
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # uvicorn.run 运行时按配置动态 import 这些实现模块，PyInstaller 6 不会自动收集
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets.websockets_impl',
        # 注意：不要加 'uvicorn.workers' —— 它 import gunicorn，而本项目不装 gunicorn，
        # 只会让 PyInstaller 报一条 missing module 噪音，掩盖真正的缺模块警告。
        # pywebview edgechromium 平台（Windows 默认渲染器，由 winforms 承载）
        'webview.platforms.edgechromium',
        # Windows 上 pywebview 的唯一入口模块 + 其依赖的 win32 工具模块
        'webview.platforms.winforms',
        'webview.platforms.win32',
        # pythonnet：WinForms 后端需要 clr（import clr），
        # 其 PyInstaller hook 由 pythonnet 的 pyinstaller40 entry point 自动提供
        'clr',
        # python-osc（没有 pythonosc.handler 这个模块）
        'pythonosc.osc_server',
        'pythonosc.dispatcher',
        # 项目内部路由/模块（common 下只有 paths.py，没有 util.py）
        'routers.coyote',
        'routers.vrc_osc',
        'routers.osc_server',
        'toys.estim',
        'toys.estim.coyote',
        'toys.estim.coyote.dg_interface',
        'common.paths',
        # bleak 蓝牙相关
        'bleak',
        'bleak.backends.winrt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='osc-toys',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台窗口，方便查看日志和 ctrl+c 退出
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
