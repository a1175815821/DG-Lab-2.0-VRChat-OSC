import logging
import multiprocessing
import os
import uvicorn
from settings import Settings, settings
from pythonosc import osc_server
from routers import coyote, osc_server, vrc_osc
from fastapi import BackgroundTasks, FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.include_router(coyote.router)
app.include_router(osc_server.router)
app.include_router(vrc_osc.router)
app.mount("/", StaticFiles(directory=r"frontend\out", html=True), name="frontend")


@app.on_event("startup")
async def app_startup():
    logging.basicConfig(level=logging.INFO)


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


def run_webview():
    webview.create_window(
        "OSC Toys", "http://localhost:38080/index.html", width=1280, height=820
    )
    webview.start(http_port=38080)


def run_uvicorn():
    uvicorn.run(app, port=38080)


if __name__ == "__main__":
    # Windows 下 Nuitka 打包后 multiprocessing 需要 freeze_support
    multiprocessing.freeze_support()
    # uvicorn 作为 daemon 子进程运行，主进程退出时自动终止
    uvicorn_process = multiprocessing.Process(target=run_uvicorn, daemon=True)
    uvicorn_process.start()
    try:
        # 主进程运行 webview，窗口关闭后 run_webview 返回
        run_webview()
    finally:
        # 强制退出整个进程树，避免 uvicorn 后台残留导致 cmd 不关闭
        os._exit(0)
