import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import time
import urllib.error
import urllib.request

import uvicorn
from settings import Settings, settings
from common.paths import BASE_DIR
from pythonosc import osc_server
from routers import coyote, osc_server, vrc_osc
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.include_router(coyote.router)
app.include_router(osc_server.router)
app.include_router(vrc_osc.router)
app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "frontend", "out"), html=True), name="frontend")


@app.on_event("startup")
async def app_startup():
    logging.basicConfig(level=logging.INFO)
    # 应用启动时即启动 OSC 监听服务，独立于 Coyote 设备连接
    # 用户无需连接设备即可测试 VRChat OSC 信号是否正常
    # 启动时强制恢复功率更新锁，避免上次异常退出遗留 can_update_power=false
    if not settings.can_update_power:
        settings.can_update_power = True
        try:
            settings.dump()
        except Exception:
            pass
    asyncio.create_task(coyote.serve_osc())


@app.on_event("shutdown")
async def app_shutdown():
    await coyote.stop_coyote()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/settings")
async def get_settings() -> Settings:
    return settings


import webview


def _wait_for_server(url: str = "http://127.0.0.1:38080/health", timeout: float = 30.0) -> bool:
    """等待 uvicorn 就绪后再打开窗口，避免白屏。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    return False


def run_webview():
    if not _wait_for_server():
        logging.warning("后端健康检查超时，仍尝试打开窗口")
    webview.create_window(
        "DG-Lab 2.0 — VRChat OSC",
        "http://localhost:38080/index.html",
        width=1280,
        height=820,
    )
    webview.start()


def run_uvicorn():
    uvicorn.run(app, port=38080)


def _stop_uvicorn(proc: multiprocessing.Process):
    """终止 uvicorn 子进程"""
    if not proc.is_alive():
        return
    proc.terminate()
    proc.join(timeout=5)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=3)


if __name__ == "__main__":
    multiprocessing.freeze_support()

    uvicorn_process = multiprocessing.Process(target=run_uvicorn, daemon=True)
    uvicorn_process.start()

    def _signal_handler(*_args):
        _stop_uvicorn(uvicorn_process)
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)

    try:
        run_webview()
    finally:
        _stop_uvicorn(uvicorn_process)
