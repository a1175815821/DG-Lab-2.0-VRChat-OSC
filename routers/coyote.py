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


router = APIRouter(prefix="/api/coyote")


ci = CoyoteInterface(
    device_uid=settings.coyote_uid,
    power_multiplier=settings.coyote_multiplier,
    safe_mode=settings.coyote_safe_mode,
)

transport = None  # OSC transport，独立于设备连接
_osc_protocol = None  # 对应的 DatagramProtocol，持有 dispatcher，热更新地址时原地替换
osc_last_error: Optional[str] = None  # OSC 服务启动/重启失败原因，供前端展示
_last_osc_bind: Optional[tuple] = None  # 上次成功绑定的 (host, port)，热重启失败时用于回滚
_signal_task: Optional[asyncio.Task] = None  # 信号输出任务（start_channel_a/b）
_connect_task: Optional[asyncio.Task] = None  # 蓝牙连接任务，可由前端取消
_connect_cancel_event: Optional[asyncio.Event] = None

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


def _get_patterns() -> Dict[str, Any]:
    """获取 pattern 字典。优先用已有 ci（启动时已从磁盘加载），无需设备连接。"""
    if ci is not None and getattr(ci, "patterns", None):
        return ci.patterns
    return CoyoteInterface(
        device_uid="", power_multiplier=1.0, safe_mode=True
    ).patterns


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


def _coerce_signal(value) -> Optional[float]:
    """把 OSC 参数值规整成 float，非法类型返回 None。

    VRChat 的 avatar 参数可能是 Bool / Int / Float，用户也可能把地址误填成
    Bool 或字符串参数。以前这里直接 round(raw, 4)：遇到字符串会抛 TypeError，
    于是 ① OSC handler 每次收包都崩 ② latest_raw_* 已被赋成字符串，
    概览页 `value.toFixed(3)` 直接 TypeError，整个界面被 ErrorBoundary 接管。
    """
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


_unexpected_signal_warned: set = set()


def _warn_unexpected_signal(ch: str, value) -> None:
    """非数值信号只提示一次，避免刷屏。"""
    key = (ch, type(value).__name__)
    if key in _unexpected_signal_warned:
        return
    _unexpected_signal_warned.add(key)
    logging.warning(
        "通道 %s 收到非数值 OSC 参数（%s: %r），已忽略。"
        "请确认绑定的地址是 Float 类型参数。",
        ch, type(value).__name__, value,
    )


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


def _window_size() -> float:
    """窗口时长守卫：避免 window_size <= 0 导致每条消息都触发输出。"""
    w = settings.window_size
    return w if w > 0 else 0.1


def get_raw_avg(queue: List[float]) -> float:
    """计算滑动窗口内信号的原始平均值。"""
    if not queue:
        return 0.0
    return sum(queue) / len(queue)


def map_signal(s: float) -> float:
    """
    三段式信号映射：
    - 低于 start_limit → 0（断电）
    - 低于 min_limit → min_power（最小功率）
    - 高于 max_limit → 1.0（满功率）
    - 中间区域线性插值
    """
    if s < settings.start_limit:
        return 0.0
    if s < settings.min_limit:
        return settings.min_power
    if s >= settings.max_limit:
        return 1.0
    span = settings.max_limit - settings.min_limit
    if span <= 0:
        # 配置异常（min_limit >= max_limit）时避免除零，按满档处理
        return 1.0
    return (s - settings.min_limit) / span * (1 - settings.min_power) + settings.min_power


def coyote_handler_a(addr, args, dis):
    """处理 A 通道 OSC 信号。记录原始值、历史，设备连接时按窗口输出功率。"""
    global param_queue_a, last_time_a, cur_time_a, latest_raw_a, latest_avg_a, latest_mapped_a
    # 先标记「收到过消息」：即使值是非法类型，也证明 VRChat → 本程序的
    # OSC 通路是通的（界面据此显示「VRChat 已连接」），便于用户定位问题。
    cur_time_a = time.time()
    value = _coerce_signal(dis)
    if value is None:
        _warn_unexpected_signal("A", dis)
        return
    latest_raw_a = value
    # 记录每条原始消息到历史
    _push_history("A", value)

    # 设备未连接时跳过输出（OSC 监听独立于设备连接）
    # 同时清零窗口均值与映射值，避免概览页停留在断连前的旧数值上
    if not ci or not ci.is_connected:
        latest_avg_a = 0.0
        latest_mapped_a = 0.0
        return

    # 检查 can_update_power 超时兜底
    _check_power_lock_timeout()

    if cur_time_a - last_time_a > _window_size():
        last_time_a = time.time()
        if len(param_queue_a) == 0 or not settings.can_update_power:
            param_queue_a.append(value)
            return
        raw_avg = get_raw_avg(param_queue_a)
        latest_avg_a = raw_avg
        s = map_signal(raw_avg)
        # 这里必须拿原始信号 raw_avg 与 start_limit 比较。
        # s 是 map_signal() 的输出（0-1 的功率比例），拿它去比原始信号阈值，
        # 一旦用户把 min_power 调到小于 start_limit，整个 [start_limit, min_limit)
        # 区间都会被误判为断电。
        if raw_avg < settings.start_limit:
            latest_mapped_a = 0.0
            asyncio.ensure_future(ci.set_pwm(0, -1), loop=asyncio.get_event_loop())
        else:
            latest_mapped_a = s
            # power = max_power × mapped_signal × multiplier（默认 multiplier=1.0，滑块 1:1）
            # 安全模式下强制裁剪到 100，避免 multiplier 导致越界
            safe_limit = 100 if settings.coyote_safe_mode else 200
            power = min(safe_limit, int(settings.coyote_max_power_a * s * settings.coyote_multiplier))
            asyncio.ensure_future(
                ci.set_pwm(power, -1), loop=asyncio.get_event_loop()
            )
        param_queue_a = []
    else:
        param_queue_a.append(value)


def coyote_handler_b(addr, args, dis):
    """处理 B 通道 OSC 信号。记录原始值、历史，设备连接时按窗口输出功率。"""
    global param_queue_b, last_time_b, cur_time_b, latest_raw_b, latest_avg_b, latest_mapped_b
    # 同 A 通道：先标记收到消息，非法类型只忽略数值本身
    cur_time_b = time.time()
    value = _coerce_signal(dis)
    if value is None:
        _warn_unexpected_signal("B", dis)
        return
    latest_raw_b = value
    # 记录每条原始消息到历史
    _push_history("B", value)

    if not ci or not ci.is_connected:
        latest_avg_b = 0.0
        latest_mapped_b = 0.0
        return

    _check_power_lock_timeout()

    if cur_time_b - last_time_b > _window_size():
        last_time_b = time.time()
        if len(param_queue_b) == 0 or not settings.can_update_power:
            param_queue_b.append(value)
            return
        raw_avg = get_raw_avg(param_queue_b)
        latest_avg_b = raw_avg
        s = map_signal(raw_avg)
        # 同 A 通道：与 start_limit 比较的是原始信号，不是映射后的功率比例
        if raw_avg < settings.start_limit:
            latest_mapped_b = 0.0
            asyncio.ensure_future(ci.set_pwm(-1, 0), loop=asyncio.get_event_loop())
        else:
            latest_mapped_b = s
            safe_limit = 100 if settings.coyote_safe_mode else 200
            power = min(safe_limit, int(settings.coyote_max_power_b * s * settings.coyote_multiplier))
            asyncio.ensure_future(
                ci.set_pwm(-1, power), loop=asyncio.get_event_loop()
            )
        param_queue_b = []
    else:
        param_queue_b.append(value)


# ─── OSC 服务（独立于设备连接） ────────────────────────────────────────────
def _build_dispatcher() -> Dispatcher:
    """按当前配置构建 OSC 分发器。"""
    dispatcher = Dispatcher()
    dispatcher.map(settings.coyote_addr_a, coyote_handler_a, "A")
    dispatcher.map(settings.coyote_addr_b, coyote_handler_b, "B")
    dispatcher.map("/avatar/change", avatar_change_handler, "avatar")
    return dispatcher


async def _bind_osc(host: str, port: int, dispatcher: Dispatcher):
    """绑定一个 UDP 监听端点。构造与绑定都在调用方的 try 内完成。"""
    server = osc_server.AsyncIOOSCUDPServer(
        (host, port), dispatcher, asyncio.get_event_loop()
    )
    return await server.create_serve_endpoint()


async def serve_osc():
    """启动 / 热更新 OSC 监听服务。独立于 Coyote 设备连接，应用启动时即运行。

    这里刻意区分两条路径，因为「先 close 旧 socket 再 bind 同一端口」在
    Windows 上必然失败：close() 之后端口不会立刻释放，紧接着 bind 会得到
    WinError 10048，于是「点一次保存 OSC 地址」就把监听打死、接口还返回 500
    （实测连续保存 4 次，第 1、3 次失败）。所以：

    - host/port 没变（只是改了 OSC 地址）：原地替换 dispatcher，完全不碰 socket；
    - host/port 变了：先绑新端点，成功后再关旧的；失败则保留旧监听继续工作。
    """
    global transport, _osc_protocol, osc_last_error, _last_osc_bind
    target = (settings.vrc_host, settings.vrc_osc_port)

    # 路径一：监听地址未变，只重建映射（地址热更新，零风险）
    if transport is not None and _osc_protocol is not None and _last_osc_bind == target:
        _osc_protocol.dispatcher = _build_dispatcher()
        osc_last_error = None
        logging.info(
            "OSC 地址已热更新（监听 %s:%s 保持不变，未重建 socket）", target[0], target[1]
        )
        return

    # 路径二：监听地址变化，先绑新、再关旧
    old_transport = transport
    try:
        new_transport, protocol = await _bind_osc(*target, _build_dispatcher())
    except Exception as e:
        # 端口被占用（程序双开 / 其它 OSC 工具占用）或端口非法是最常见原因。
        reason = (
            f"监听 {target[0]}:{target[1]} 失败：{e}。"
            f"端口可能已被其它程序占用，或本程序已经启动了一份。"
        )
        if old_transport is not None and _last_osc_bind is not None:
            reason += (
                f" 已保留原监听 {_last_osc_bind[0]}:{_last_osc_bind[1]}，OSC 仍可用。"
            )
        osc_last_error = reason
        logging.error(reason)
        # 仍然抛出：调用方需要知道这次地址更新没有生效
        raise

    transport = new_transport
    _osc_protocol = protocol
    _last_osc_bind = target
    osc_last_error = None
    if old_transport is not None:
        old_transport.close()
    logging.info("OSC 服务已启动: %s:%s", target[0], target[1])


async def _osc_event_generator():
    """SSE 事件生成器：仅在数据变化时推送。

    比较时必须剔除 ts —— ts 每次都在变，带上它就永远不相等，
    “仅数据变化时推送”会退化成无条件每 0.15s 推一次完整 payload。
    """
    last_snapshot = None
    try:
        while True:
            payload = _build_monitor_payload()
            snapshot = {k: v for k, v in payload.items() if k != "ts"}
            if snapshot != last_snapshot:
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_snapshot = snapshot
            await asyncio.sleep(0.15)
    except asyncio.CancelledError:
        pass


# ─── 实时监控 SSE ──────────────────────────────────────────────────────────
@router.get("/osc_stream")
async def osc_stream():
    """SSE 实时推送 OSC 信号数值、映射结果、消息历史"""
    return StreamingResponse(
        _osc_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _log_signal_task_error(task: asyncio.Task):
    """信号输出任务异常退出时记录日志。

    这个 task 由 asyncio.gather 包裹且无人 await，异常只会在 GC 时留下一句
    'Task exception was never retrieved'，表现为「界面显示已连接、设备毫无反应」。
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logging.exception("信号输出任务异常退出，设备将停止输出", exc_info=exc)


async def start_signal_output():
    """启动信号输出任务（设备连接后调用）"""
    global _signal_task
    await asyncio.gather(start_channel_a(), start_channel_b())


async def start_channel_a():
    # 初始强度 0：连接后不立即输出，等待首个 OSC 信号再由 handler 驱动强度。
    await ci.signal(
        power=0,
        pattern_name=settings.coyote_pattern_a,
        duration=100000000,
        channel="a",
    )


async def start_channel_b():
    # 初始强度 0：连接后不立即输出，等待首个 OSC 信号再由 handler 驱动强度。
    await ci.signal(
        power=0,
        pattern_name=settings.coyote_pattern_b,
        duration=100000000,
        channel="b",
    )


# ─── API 端点 ─────────────────────────────────────────────────────────────
class StartRequest(BaseModel):
    uid: str


@router.post("/start")
async def start_coyote(req: StartRequest):
    """连接 Coyote 设备并启动信号输出。OSC 监听已独立运行，无需在此启动。"""
    global ci, _signal_task, _connect_task, _connect_cancel_event
    if ci is not None and ci.is_connected:
        return {"msg": "already started"}
    if _connect_task is not None and not _connect_task.done():
        raise HTTPException(status_code=409, detail="设备正在连接")

    settings.coyote_uid = req.uid
    # 配置写不进去（exe 放在只读目录）不能把连接流程一起打断，只记一条日志
    if not settings.dump():
        logging.warning("Coyote UID 未能写入 settings.yaml，本次连接不受影响")
    ci = CoyoteInterface(
        device_uid=settings.coyote_uid,
        power_multiplier=settings.coyote_multiplier,
        safe_mode=settings.coyote_safe_mode,
    )
    _connect_cancel_event = asyncio.Event()
    _connect_task = asyncio.create_task(_connect_device(_connect_cancel_event))
    try:
        await _connect_task
    except asyncio.CancelledError:
        raise HTTPException(status_code=409, detail="连接已取消")
    except Exception as e:
        # 把 bleak 的原始异常透给前端。否则 FastAPI 只会返回一句
        # "Internal Server Error"，用户看不出是设备没开、在配对模式还是扫描不到。
        logging.exception("连接 Coyote 失败")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or "连接失败",
        )
    finally:
        _connect_task = None
        _connect_cancel_event = None

    # 只启动信号输出，OSC 监听已在应用启动时独立运行
    _signal_task = asyncio.create_task(start_signal_output())
    _signal_task.add_done_callback(_log_signal_task_error)
    return {"msg": "starting"}


async def _connect_device(cancel_event: asyncio.Event):
    """执行可取消的扫描/连接流程，避免前端超时后后台继续连接。"""
    if ci.device is None:
        await _run_cancelable(ci.search_for_device(), cancel_event)
    retries = max(1, settings.coyote_connect_retries)
    await _run_cancelable(ci.connect(retries=retries), cancel_event)


async def _run_cancelable(awaitable, cancel_event: asyncio.Event):
    operation = asyncio.create_task(awaitable)
    cancellation = asyncio.create_task(cancel_event.wait())
    done, pending = await asyncio.wait(
        {operation, cancellation}, return_when=asyncio.FIRST_COMPLETED
    )
    if cancellation in done and cancel_event.is_set():
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        if ci is not None and ci.is_connected:
            await ci.disconnect()
        raise asyncio.CancelledError
    cancellation.cancel()
    await asyncio.gather(cancellation, return_exceptions=True)
    return await operation


@router.get("/stop")
async def stop_coyote():
    """停止设备并断开蓝牙。OSC 监听保持运行，不影响后续重连。"""
    global transport, _signal_task, _connect_cancel_event, _connect_task
    if _connect_task is not None and not _connect_task.done():
        if _connect_cancel_event is not None:
            _connect_cancel_event.set()
        await asyncio.gather(_connect_task, return_exceptions=True)
        _connect_task = None
        _connect_cancel_event = None
        return {"msg": "stopping"}
    if ci is None or not ci.is_connected:
        return {"msg": "not started"}
    if _signal_task is not None:
        _signal_task.cancel()
        _signal_task = None
    await ci.stop()
    await ci.disconnect()
    # 不关闭 OSC transport，保持监听
    return {"msg": "stopping"}


class UpdatePowerRequest(BaseModel):
    pow_a: int
    pow_b: int


@router.post("/max_power")
async def update_max_power(req: UpdatePowerRequest):
    """设置 A/B 通道最大强度。安全模式下上限强制 100。未连接设备时仅持久化配置。"""
    try:
        safe_limit = 100 if settings.coyote_safe_mode else 200
        pow_a = max(0, min(req.pow_a, safe_limit))
        pow_b = max(0, min(req.pow_b, safe_limit))
        if ci is not None and ci.is_connected:
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
        else:
            settings.coyote_max_power_a = pow_a
            settings.coyote_max_power_b = pow_b
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
            # Immediately apply the safety cap to the live device output.
            # Waiting for the next OSC packet would leave the previous power
            # level active after the UI already reports safe mode enabled.
            if ci is not None and ci.is_connected:
                await ci.set_pwm(
                    min(ci.pow_a, 100),
                    min(ci.pow_b, 100),
                )
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


def _validate_osc_address(name: str, addr: str) -> None:
    """OSC 地址校验。

    允许留空（表示不绑定该通道），但非空时必须是 `/xxx` 形式。
    以前不校验：填了 `EarLDis`（漏了开头的 `/`）也会返回「保存成功」，
    dispatcher 永远匹配不到，表现为「设置保存了但设备毫无反应」。
    """
    addr = (addr or "").strip()
    if addr and not addr.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{name} 通道 OSC 地址必须以 / 开头（例如 /avatar/parameters/EarLDis），当前为「{addr}」。",
        )


@router.post("/osc_addr")
async def update_osc_addr(req: UpdateOscAddrRequest):
    """热更新 OSC 地址。无需断开设备，直接更新 OSC 分发映射。"""
    try:
        _validate_osc_address("A", req.addr_a)
        _validate_osc_address("B", req.addr_b)
        settings.coyote_addr_a = (req.addr_a or "").strip()
        settings.coyote_addr_b = (req.addr_b or "").strip()
        settings.dump()
        # 更新 OSC 分发映射（监听地址不变时不会重建 socket）
        await serve_osc()
        return {"msg": "success"}
    except HTTPException:
        raise
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
    """获取 patterns 列表。从磁盘加载，无需设备已连接。"""
    try:
        return {"patterns": list(_get_patterns().keys())}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/patterns/detail")
async def get_patterns_detail():
    """返回所有 patterns 的详细波形数据。无需设备已连接。"""
    try:
        return {"patterns": _get_patterns()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


class UpdatePatternRequest(BaseModel):
    pattern_a: str
    pattern_b: str


@router.post("/pattern")
async def update_pattern(req: UpdatePatternRequest):
    """设置 A/B 通道 pattern。未连接设备时仅持久化配置。

    以前对不存在的波形名直接忽略、仍然返回 success —— 用户看到「保存成功」
    但配置没变（假成功）。这里改为明确拒绝。
    """
    try:
        patterns = _get_patterns()
        unknown = [
            name for name in (req.pattern_a, req.pattern_b)
            if name not in patterns
        ]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知波形：{', '.join(sorted(set(unknown)))}",
            )
        settings.coyote_pattern_a = req.pattern_a
        settings.coyote_pattern_b = req.pattern_b
        if ci is not None:
            ci.pattern_name_a = req.pattern_a
            ci.pattern_name_b = req.pattern_b
        settings.dump()
        return {"msg": "success"}
    except HTTPException:
        raise
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
    """获取设备连接状态。

    与 /aggregate_status 行为保持一致：蓝牙链路已断但 is_connected 尚未复位时，
    读电量会抛异常。以前这里直接冒泡成 500，而前端每 3 秒轮询一次 /status，
    连续 3 次失败就弹「无法连接到服务器」，界面却仍停在「已连接 / 电量 N%」，
    用户完全看不出其实是设备掉线了。这里只把电量归零，状态照常返回。
    """
    try:
        if ci and ci.is_connected:
            try:
                battery = await ci.get_battery_level()
            except Exception:
                logging.warning("读取电量失败，本次按 0 处理", exc_info=True)
                battery = 0
            return {
                "is_connected": ci.is_connected,
                "battery_level": battery,
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
                battery = await ci.get_battery_level()
            except Exception:
                pass
        return {
            # 设备状态
            "device_connected": device_connected,
            "battery_level": battery,
            "uid": settings.coyote_uid if device_connected else "",
            # OSC 状态
            "osc_running": transport is not None,
            "osc_error": osc_last_error,
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
            "multiplier": settings.coyote_multiplier,
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
