from collections import deque
import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
import asyncio
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from settings import settings
import time
import logging
from toys.estim.coyote.dg_interface import CoyoteInterface
from toys.estim.coyote import dg_interface as dgi
from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
from fastapi import BackgroundTasks


router = APIRouter(prefix="/api/coyote")


ci = CoyoteInterface(
    device_uid=settings.coyote_uid,
    power_multiplier=settings.coyote_multiplier,
    safe_mode=settings.coyote_safe_mode,
)

transport = None  # OSC transport，独立于设备连接
_signal_task: Optional[asyncio.Task] = None  # 信号输出任务（start_channel_a/b）

# ─── VRChat 当前穿戴模型追踪 ──────────────────────────────────────────────
current_vrc_avatar_id: Optional[str] = None  # 通过 /avatar/change 实时更新
current_vrc_avatar_ts: float = 0.0  # 上次更新时间戳


def avatar_change_handler(addr, args, avatar_id):
    """监听 VRChat 切换模型事件，实时记录当前穿戴的 avatar ID"""
    global current_vrc_avatar_id, current_vrc_avatar_ts
    if isinstance(avatar_id, str) and avatar_id.startswith("avtr_"):
        current_vrc_avatar_id = avatar_id
        current_vrc_avatar_ts = time.time()
        logging.info(f"VRChat 切换模型: {avatar_id}")


# ─── can_update_power 超时兜底 ────────────────────────────────────────────
# set_pwm 设为 False 后，如果 signal() 异常退出会永久失效。
# dg_interface 记录设置时间，超过 5 秒未恢复则自动恢复。
_POWER_LOCK_TIMEOUT = 5.0  # 秒


def _check_power_lock_timeout():
    """检查 can_update_power 是否超时，超时则自动恢复"""
    global settings
    if not settings.can_update_power and dgi._can_update_power_set_time > 0:
        if time.time() - dgi._can_update_power_set_time > _POWER_LOCK_TIMEOUT:
            settings.can_update_power = True
            logging.warning("can_update_power 超时未恢复，已自动重置为 True")


# ─── OSC 信号处理 ─────────────────────────────────────────────────────────
param_queue_a: List[float] = []
param_queue_b: List[float] = []
last_time_a = time.time()
cur_time_a: Optional[float] = None
last_time_b = time.time()
cur_time_b: Optional[float] = None

# ─── 实时监控数据 ──────────────────────────────────────────────────────────
latest_raw_a: float = 0.0        # 最新收到的 A 通道原始 OSC 值
latest_raw_b: float = 0.0        # 最新收到的 B 通道原始 OSC 值
latest_avg_a: float = 0.0        # 最近一次计算的 A 通道平均值
latest_avg_b: float = 0.0        # 最近一次计算的 B 通道平均值
latest_mapped_a: float = 0.0     # 最近一次映射后的 A 通道输出比例 (0-1)
latest_mapped_b: float = 0.0     # 最近一次映射后的 B 通道输出比例 (0-1)
msg_history: deque = deque(maxlen=20)  # 最近 20 条 OSC 消息记录


def _push_history(ch: str, raw: float):
    """向消息历史追加一条记录（仅原始值，avg/mapped 由首次 SSE 构建时从全局变量读取）"""
    msg_history.append({
        "ts": time.time(),
        "ch": ch,
        "raw": round(raw, 4),
    })


def _build_monitor_payload() -> Dict[str, Any]:
    """构建 SSE/API 实时监控数据"""
    now = time.time()
    a_active = cur_time_a is not None and (now - cur_time_a) < 2.0
    b_active = cur_time_b is not None and (now - cur_time_b) < 2.0
    return {
        "ts": now,
        "a": {
            "raw": latest_raw_a,
            "avg": latest_avg_a,
            "mapped": latest_mapped_a,
            "active": a_active,
        },
        "b": {
            "raw": latest_raw_b,
            "avg": latest_avg_b,
            "mapped": latest_mapped_b,
            "active": b_active,
        },
        "history": list(msg_history),
        "current_avatar_id": current_vrc_avatar_id,
    }


def get_avg(queue: List[float]) -> float:
    """
    三段式信号映射：
    - 低于 start_limit → 0（断电）
    - 低于 min_limit → min_power（最小功率）
    - 高于 max_limit → 1.0（满功率）
    - 中间区域线性插值
    """
    s = 0.0
    for x in queue:
        s += x
    s /= len(queue)
    if s < settings.start_limit:
        return 0.0
    if s < settings.min_limit:
        return settings.min_power
    if s >= settings.max_limit:
        return 1.0
    s = (s - settings.min_limit) / (settings.max_limit - settings.min_limit) * (
        1 - settings.min_power
    ) + settings.min_power
    return s


def coyote_handler_a(addr, args, dis):
    """处理 A 通道 OSC 信号。记录原始值、历史，设备连接时按窗口输出功率。"""
    global param_queue_a, last_time_a, cur_time_a, latest_raw_a, latest_avg_a, latest_mapped_a
    cur_time_a = time.time()
    latest_raw_a = dis
    # 记录每条原始消息到历史
    _push_history("A", dis)

    # 设备未连接时跳过输出（OSC 监听独立于设备连接）
    if not ci or not ci.is_connected:
        return

    # 检查 can_update_power 超时兜底
    _check_power_lock_timeout()

    if cur_time_a - last_time_a > settings.window_size:
        last_time_a = time.time()
        if len(param_queue_a) == 0 or not settings.can_update_power:
            param_queue_a.append(dis)
            return
        s = get_avg(param_queue_a)
        latest_avg_a = s
        if s < settings.start_limit:
            latest_mapped_a = 0.0
            asyncio.ensure_future(ci.set_pwm(0, -1), loop=asyncio.get_event_loop())
        else:
            latest_mapped_a = s
            power = min(200, int(settings.coyote_max_power_a * s * settings.coyote_multiplier))
            asyncio.ensure_future(
                ci.set_pwm(power, -1), loop=asyncio.get_event_loop()
            )
        param_queue_a = []
    else:
        param_queue_a.append(dis)


def coyote_handler_b(addr, args, dis):
    """处理 B 通道 OSC 信号。记录原始值、历史，设备连接时按窗口输出功率。"""
    global param_queue_b, last_time_b, cur_time_b, latest_raw_b, latest_avg_b, latest_mapped_b
    cur_time_b = time.time()
    latest_raw_b = dis
    # 记录每条原始消息到历史
    _push_history("B", dis)

    if not ci or not ci.is_connected:
        return

    _check_power_lock_timeout()

    if cur_time_b - last_time_b > settings.window_size:
        last_time_b = time.time()
        if len(param_queue_b) == 0 or not settings.can_update_power:
            param_queue_b.append(dis)
            return
        s = get_avg(param_queue_b)
        latest_avg_b = s
        if s < settings.start_limit:
            latest_mapped_b = 0.0
            asyncio.ensure_future(ci.set_pwm(-1, 0), loop=asyncio.get_event_loop())
        else:
            latest_mapped_b = s
            power = min(200, int(settings.coyote_max_power_b * s * settings.coyote_multiplier))
            asyncio.ensure_future(
                ci.set_pwm(-1, power), loop=asyncio.get_event_loop()
            )
        param_queue_b = []
    else:
        param_queue_b.append(dis)


# ─── OSC 服务（独立于设备连接） ────────────────────────────────────────────
async def serve_osc():
    """启动 OSC 监听服务。独立于 Coyote 设备连接，应用启动时即运行。"""
    global transport
    # 如果已有 transport，先关闭再重启（用于地址热更新）
    if transport is not None:
        transport.close()
        transport = None
    dispatcher = Dispatcher()
    dispatcher.map(settings.coyote_addr_a, coyote_handler_a, "A")
    dispatcher.map(settings.coyote_addr_b, coyote_handler_b, "B")
    dispatcher.map("/avatar/change", avatar_change_handler, "avatar")
    server = osc_server.AsyncIOOSCUDPServer(
        (settings.vrc_host, settings.vrc_osc_port), dispatcher, asyncio.get_event_loop()
    )
    transport, _ = await server.create_serve_endpoint()
    logging.info(f"OSC 服务已启动: {settings.vrc_host}:{settings.vrc_osc_port}")


# ─── 实时监控 SSE ──────────────────────────────────────────────────────────
@router.get("/osc_stream")
async def osc_stream():
    """SSE 实时推送 OSC 信号数值、映射结果、消息历史"""

    async def event_generator():
        last_payload = None
        try:
            while True:
                payload = _build_monitor_payload()
                # 仅数据有变化时推送，减少不必要传输
                if payload != last_payload:
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    last_payload = payload
                await asyncio.sleep(0.15)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def start_signal_output():
    """启动信号输出任务（设备连接后调用）"""
    global _signal_task
    await asyncio.gather(start_channel_a(), start_channel_b())


async def start_channel_a():
    print(ci.patterns[settings.coyote_pattern_a])
    await ci.signal(
        power=int(settings.coyote_max_power_a * settings.min_power),
        pattern_name=settings.coyote_pattern_a,
        duration=100000000,
        channel="a",
    )


async def start_channel_b():
    print(ci.patterns[settings.coyote_pattern_b])
    await ci.signal(
        power=int(settings.coyote_max_power_b * settings.min_power),
        pattern_name=settings.coyote_pattern_b,
        duration=100000000,
        channel="b",
    )


# ─── API 端点 ─────────────────────────────────────────────────────────────
class StartRequest(BaseModel):
    uid: str


@router.post("/start")
async def start_coyote(req: StartRequest, background_tasks: BackgroundTasks):
    """连接 Coyote 设备并启动信号输出。OSC 监听已独立运行，无需在此启动。"""
    global ci, _signal_task
    if ci is not None and ci.is_connected:
        return {"msg": "already started"}
    settings.coyote_uid = req.uid
    settings.dump()
    ci = CoyoteInterface(
        device_uid=settings.coyote_uid,
        power_multiplier=settings.coyote_multiplier,
        safe_mode=settings.coyote_safe_mode,
    )
    if ci.device is None:
        await ci.search_for_device()
    await ci.connect(retries=3)
    # 只启动信号输出，OSC 监听已在应用启动时独立运行
    background_tasks.add_task(start_signal_output)
    return {"msg": "starting"}


@router.get("/stop")
async def stop_coyote():
    """停止设备并断开蓝牙。OSC 监听保持运行，不影响后续重连。"""
    global transport, _signal_task
    if not ci.is_connected:
        return {"msg": "not started"}
    await ci.stop()
    await ci.disconnect()
    # 不关闭 OSC transport，保持监听
    return {"msg": "stopping"}


class UpdatePowerRequest(BaseModel):
    pow_a: int
    pow_b: int


@router.post("/max_power")
async def update_max_power(req: UpdatePowerRequest):
    """设置 A/B 通道最大强度。安全模式下上限强制 100。"""
    try:
        safe_limit = 100 if settings.coyote_safe_mode else 200
        pow_a = min(req.pow_a, safe_limit)
        pow_b = min(req.pow_b, safe_limit)
        if settings.coyote_max_power_a != 0:
            percentage_a = ci.pow_a / settings.coyote_max_power_a
        else:
            percentage_a = 0.5
        if settings.coyote_max_power_b != 0:
            percentage_b = ci.pow_b / settings.coyote_max_power_b
        else:
            percentage_b = 0.5
        settings.coyote_max_power_a = pow_a
        settings.coyote_max_power_b = pow_b
        await ci.set_pwm(int(percentage_a * pow_a), int(percentage_b * pow_b))
        settings.dump()
        return {"msg": "success", "max_power_a": pow_a, "max_power_b": pow_b}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


class UpdateSafeModeRequest(BaseModel):
    safe_mode: bool


@router.get("/safe_mode")
async def get_safe_mode():
    """获取安全模式状态。"""
    try:
        return {"safe_mode": settings.coyote_safe_mode}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/safe_mode")
async def update_safe_mode(req: UpdateSafeModeRequest):
    """设置安全模式。启用后最大强度限制为 100 并自动裁剪已有值。"""
    try:
        settings.coyote_safe_mode = req.safe_mode
        if ci is not None:
            ci.safe_mode = req.safe_mode
        if req.safe_mode:
            if settings.coyote_max_power_a > 100:
                settings.coyote_max_power_a = 100
            if settings.coyote_max_power_b > 100:
                settings.coyote_max_power_b = 100
        settings.dump()
        return {"msg": "success", "safe_mode": settings.coyote_safe_mode}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/max_power")
async def get_max_power():
    """获取 A/B 通道最大强度。"""
    try:
        return {
            "pow_a": settings.coyote_max_power_a,
            "pow_b": settings.coyote_max_power_b,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


class UpdateOscAddrRequest(BaseModel):
    addr_a: str
    addr_b: str


@router.post("/osc_addr")
async def update_osc_addr(req: UpdateOscAddrRequest):
    """热更新 OSC 地址。无需断开设备，直接重启 OSC 监听服务。"""
    try:
        settings.coyote_addr_a = req.addr_a
        settings.coyote_addr_b = req.addr_b
        settings.dump()
        # 重启 OSC 服务以应用新地址
        await serve_osc()
        return {"msg": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/osc_addr")
async def get_osc_addr():
    """获取 A/B 通道 OSC 地址。"""
    try:
        return {
            "addr_a": settings.coyote_addr_a,
            "addr_b": settings.coyote_addr_b,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/patterns")
async def get_patterns():
    """获取 patterns 列表。"""
    try:
        return {"patterns": list(ci.patterns.keys())}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/patterns/detail")
async def get_patterns_detail():
    """返回所有 patterns 的详细波形数据。"""
    try:
        return {"patterns": ci.patterns}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


class UpdatePatternRequest(BaseModel):
    pattern_a: str
    pattern_b: str


@router.post("/pattern")
async def update_pattern(req: UpdatePatternRequest):
    """设置 A/B 通道 pattern。"""
    try:
        if req.pattern_a in ci.patterns.keys():
            settings.coyote_pattern_a = req.pattern_a
            ci.pattern_name_a = req.pattern_a
        if req.pattern_b in ci.patterns.keys():
            settings.coyote_pattern_b = req.pattern_b
            ci.pattern_name_b = req.pattern_b
        ci.switch_pattern = True
        settings.dump()
        return {"msg": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/pattern")
async def get_pattern():
    """获取当前 pattern 设置。"""
    try:
        return {
            "pattern_a": settings.coyote_pattern_a,
            "pattern_b": settings.coyote_pattern_b,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/status")
async def get_status():
    """获取设备连接状态。"""
    try:
        if ci and ci.is_connected:
            return {
                "is_connected": ci.is_connected,
                "battery_level": await ci.get_bettery_level(),
                "uid": settings.coyote_uid,
            }
        else:
            return {
                "is_connected": False,
                "battery_level": 0,
                "uid": "",
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/osc_status")
async def get_osc_status():
    """获取 OSC 链接状态。"""
    try:
        now = time.time()
        a_active = cur_time_a is not None and (now - cur_time_a) < 2.0
        b_active = cur_time_b is not None and (now - cur_time_b) < 2.0
        return {
            "osc_running": transport is not None,
            "a_active": a_active,
            "b_active": b_active,
            "a_last_signal": cur_time_a,
            "b_last_signal": cur_time_b,
            "addr_a": settings.coyote_addr_a,
            "addr_b": settings.coyote_addr_b,
            "vrc_host": settings.vrc_host,
            "vrc_osc_port": settings.vrc_osc_port,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/aggregate_status")
async def get_aggregate_status():
    """聚合状态接口：一次请求返回设备状态 + OSC 状态 + 强度 + 安全模式。
    替代前端多个独立轮询，减少 HTTP 请求。
    """
    try:
        now = time.time()
        a_active = cur_time_a is not None and (now - cur_time_a) < 2.0
        b_active = cur_time_b is not None and (now - cur_time_b) < 2.0
        device_connected = ci is not None and ci.is_connected
        battery = 0
        if device_connected:
            try:
                battery = await ci.get_bettery_level()
            except Exception:
                pass
        return {
            # 设备状态
            "device_connected": device_connected,
            "battery_level": battery,
            "uid": settings.coyote_uid if device_connected else "",
            # OSC 状态
            "osc_running": transport is not None,
            "a_active": a_active,
            "b_active": b_active,
            "addr_a": settings.coyote_addr_a,
            "addr_b": settings.coyote_addr_b,
            "vrc_host": settings.vrc_host,
            "vrc_osc_port": settings.vrc_osc_port,
            # 强度
            "max_power_a": settings.coyote_max_power_a,
            "max_power_b": settings.coyote_max_power_b,
            "current_pow_a": ci.pow_a if device_connected else 0,
            "current_pow_b": ci.pow_b if device_connected else 0,
            # 安全模式
            "safe_mode": settings.coyote_safe_mode,
            # pattern
            "pattern_a": settings.coyote_pattern_a,
            "pattern_b": settings.coyote_pattern_b,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/uid")
async def get_uid():
    """获取设备 UID。"""
    try:
        return {"uid": settings.coyote_uid}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
