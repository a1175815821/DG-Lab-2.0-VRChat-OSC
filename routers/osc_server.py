from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from routers.coyote import serve_osc
from settings import settings

import ipaddress


router = APIRouter(prefix="/api/osc_server")


class OSCAddress(BaseModel):
    # 端口越界（如 70000）以前会一路走到 socket.bind() 才失败：接口 500，
    # 而且旧监听已被关闭 → OSC 直接停摆。这里在入参层就拦掉，返回 422。
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)


def _validate_host(host: str) -> None:
    """监听主机校验：拒绝空值与「所有网卡」。

    OSC 是电刺激设备的控制面：监听 0.0.0.0/:: 意味着同一局域网内的任意主机
    都能往 9001 发包驱动设备。默认必须只监听本机；确有非本机需求时，
    请手动编辑 settings.yaml 的 vrc_host（自担风险）。
    """
    h = (host or "").strip()
    if h in ("0.0.0.0", "::", "::0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "不允许监听所有网卡（0.0.0.0/::）：这会让局域网内任意主机向设备发送 OSC。"
                "请使用 127.0.0.1；确有需要请手动编辑 settings.yaml 的 vrc_host。"
            ),
        )
    try:
        ipaddress.ip_address(h)
        return
    except ValueError:
        pass
    if len(h) > 253 or any(c.isspace() for c in h):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"监听主机不是合法的 IP 或主机名：{h!r}",
        )


@router.post("/address")
async def update_address(req: OSCAddress):
    """
    设置 VRChat OSC 监听地址并热重启 OSC 服务。
    无需断开 Coyote 设备，OSC 监听会自动重启应用新地址。
    """
    try:
        _validate_host(req.host)
        old_host, old_port = settings.vrc_host, settings.vrc_osc_port
        settings.vrc_host = req.host.strip()
        settings.vrc_osc_port = req.port
        try:
            # 先绑成功再落盘。以前是先 dump 再 serve_osc：绑定失败时新地址
            # 已经写进 settings.yaml，而监听还是旧的 —— 重启后 OSC 启动即
            # 失败（彻底收不到信号），且本次会话内 /osc_addr 也会因为反复
            # 重绑这个失败地址而全部 500（实测级联）。
            await serve_osc()
        except Exception:
            # 绑定失败：内存回滚到旧地址即可（磁盘从未写入新值），
            # 旧监听继续工作，后续 /osc_addr 也不再受牵连。
            settings.vrc_host, settings.vrc_osc_port = old_host, old_port
            raise
        # 持久化到 settings.yaml
        settings.dump()
        return {"msg": "success"}
    except HTTPException:
        raise
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
