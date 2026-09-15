from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from routers.coyote import serve_osc
from settings import settings


router = APIRouter(prefix="/api/osc_server")


class OSCAddress(BaseModel):
    # 端口越界（如 70000）以前会一路走到 socket.bind() 才失败：接口 500，
    # 而且旧监听已被关闭 → OSC 直接停摆。这里在入参层就拦掉，返回 422。
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)


@router.post("/address")
async def update_address(req: OSCAddress):
    """
    设置 VRChat OSC 监听地址并热重启 OSC 服务。
    无需断开 Coyote 设备，OSC 监听会自动重启应用新地址。
    """
    try:
        settings.vrc_host = req.host
        settings.vrc_osc_port = req.port
        # 持久化到 settings.yaml
        settings.dump()
        # 热重启 OSC 服务以应用新地址
        await serve_osc()
        return {"msg": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/address")
async def get_address():
    """
    Get the OSC address of the device.
    """
    try:
        return {
            "host": settings.vrc_host,
            "port": settings.vrc_osc_port,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
