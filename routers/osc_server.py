from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from routers.coyote import ci
from settings import settings


router = APIRouter(prefix="/api/osc_server")


class OSCAddress(BaseModel):
    host: str
    port: int


@router.post("/address")
async def update_address(req: OSCAddress):
    """
    设置 VRChat OSC 监听地址。
    设备已连接时不允许修改，需先断开。
    """
    if ci.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="设备已连接，无法修改地址，请先断开设备。",
        )
    try:
        settings.vrc_host = req.host
        settings.vrc_osc_port = req.port
        # 持久化到 settings.yaml，避免重启后丢失
        settings.dump()
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
