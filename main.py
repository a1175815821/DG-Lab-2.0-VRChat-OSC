import asyncio
import logging
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn
from settings import settings
from common.paths import BASE_DIR
from routers import coyote, osc_server, vrc_osc
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()

app.include_router(coyote.router)
app.include_router(osc_server.router)
app.include_router(vrc_osc.router)


BACKEND_PORT = 38080


def _make_console_encoding_safe():
    """让控制台输出永远不会因为编码问题抛异常。

    打包版是 console=True，日志里有大量中文。Windows 控制台编码由代码页决定，
    在非中文系统上可能是 cp1252/cp437 —— 这些编码表示不了中文，直接 write 会抛
    UnicodeEncodeError。日志本身崩掉事小，但如果它发生在错误处理路径里
    （例如「配置文件读不了，回落默认值」），就会把兜底逻辑一起带走。
    这里把 stdout/stderr 的 errors 放宽成 replace，最坏情况是显示成问号。
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except Exception:
            pass


_make_console_encoding_safe()


def _log_osc_startup_result(task: asyncio.Task):
    """startup 里 OSC 服务是 create_task 起的，异常必须有人取，否则静默失败。"""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logging.error("OSC 服务启动失败：%s", exc, exc_info=exc)


@app.on_event("startup")
async def app_startup():
    # 日志级别可用环境变量覆盖：OSC_TOYS_LOG_LEVEL=DEBUG 能看到每个窗口周期的
    # 强度下发、avatar 扫描明细等（默认 INFO，避免打包版控制台被刷屏拖慢）。
    logging.basicConfig(level=os.environ.get("OSC_TOYS_LOG_LEVEL", "INFO").upper())
    # 应用启动时即启动 OSC 监听服务，独立于 Coyote 设备连接
    # 用户无需连接设备即可测试 VRChat OSC 信号是否正常
    # 启动时强制恢复功率更新锁，避免上次异常退出遗留 can_update_power=false
    if not settings.can_update_power:
        settings.can_update_power = True
        try:
            settings.dump()
        except Exception:
            pass
    osc_task = asyncio.create_task(coyote.serve_osc())
    osc_task.add_done_callback(_log_osc_startup_result)


@app.on_event("shutdown")
async def app_shutdown():
    await coyote.stop_coyote()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/settings")
async def get_settings():
    """返回当前配置。

    额外附带 `coyote_connect_budget`（蓝牙连接最坏耗时，秒）：前端用它做
    连接倒计时与请求超时。之前前端硬编码 40s，比后端最坏 130s 短得多，
    倒计时一到就 abort + /stop，慢速设备永远连不上。
    """
    data = settings._as_dict()
    data["coyote_connect_budget"] = settings.connect_budget()
    return data


FRONTEND_DIR = os.path.join(BASE_DIR, "frontend", "out")


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_spa(full_path: str):
    """静态导出前端回退：把 /coyote 映射到 coyote.html，避免桌面窗口刷新时 404。

    next export 只生成 index.html / coyote.html / 404.html 与 _next、assets 目录，
    没有 /coyote 目录，因此用 StaticFiles(html=True) 无法命中。这里按顺序尝试：
    1) out 下真实存在的文件（_next、assets、favicon 等）；
    2) 目录下的 index.html；
    3) <path>.html 页面文件；
    最后回退到 404.html。
    """
    # 未命中的 /api/* 必须返回 JSON 404，而不是 HTML 的 404 页面：
    # 否则前端拿到的 body 是 HTML，`err.response.data.detail` 恒为 undefined，
    # 所有接口报错都退化成「Request failed with status code 404」。
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"未知接口：/{full_path}")

    base = os.path.normpath(FRONTEND_DIR)
    target = os.path.normpath(os.path.join(FRONTEND_DIR, full_path))
    if target != base and not target.startswith(base + os.sep):
        raise HTTPException(status_code=404)

    if full_path:
        if os.path.isfile(target):
            return FileResponse(target)
        if os.path.isdir(target):
            index = os.path.join(target, "index.html")
            if os.path.isfile(index):
                return FileResponse(index)
        page_html = os.path.join(base, full_path.strip("/") + ".html")
        if os.path.isfile(page_html):
            return FileResponse(page_html)
    else:
        index = os.path.join(base, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)

    not_found = os.path.join(base, "404.html")
    if os.path.isfile(not_found):
        return FileResponse(not_found, status_code=404)
    raise HTTPException(status_code=404)


def _local_opener() -> urllib.request.OpenerDirector:
    """访问本机回环地址专用的 opener：显式禁用系统代理。

    urllib 默认会读取系统代理设置（Windows 上来自 IE/注册表）。如果机器上配了
    代理且没有把 127.0.0.1 列入 bypass，`http://127.0.0.1:38080/...` 会被送到
    代理，拿到 502 —— 表现就是「后端明明在跑，健康检查却一直失败」，
    更要命的是退出时的优雅停机请求也会一起失败（设备功率可能不被归零）。
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _wait_for_server(url: str = None, timeout: float = 30.0) -> bool:
    """等待 uvicorn 就绪后再打开窗口，避免白屏。"""
    url = url or f"http://127.0.0.1:{BACKEND_PORT}/health"
    opener = _local_opener()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with opener.open(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    return False


def run_webview():
    # 延迟导入：模块级 `import webview` 会让 `uvicorn main:app` 在服务器 /
    # 未装 pywebview 的环境里直接 ImportError，连纯后端都起不来。
    import webview

    if not _wait_for_server():
        logging.warning("后端健康检查超时，仍尝试打开窗口")
    # 与 _wait_for_server 保持同一个主机名：uvicorn 只监听 127.0.0.1，
    # 用 localhost 在「::1 优先」的解析顺序下可能连不上，表现为窗口白屏。
    webview.create_window(
        "DG-Lab 2.0 — VRChat OSC",
        f"http://127.0.0.1:{BACKEND_PORT}/index.html",
        width=1280,
        height=820,
    )
    webview.start()


def run_uvicorn():
    uvicorn.run(app, port=BACKEND_PORT)


def _graceful_stop_device(timeout: float = 8.0):
    """退出前先让后端把设备功率归零并断开蓝牙。

    uvicorn 跑在守护线程里，进程退出时不会给 uvicorn 任何清理机会，
    FastAPI 的 shutdown 钩子（里面的 stop_coyote，即 set_pwm(0,0) + disconnect）
    不会执行。所以必须先主动打一次停止接口。

    这里刻意用禁用了系统代理的 opener：这一步关系到「退出后设备是否还在输出」，
    不能因为机器上配了代理、而 127.0.0.1 又不在 bypass 名单里就静默失败。
    """
    try:
        with _local_opener().open(
            f"http://127.0.0.1:{BACKEND_PORT}/api/coyote/stop", timeout=timeout
        ) as resp:
            logging.info(f"优雅停机完成：HTTP {resp.status}")
    except Exception as e:
        logging.warning(f"优雅停机失败，将直接终止进程：{e}")


def _stop_uvicorn(thread: threading.Thread):
    """先优雅停机（让后端归零功率并断开蓝牙），再随进程退出回收守护线程。

    原实现用 multiprocessing.Process 起 uvicorn 子进程，但在 PyInstaller
    单文件(one-file)打包下，Windows 默认 spawn 会重新拉起一份 exe 作为子进程，
    PyInstaller 6 的引导程序对该场景处理不稳，导致子进程起不来、38080 无监听、
    窗口打开后白屏/打不开。改为同一进程内的守护线程跑 uvicorn，彻底规避该问题。
    """
    if not thread.is_alive():
        return
    _graceful_stop_device()
    # 守护线程会在进程退出时被回收；uvicorn 的 asyncio 循环随线程结束而停止
    thread.join(timeout=5)


if __name__ == "__main__":
    uvicorn_thread = threading.Thread(target=run_uvicorn, daemon=True)
    uvicorn_thread.start()

    def _signal_handler(*_args):
        _stop_uvicorn(uvicorn_thread)
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)

    try:
        run_webview()
    finally:
        _stop_uvicorn(uvicorn_thread)
