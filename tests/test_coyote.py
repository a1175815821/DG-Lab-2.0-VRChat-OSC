"""Coyote 后端核心逻辑的单元测试。

覆盖：
- map_signal / get_raw_avg / _window_size 的信号映射与边界
- /api/coyote/max_power 的非负钳制
- signal() / is_running() 在 BLE 断开时的 fail-safe 行为
- 波形状态解包（含 default 波形与脏数据兜底）
- settings.yaml 损坏/缺失时的启动兜底
- /avatar/change 的跨模块可见性
- OSC handler 的 start_limit 死区
- SSE 事件流的去重

运行：py -m unittest tests.test_coyote -v
"""

import asyncio
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.coyote as coyote
import settings as settings_module
import toys.estim.estim as estimator
from settings import Settings, settings
from toys.estim.coyote.dg_interface import CoyoteInterface


class TestSignalMapping(unittest.TestCase):
    def test_map_signal_below_start_limit_is_zero(self):
        self.assertEqual(coyote.map_signal(0.0), 0.0)
        self.assertEqual(coyote.map_signal(0.01), 0.0)

    def test_map_signal_min_power_plateau(self):
        # [start_limit, min_limit) 之间输出 min_power
        self.assertEqual(coyote.map_signal(settings.start_limit), settings.min_power)
        self.assertEqual(coyote.map_signal(0.1), settings.min_power)

    def test_map_signal_full_at_max_limit(self):
        self.assertEqual(coyote.map_signal(settings.max_limit), 1.0)
        self.assertEqual(coyote.map_signal(1.0), 1.0)

    def test_map_signal_linear_interpolation(self):
        m = coyote.map_signal((settings.min_limit + settings.max_limit) / 2)
        self.assertGreater(m, settings.min_power)
        self.assertLess(m, 1.0)

    def test_map_signal_no_div_zero_when_limits_equal(self):
        old_min, old_max = settings.min_limit, settings.max_limit
        try:
            settings.min_limit = settings.max_limit = 0.5
            self.assertEqual(coyote.map_signal(0.5), 1.0)
        finally:
            settings.min_limit, settings.max_limit = old_min, old_max

    def test_get_raw_avg(self):
        self.assertAlmostEqual(coyote.get_raw_avg([0.1, 0.3, 0.5]), 0.3)
        self.assertEqual(coyote.get_raw_avg([]), 0.0)

    def test_window_size_guard(self):
        old = settings.window_size
        try:
            settings.window_size = 0
            self.assertEqual(coyote._window_size(), 0.1)
            settings.window_size = -3
            self.assertEqual(coyote._window_size(), 0.1)
            settings.window_size = 0.2
            self.assertEqual(coyote._window_size(), 0.2)
        finally:
            settings.window_size = old


class TestPatternStates(unittest.TestCase):
    """波形状态解包。

    回归背景：patterns["default"] 曾是「变体列表」（三层嵌套），
    signal() 里的 `ax, ay, az = state` 会抛 ValueError，
    表现为选了「默认」波形后设备完全无输出、界面却显示已连接。
    """

    def setUp(self):
        self.ci = CoyoteInterface(device_uid="", power_multiplier=1.0, safe_mode=True)

    def test_default_pattern_is_flat_state_list(self):
        states = self.ci.patterns["default"]
        self.assertTrue(states, "default 波形不应为空")
        for s in states:
            self.assertIsInstance(s, list)
            self.assertEqual(len(s), 3)

    def test_every_pattern_can_be_unpacked(self):
        for name in self.ci.patterns:
            for state in self.ci._resolve_states(name):
                ax, ay, az = state  # 不抛异常即通过

    def test_resolve_states_flattens_legacy_variants(self):
        self.ci.patterns["legacy"] = [[[10, 90, 10]], [[5, 135, 20], [1, 9, 20]]]
        self.assertEqual(
            self.ci._resolve_states("legacy"),
            [[10, 90, 10], [5, 135, 20], [1, 9, 20]],
        )

    def test_resolve_states_drops_malformed_entries(self):
        self.ci.patterns["bad"] = [[1, 2, 3], "junk", [4, 5]]
        self.assertEqual(self.ci._resolve_states("bad"), [[1, 2, 3]])

    def test_resolve_states_unknown_pattern_is_empty(self):
        self.assertEqual(self.ci._resolve_states("does_not_exist"), [])


class TestSettingsResilience(unittest.TestCase):
    """settings.yaml 损坏 / 缺失时不能让程序起不来。

    Settings.load() 在模块级执行，一旦抛异常就是「双击 exe 无响应」，
    而用户又是被 README 引导去手改这个文件的。
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_user_dir = settings_module.USER_DATA_DIR
        self._old_base_dir = settings_module.BASE_DIR
        settings_module.USER_DATA_DIR = self.tmp
        settings_module.BASE_DIR = self.tmp  # 同时拿掉内置副本，走最坏路径

    def tearDown(self):
        settings_module.USER_DATA_DIR = self._old_user_dir
        settings_module.BASE_DIR = self._old_base_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, content):
        with open(os.path.join(self.tmp, "settings.yaml"), "w", encoding="utf-8") as f:
            f.write(content)

    def _assert_defaults(self, loaded):
        self.assertEqual(loaded.coyote_max_power_a, Settings().coyote_max_power_a)
        self.assertEqual(loaded.coyote_safe_mode, Settings().coyote_safe_mode)

    def test_missing_file_falls_back_to_defaults(self):
        self._assert_defaults(Settings.load())

    def test_empty_file_falls_back_to_defaults(self):
        self._write("")
        self._assert_defaults(Settings.load())

    def test_scalar_root_falls_back_to_defaults(self):
        self._write("just_a_string")
        self._assert_defaults(Settings.load())

    def test_list_root_falls_back_to_defaults(self):
        self._write("- a\n- b\n")
        self._assert_defaults(Settings.load())

    def test_broken_yaml_falls_back_and_is_backed_up(self):
        self._write("coyote_max_power_a: [1,2\n")
        self._assert_defaults(Settings.load())
        self.assertTrue(
            any(f.endswith(".bak") for f in os.listdir(self.tmp)),
            "损坏的配置应被备份，便于用户找回",
        )

    def test_wrong_field_type_falls_back_to_defaults(self):
        self._write("coyote_max_power_a: not_a_number\n")
        self._assert_defaults(Settings.load())

    def test_valid_file_is_loaded(self):
        self._write("coyote_max_power_a: 77\ncoyote_safe_mode: true\n")
        loaded = Settings.load()
        self.assertEqual(loaded.coyote_max_power_a, 77)
        self.assertTrue(loaded.coyote_safe_mode)

    def test_unknown_keys_are_ignored(self):
        # 历史版本残留字段（如 warn_on_stack_dump_sound）不应导致加载失败
        self._write("warn_on_stack_dump_sound: true\ncoyote_max_power_a: 88\n")
        self.assertEqual(Settings.load().coyote_max_power_a, 88)


class TestAvatarTracking(unittest.TestCase):
    """回归：/avatar/change 记录的值必须对 vrc_osc 路由可见。

    值绑定（`from routers.coyote import current_vrc_avatar_id`）拿到的是导入
    时的快照，永远读到 None，「当前 Avatar」会退化成按文件 mtime 猜。
    """

    def test_avatar_change_is_visible_to_vrc_router(self):
        import routers.vrc_osc as vrc_osc

        old = coyote.current_vrc_avatar_id
        try:
            coyote.avatar_change_handler("/avatar/change", None, "avtr_test123")
            self.assertEqual(
                vrc_osc.coyote_router.current_vrc_avatar_id,
                "avtr_test123",
            )
        finally:
            coyote.current_vrc_avatar_id = old


class TestStartLimitDeadZone(unittest.TestCase):
    """回归：断电判断必须拿原始信号与 start_limit 比较。

    拿映射后的功率比例 s 去比原始信号阈值，一旦 min_power < start_limit，
    整段 [start_limit, min_limit) 都会被误判成断电，设备毫无输出。
    """

    def _drive_handler(self, raw):
        """喂一个 raw 信号走完窗口聚合，返回被 mock 的 set_pwm。"""
        fake = type("FakeCoyote", (), {
            "is_connected": True,
            "pow_a": 0,
            "pow_b": 0,
            "set_pwm": unittest.mock.AsyncMock(),
            "safe_mode": True,
        })()

        async def scenario():
            old_ci = coyote.ci
            old_min_power = settings.min_power
            old_max_a = settings.coyote_max_power_a
            old_multiplier = settings.coyote_multiplier
            old_queue = coyote.param_queue_a
            old_last = coyote.last_time_a
            try:
                settings.min_power = 0.02          # 故意小于 start_limit(0.05)
                settings.coyote_max_power_a = 50
                settings.coyote_multiplier = 1.0
                settings.can_update_power = True
                coyote.ci = fake
                coyote.param_queue_a = [raw]
                coyote.last_time_a = time.time() - 1.0   # 强制跨过窗口
                coyote.coyote_handler_a("/avatar/parameters/EarLDis", "A", raw)
                await asyncio.sleep(0.02)          # 让 ensure_future 的 task 落地
                return fake.set_pwm
            finally:
                coyote.ci = old_ci
                settings.min_power = old_min_power
                settings.coyote_max_power_a = old_max_a
                settings.coyote_multiplier = old_multiplier
                coyote.param_queue_a = old_queue
                coyote.last_time_a = old_last

        return asyncio.run(scenario())

    def test_signal_above_start_limit_is_not_muted(self):
        set_pwm = self._drive_handler(0.10)   # 落在 [start_limit, min_limit)
        set_pwm.assert_awaited_once()
        self.assertGreater(
            set_pwm.await_args.args[0], 0,
            "信号已越过 start_limit，不应被判为断电",
        )

    def test_signal_below_start_limit_is_muted(self):
        set_pwm = self._drive_handler(0.01)
        set_pwm.assert_awaited_once_with(0, -1)


class TestOscStreamDedup(unittest.TestCase):
    """回归：SSE 去重不能因为 ts 字段而失效。"""

    def test_unchanged_payload_is_not_resent(self):
        async def scenario():
            fixed = {"ts": 1.0, "a": {"raw": 0.5, "avg": 0.5, "mapped": 0.7, "active": True},
                     "b": {"raw": 0.0, "avg": 0.0, "mapped": 0.0, "active": False},
                     "history": [], "current_avatar_id": None}
            with patch.object(coyote, "_build_monitor_payload", return_value=dict(fixed)):
                gen = coyote._osc_event_generator()
                first = await gen.__anext__()
                pending = asyncio.create_task(gen.__anext__())
                await asyncio.sleep(0.45)   # 至少跨过两轮 0.15s 循环
                still_pending = not pending.done()
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
                return first, still_pending

        first, still_pending = asyncio.run(scenario())
        self.assertTrue(first.startswith("data: "))
        self.assertTrue(still_pending, "payload 未变化时应跳过推送")


class TestConnectionCancellation(unittest.TestCase):
    def test_run_cancelable_cancels_inflight_operation(self):
        async def scenario():
            cancel_event = asyncio.Event()
            started = asyncio.Event()
            finished = False

            async def operation():
                nonlocal finished
                started.set()
                await asyncio.sleep(10)
                finished = True

            task = asyncio.create_task(coyote._run_cancelable(operation(), cancel_event))
            await started.wait()
            cancel_event.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertFalse(finished)

        asyncio.run(scenario())


class TestSafeMode(unittest.TestCase):
    def test_safe_mode_caps_live_output(self):
        async def scenario():
            fake = type("FakeCoyote", (), {
                "is_connected": True,
                "pow_a": 150,
                "pow_b": 120,
                "set_pwm": unittest.mock.AsyncMock(),
                "safe_mode": False,
            })()
            old_ci = coyote.ci
            old_safe = settings.coyote_safe_mode
            try:
                coyote.ci = fake
                settings.coyote_safe_mode = False
                with patch.object(Settings, "dump"):
                    result = await coyote.update_safe_mode(
                        coyote.UpdateSafeModeRequest(safe_mode=True)
                    )
                self.assertEqual(result["safe_mode"], True)
                fake.set_pwm.assert_awaited_once_with(100, 100)
            finally:
                coyote.ci = old_ci
                settings.coyote_safe_mode = old_safe

        asyncio.run(scenario())


class TestMaxPowerClamp(unittest.TestCase):
    def test_max_power_clamped_and_not_negative(self):
        app = FastAPI()
        app.include_router(coyote.router)
        client = TestClient(app)

        old_safe = settings.coyote_safe_mode
        old_a, old_b = settings.coyote_max_power_a, settings.coyote_max_power_b
        try:
            settings.coyote_safe_mode = True
            # 阻止 dump() 写回真实 settings.yaml（pydantic 实例禁止 setattr，须 patch 类方法）
            with patch.object(Settings, "dump"):
                r = client.post(
                    "/api/coyote/max_power", json={"pow_a": -50, "pow_b": 300}
                )
        finally:
            settings.coyote_safe_mode = old_safe
            settings.coyote_max_power_a = old_a
            settings.coyote_max_power_b = old_b

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["max_power_a"], 0)
        self.assertEqual(r.json()["max_power_b"], 100)  # 安全模式上限 100


class _FakeDevice:
    def __init__(self, read_raises=False, write_raises=False):
        self.read_raises = read_raises
        self.write_raises = write_raises
        self.writes = []

    async def read_gatt_char(self, *args, **kwargs):
        if self.read_raises:
            raise ConnectionError("read boom")
        return b"\x00\x00\x00"

    async def write_gatt_char(self, *args, **kwargs):
        if self.write_raises:
            raise ConnectionError("write boom")
        self.writes.append(args[0] if args else None)
        return None


class TestDefaultPatternOutput(unittest.TestCase):
    """端到端：选中 default 波形后必须真的往设备写数据。

    修复前 signal() 会在解包时抛 ValueError，整个信号任务静默死亡，
    界面仍显示「已连接」，但设备一条数据都收不到。
    """

    def test_signal_with_default_pattern_writes_to_device(self):
        ci = CoyoteInterface(device_uid="", power_multiplier=1.0, safe_mode=True)
        ci.patterns = {"default": [[10, 90, 10], [5, 135, 20], [1, 9, 20]]}
        ci.pattern_name_a = "default"
        ci.pattern_name_b = "default"
        ci._pwm_a34 = type("Char", (), {"uuid": "a34"})()
        ci._pwm_b34 = type("Char", (), {"uuid": "b34"})()
        ci._pwm_ab2 = type("Char", (), {"uuid": "ab2"})()
        device = _FakeDevice()
        ci.device = device
        ci.is_connected = True
        ci.pow_a = 0
        ci.pow_b = 0

        asyncio.run(ci.signal(power=0, pattern_name="default", duration=600, channel="a"))

        self.assertGreater(
            len(device.writes), 0,
            "default 波形应正常向设备写入，而不是让信号任务静默崩溃",
        )


class TestDisconnectHandling(unittest.TestCase):
    def _make_ci(self):
        ci = CoyoteInterface(device_uid="", power_multiplier=1.0, safe_mode=True)
        ci.patterns = {"test": [[10, 90, 10]]}
        ci.pattern_name_a = "test"
        ci.pattern_name_b = "test"
        ci._pwm_a34 = object()
        ci._pwm_b34 = object()
        ci.pow_a = 0
        ci.pow_b = 0
        return ci

    def test_is_running_read_failure_marks_disconnected(self):
        ci = self._make_ci()
        ci.device = _FakeDevice(read_raises=True)
        ci.is_connected = True

        result = asyncio.run(ci.is_running())

        self.assertFalse(result)
        self.assertFalse(ci.is_connected)
        self.assertTrue(ci.stop_signal)

    def test_is_running_ok_stays_connected(self):
        ci = self._make_ci()
        ci.device = _FakeDevice(read_raises=False)
        ci.is_connected = True

        result = asyncio.run(ci.is_running())

        self.assertTrue(result)
        self.assertTrue(ci.is_connected)

    def test_signal_write_failure_marks_disconnected(self):
        ci = self._make_ci()
        ci.device = _FakeDevice(write_raises=True)
        ci.is_connected = True

        asyncio.run(ci.signal(power=0, pattern_name="test", duration=500, channel="a"))

        self.assertFalse(ci.is_connected)
        self.assertTrue(ci.stop_signal)


class TestStatusEndpointResilience(unittest.TestCase):
    """回归 B22：蓝牙链路已断但 is_connected 还没复位时，/status 不能 500。

    前端每 3 秒轮询 /status，连续 3 次失败就弹「无法连接到服务器」，
    而「已连接 / 电量 N%」还停在旧值上 —— 用户看不出其实是设备掉线了。
    """

    def _make_ci(self, battery_raises):
        class FakeCoyote:
            is_connected = True

            def __init__(self):
                self.pow_a = 10
                self.pow_b = 10

            async def get_battery_level(self):
                if battery_raises:
                    raise RuntimeError("BLE gone")
                return 80

        return FakeCoyote()

    def test_battery_failure_does_not_500(self):
        app = FastAPI()
        app.include_router(coyote.router)
        client = TestClient(app)
        old = coyote.ci
        try:
            coyote.ci = self._make_ci(battery_raises=True)
            r = client.get("/api/coyote/status")
            self.assertEqual(r.status_code, 200, "读电量失败不应让整个 /status 变成 500")
            self.assertEqual(r.json()["battery_level"], 0)
        finally:
            coyote.ci = old

    def test_healthy_device_still_reports_battery(self):
        app = FastAPI()
        app.include_router(coyote.router)
        client = TestClient(app)
        old = coyote.ci
        try:
            coyote.ci = self._make_ci(battery_raises=False)
            r = client.get("/api/coyote/status")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["battery_level"], 80)
        finally:
            coyote.ci = old


class TestOscServeResilience(unittest.TestCase):
    """回归 B26/B33：OSC 热重启失败时不能让监听彻底停摆。"""

    def test_hot_restart_failure_keeps_old_transport(self):
        async def scenario():
            old_transport = coyote.transport
            old_proto = coyote._osc_protocol
            old_bind = coyote._last_osc_bind
            old_err = coyote.osc_last_error
            old_host = settings.vrc_host
            old_port = settings.vrc_osc_port

            class FakeTransport:
                def __init__(self, key):
                    self.key = key
                    self.closed = False

                def close(self):
                    self.closed = True

            class FakeProto:
                def __init__(self):
                    self.dispatcher = None

            async def fake_bind(host, port, dispatcher):
                if port == 59999:  # 故意让新地址绑不上
                    raise OSError("bind failed")
                return FakeTransport((host, port)), FakeProto()

            try:
                coyote.transport = None
                coyote._osc_protocol = None
                coyote._last_osc_bind = None
                with patch.object(coyote, "_bind_osc", side_effect=fake_bind):
                    await coyote.serve_osc()
                self.assertIsNotNone(coyote.transport, "首次启动应成功")
                old = coyote.transport

                settings.vrc_osc_port = 59999
                with patch.object(coyote, "_bind_osc", side_effect=fake_bind):
                    with self.assertRaises(OSError):
                        await coyote.serve_osc()

                self.assertIs(
                    coyote.transport, old,
                    "新地址绑不上时必须保留旧监听，否则 OSC 直接停摆",
                )
                self.assertFalse(old.closed, "旧监听不应被关闭")
                self.assertIn("保留原监听", coyote.osc_last_error or "")
            finally:
                settings.vrc_host = old_host
                settings.vrc_osc_port = old_port
                coyote.transport = old_transport
                coyote._osc_protocol = old_proto
                coyote._last_osc_bind = old_bind
                coyote.osc_last_error = old_err

        asyncio.run(scenario())

    def test_same_host_port_does_not_rebind_socket(self):
        """回归 B33：只改 OSC 地址时必须原地换 dispatcher，不能重建 socket。

        以前 serve_osc() 无条件 close 旧 transport 再 bind 同一个端口，
        Windows 上端口尚未释放 → WinError 10048，接口 500 且 OSC 停摆。
        实测连续保存 4 次地址，第 1、3 次失败。
        """
        async def scenario():
            old_transport = coyote.transport
            old_proto = coyote._osc_protocol
            old_bind = coyote._last_osc_bind
            old_err = coyote.osc_last_error
            old_addr_a = settings.coyote_addr_a
            old_addr_b = settings.coyote_addr_b
            calls = []

            class FakeProto:
                def __init__(self):
                    self.dispatcher = None

            async def fake_bind(host, port, dispatcher):
                calls.append((host, port))
                return object(), FakeProto()

            try:
                coyote.transport = None
                coyote._osc_protocol = None
                coyote._last_osc_bind = None
                with patch.object(coyote, "_bind_osc", side_effect=fake_bind):
                    await coyote.serve_osc()
                    self.assertEqual(len(calls), 1)

                    settings.coyote_addr_a = "/avatar/parameters/OtherL"
                    settings.coyote_addr_b = "/avatar/parameters/OtherR"
                    await coyote.serve_osc()
                    await coyote.serve_osc()

                self.assertEqual(
                    len(calls), 1,
                    "监听地址未变时不应重新 bind（否则 Windows 上必然 10048）",
                )
                self.assertIsNotNone(coyote._osc_protocol.dispatcher)
                self.assertIsNone(coyote.osc_last_error)
            finally:
                settings.coyote_addr_a = old_addr_a
                settings.coyote_addr_b = old_addr_b
                coyote.transport = old_transport
                coyote._osc_protocol = old_proto
                coyote._last_osc_bind = old_bind
                coyote.osc_last_error = old_err

        asyncio.run(scenario())

    def test_bind_error_is_recorded(self):
        """构造/绑定阶段的失败也要写进 osc_last_error，否则界面只有一句「未启动」。"""
        async def scenario():
            old_transport = coyote.transport
            old_proto = coyote._osc_protocol
            old_bind = coyote._last_osc_bind
            old_err = coyote.osc_last_error
            try:
                coyote.transport = None
                coyote._osc_protocol = None
                coyote._last_osc_bind = None  # 首次启动，无旧监听可保留
                async def always_fail(host, port, dispatcher):
                    raise OSError("address invalid")
                with patch.object(coyote, "_bind_osc", side_effect=always_fail):
                    with self.assertRaises(OSError):
                        await coyote.serve_osc()
                self.assertIsNone(coyote.transport)
                self.assertTrue(coyote.osc_last_error, "失败原因必须留给前端展示")
                self.assertIn("59998", coyote.osc_last_error)
            finally:
                coyote.transport = old_transport
                coyote._osc_protocol = old_proto
                coyote._last_osc_bind = old_bind
                coyote.osc_last_error = old_err

        old_port = settings.vrc_osc_port
        settings.vrc_osc_port = 59998
        try:
            asyncio.run(scenario())
        finally:
            settings.vrc_osc_port = old_port


class TestSettingsDumpResilience(unittest.TestCase):
    """回归 B29：配置写不进去不能把整个接口拖成 500。"""

    def test_dump_returns_false_instead_of_raising(self):
        s = Settings()
        with patch("builtins.open", side_effect=OSError("read-only fs")):
            self.assertFalse(s.dump(), "写入失败应返回 False 而不是抛异常")

    def test_dump_success_returns_true(self):
        tmp = tempfile.mkdtemp()
        try:
            s = Settings(coyote_max_power_a=77)
            with patch.object(settings_module, "USER_DATA_DIR", tmp):
                self.assertTrue(s.dump())
            with open(os.path.join(tmp, "settings.yaml"), "r", encoding="utf-8") as f:
                self.assertIn("coyote_max_power_a: 77", f.read())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_dump_never_persists_power_lock_as_false(self):
        s = Settings()
        s.can_update_power = False
        tmp = tempfile.mkdtemp()
        try:
            with patch.object(settings_module, "USER_DATA_DIR", tmp):
                s.dump()
            self.assertTrue(s.can_update_power, "运行时锁不应被持久化成 false")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestStopSignalInitialized(unittest.TestCase):
    """回归 B30：stop_signal 必须在构造时就存在。"""

    def test_stop_signal_exists_after_init(self):
        ci = CoyoteInterface(device_uid="", power_multiplier=1.0, safe_mode=True)
        self.assertIs(ci.stop_signal, False)


class TestNonNumericOscSignal(unittest.TestCase):
    """回归 B33-1：非数值 OSC 参数不能污染 latest_raw_* / 不能抛异常。

    实测：向 EarLDis 发一个字符串，`round(raw, 4)` 抛 TypeError；
    更严重的是 latest_raw_a 已被赋成字符串，概览页 `value.toFixed(3)`
    直接 TypeError，整个界面被 ErrorBoundary 接管（cards: 0）。
    """

    def setUp(self):
        self._old_raw = coyote.latest_raw_a
        self._old_hist = list(coyote.msg_history)
        self._old_cur = coyote.cur_time_a

    def tearDown(self):
        coyote.latest_raw_a = self._old_raw
        coyote.msg_history.clear()
        coyote.msg_history.extend(self._old_hist)
        coyote.cur_time_a = self._old_cur

    def test_string_signal_is_ignored(self):
        coyote.latest_raw_a = 0.25
        before = len(coyote.msg_history)
        coyote.coyote_handler_a("/avatar/parameters/EarLDis", "A", "hello")
        self.assertEqual(coyote.latest_raw_a, 0.25, "非法值不得污染 latest_raw_a")
        self.assertEqual(len(coyote.msg_history), before, "非法值不应写入历史")

    def test_invalid_signal_still_marks_activity(self):
        """值非法也要标记「收到过消息」：界面据此显示 VRChat 已连接，
        用户才知道 OSC 通路是通的、只是地址绑错了类型。"""
        coyote.cur_time_a = None
        coyote.coyote_handler_a("/avatar/parameters/EarLDis", "A", "hello")
        self.assertIsNotNone(coyote.cur_time_a)
        self.assertLess(abs(time.time() - coyote.cur_time_a), 1.0)

    def test_bool_and_int_are_accepted(self):
        coyote.coyote_handler_a("/avatar/parameters/EarLDis", "A", True)
        self.assertEqual(coyote.latest_raw_a, 1.0)
        coyote.coyote_handler_a("/avatar/parameters/EarLDis", "A", 0)
        self.assertEqual(coyote.latest_raw_a, 0.0)

    def test_coerce_signal(self):
        self.assertEqual(coyote._coerce_signal(0.5), 0.5)
        self.assertEqual(coyote._coerce_signal(3), 3.0)
        self.assertEqual(coyote._coerce_signal(False), 0.0)
        self.assertIsNone(coyote._coerce_signal("x"))
        self.assertIsNone(coyote._coerce_signal(None))
        self.assertIsNone(coyote._coerce_signal([1]))


class TestSignalLoopGuard(unittest.TestCase):
    """回归 B33-2：未知/损坏波形不能让 signal() 无 await 空转。

    cur_time 以前只在 for 体内赋值，_resolve_states() 返回空列表时
    for 体一次都不执行 → 死循环，整个 asyncio 事件循环被独占、后端卡死。
    """

    def _make_ci(self):
        ci = CoyoteInterface(device_uid="", power_multiplier=1.0, safe_mode=True)
        ci.patterns = {"ok": [[10, 90, 10]]}
        ci.pattern_name_a = "missing"
        ci.pattern_name_b = "missing"
        ci._pwm_a34 = type("C", (), {"uuid": "a"})()
        ci._pwm_b34 = type("C", (), {"uuid": "b"})()
        ci._pwm_ab2 = type("C", (), {"uuid": "ab"})()
        ci.device = _FakeDevice()
        ci.is_connected = True
        ci.pow_a = 0
        ci.pow_b = 0
        return ci

    def _run_with_timeout(self, ci, seconds=3.0):
        import threading

        done = {"ok": False}

        def run():
            asyncio.run(
                ci.signal(power=0, pattern_name="missing", duration=100000, channel="a")
            )
            done["ok"] = True

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout=seconds)
        return done["ok"]

    def test_unknown_pattern_returns_instead_of_spinning(self):
        ci = self._make_ci()
        self.assertTrue(
            self._run_with_timeout(ci),
            "未知波形必须立即返回，而不是无 await 死循环卡死整个事件循环",
        )

    def test_unknown_pattern_does_not_touch_device(self):
        ci = self._make_ci()
        asyncio.run(ci.signal(power=0, pattern_name="missing", duration=100, channel="a"))
        self.assertEqual(ci.device.writes, [], "没有有效波形时不应写蓝牙")

    def test_valid_pattern_still_writes(self):
        ci = self._make_ci()
        ci.pattern_name_a = "ok"
        asyncio.run(ci.signal(power=0, pattern_name="ok", duration=100, channel="a"))
        self.assertGreater(len(ci.device.writes), 0)


class TestPatternValidation(unittest.TestCase):
    """回归 B33-4：未知波形名不能返回「保存成功」。"""

    def test_unknown_pattern_is_rejected(self):
        app = FastAPI()
        app.include_router(coyote.router)
        client = TestClient(app)
        old_a = settings.coyote_pattern_a
        try:
            r = client.post(
                "/api/coyote/pattern", json={"pattern_a": "NOPE", "pattern_b": "vibrator_4"}
            )
            self.assertEqual(r.status_code, 400)
            self.assertIn("NOPE", r.json()["detail"])
            self.assertEqual(settings.coyote_pattern_a, old_a, "非法值不应写入配置")
        finally:
            settings.coyote_pattern_a = old_a

    def test_valid_pattern_is_saved(self):
        app = FastAPI()
        app.include_router(coyote.router)
        client = TestClient(app)
        old_a = settings.coyote_pattern_a
        try:
            with patch.object(Settings, "dump"):
                r = client.post(
                    "/api/coyote/pattern",
                    json={"pattern_a": "vibrator_1", "pattern_b": "vibrator_2"},
                )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(settings.coyote_pattern_a, "vibrator_1")
        finally:
            settings.coyote_pattern_a = old_a


class TestOscAddressValidation(unittest.TestCase):
    """回归 B33-5：漏写前导 / 的地址不能「保存成功」后静默失效。"""

    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(coyote.router)
        self.client = TestClient(self.app)
        self._old_a = settings.coyote_addr_a
        self._old_b = settings.coyote_addr_b

    def tearDown(self):
        settings.coyote_addr_a = self._old_a
        settings.coyote_addr_b = self._old_b

    def test_address_without_leading_slash_is_rejected(self):
        r = self.client.post(
            "/api/coyote/osc_addr", json={"addr_a": "EarLDis", "addr_b": "/ok"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("/", r.json()["detail"])

    def test_empty_address_is_allowed(self):
        # 留空表示不绑定该通道，是合法用法
        with patch.object(Settings, "dump"), patch.object(
            coyote, "serve_osc", new=unittest.mock.AsyncMock()
        ):
            r = self.client.post(
                "/api/coyote/osc_addr", json={"addr_a": "", "addr_b": ""}
            )
        self.assertEqual(r.status_code, 200)


class TestOscServerPortValidation(unittest.TestCase):
    """回归 B33-6：端口越界要在入参层拦掉，而不是走到 bind() 才 500。"""

    def test_out_of_range_port_is_422(self):
        from routers import osc_server

        app = FastAPI()
        app.include_router(osc_server.router)
        client = TestClient(app)
        r = client.post("/api/osc_server/address", json={"host": "127.0.0.1", "port": 70000})
        self.assertEqual(r.status_code, 422)

    def test_empty_host_is_422(self):
        from routers import osc_server

        app = FastAPI()
        app.include_router(osc_server.router)
        client = TestClient(app)
        r = client.post("/api/osc_server/address", json={"host": "", "port": 9001})
        self.assertEqual(r.status_code, 422)


class TestConnectBudget(unittest.TestCase):
    """回归 B33-7：前端连接预算必须覆盖后端最坏耗时。"""

    def test_budget_covers_scan_plus_retries(self):
        s = Settings(coyote_scan_timeout=10, coyote_connect_timeout=40,
                     coyote_connect_retries=3)
        self.assertEqual(s.connect_budget(), 130.0)

    def test_budget_is_robust_to_zero_values(self):
        s = Settings(coyote_scan_timeout=0, coyote_connect_timeout=0,
                     coyote_connect_retries=0)
        self.assertGreater(s.connect_budget(), 0)

    def test_settings_endpoint_exposes_budget(self):
        import main

        client = TestClient(main.app)
        data = client.get("/settings").json()
        self.assertIn("coyote_connect_budget", data)
        self.assertGreater(data["coyote_connect_budget"], 0)


class TestApiFallbackReturnsJson(unittest.TestCase):
    """未命中的 /api/* 必须返回 JSON 而不是 HTML 404；SPA 回退要把 /coyote 映射到 coyote.html。

    这里刻意自己造一份临时的 frontend/out，而不是用真实的构建产物：
    frontend/out 是 .gitignore 的构建输出，CI 上「跑单元测试」排在「构建前端」之前，
    依赖真实产物会让这个用例在 CI 上必然 404 —— 实测就是这么挂的（本地因为
    目录一直在，永远发现不了）。真实产物是否可服务由 CI 的 exe 冒烟测试覆盖。
    """

    def setUp(self):
        import main

        self.main = main
        self.tmp = tempfile.mkdtemp()
        out = os.path.join(self.tmp, "frontend", "out")
        os.makedirs(os.path.join(out, "assets"), exist_ok=True)
        for name in ("index.html", "coyote.html", "404.html"):
            with open(os.path.join(out, name), "w", encoding="utf-8") as f:
                f.write(f"<html><body>{name}</body></html>")
        with open(os.path.join(out, "assets", "logo.svg"), "w", encoding="utf-8") as f:
            f.write("<svg/>")
        self.out = out
        self._old_frontend_dir = main.FRONTEND_DIR
        main.FRONTEND_DIR = out

    def tearDown(self):
        self.main.FRONTEND_DIR = self._old_frontend_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self):
        return TestClient(self.main.app)

    def test_unknown_api_returns_json_detail(self):
        r = self._client().get("/api/coyote/does_not_exist")
        self.assertEqual(r.status_code, 404)
        self.assertIn("detail", r.json())

    def test_spa_fallback_maps_page_to_html(self):
        r = self._client().get("/coyote")
        self.assertEqual(r.status_code, 200)
        self.assertIn("coyote.html", r.text)

    def test_spa_fallback_serves_index_for_root(self):
        r = self._client().get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("index.html", r.text)

    def test_spa_fallback_serves_real_file(self):
        r = self._client().get("/assets/logo.svg")
        self.assertEqual(r.status_code, 200)
        self.assertIn("<svg/>", r.text)

    def test_unknown_path_falls_back_to_404_page(self):
        r = self._client().get("/definitely-not-a-page")
        self.assertEqual(r.status_code, 404)
        self.assertIn("404.html", r.text)

    def test_real_frontend_dir_is_served_when_built(self):
        """前端已构建时（本机 / CI 构建之后），真实产物也要能服务。"""
        real = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "frontend", "out")
        if not os.path.isfile(os.path.join(real, "index.html")):
            self.skipTest("frontend/out 尚未构建")
        self.main.FRONTEND_DIR = real
        try:
            self.assertEqual(self._client().get("/coyote").status_code, 200)
        finally:
            self.main.FRONTEND_DIR = self.out


class TestPatternLoadingResilience(unittest.TestCase):
    """回归：波形数据缺失/损坏不能让后端起不来。

    load_patterns 由 Estim.__init__ 调用，而 CoyoteInterface 是 routers/coyote.py
    模块级构造的 —— 这里抛异常就是整个后端 import 失败，表现为「双击 exe 没有
    任何窗口、38080 无监听」，用户没有任何自助恢复路径。
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_base = estimator.BASE_DIR
        estimator.BASE_DIR = self.tmp

    def tearDown(self):
        estimator.BASE_DIR = self._old_base
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self):
        return estimator.Estim("coyote")

    def test_missing_index_still_boots_with_default(self):
        est = self._make()  # data/estim 完全不存在
        self.assertIn("default", est.patterns)
        self.assertTrue(est.patterns["default"])
        for state in est.patterns["default"]:
            self.assertEqual(len(state), 3)

    def test_broken_index_json_still_boots(self):
        os.makedirs(os.path.join(self.tmp, "data", "estim"), exist_ok=True)
        with open(os.path.join(self.tmp, "data", "estim", "pattern_dict.json"),
                  "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        est = self._make()
        self.assertIn("default", est.patterns)

    def test_non_dict_index_still_boots(self):
        os.makedirs(os.path.join(self.tmp, "data", "estim"), exist_ok=True)
        with open(os.path.join(self.tmp, "data", "estim", "pattern_dict.json"),
                  "w", encoding="utf-8") as f:
            f.write("[1, 2, 3]")
        est = self._make()
        self.assertIn("default", est.patterns)

    def test_missing_pattern_file_is_skipped(self):
        base = os.path.join(self.tmp, "data", "estim")
        os.makedirs(os.path.join(base, "patterns"), exist_ok=True)
        with open(os.path.join(base, "pattern_dict.json"), "w", encoding="utf-8") as f:
            json.dump({"good": ["a.json"], "bad": ["nope.json"]}, f)
        with open(os.path.join(base, "patterns", "a.json"), "w", encoding="utf-8") as f:
            json.dump([[10, 90, 10]], f)

        est = self._make()
        self.assertEqual(est.patterns["good"], [[10, 90, 10]])
        self.assertNotIn("bad", est.patterns, "整份数据都缺失的波形应被移除")
        self.assertIn("default", est.patterns)

    def test_real_data_still_loads(self):
        """真机数据目录（BASE_DIR 指向项目根）必须能正常加载。"""
        estimator.BASE_DIR = self._old_base  # 临时还原，读真实 data/estim
        est = self._make()
        self.assertGreater(len(est.patterns), 10)
        self.assertIn("vibrator_4", est.patterns)
        for name, states in est.patterns.items():
            self.assertTrue(states, f"{name} 不应为空")
            for s in states:
                self.assertEqual(len(s), 3, f"{name} 存在结构异常的状态 {s}")


class TestLocalOpenerBypassesProxy(unittest.TestCase):
    """回归：访问本机回环地址必须绕过系统代理。

    urllib 默认读取系统代理。机器上配了代理且没把 127.0.0.1 列入 bypass 时，
    本机请求会被送到代理（实测返回 502 Bad Gateway）：
    - 健康检查失败 → 窗口白屏；
    - 退出时的优雅停机请求失败 → 设备功率可能不被归零（安全问题）。
    """

    def _serve(self):
        import http.server
        import socketserver

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args):
                pass

        httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd, httpd.server_address[1]

    def test_bogus_proxy_does_not_break_local_request(self):
        """确定性回归：只要代理没把本机地址列入 bypass，本机请求就会被打断。

        本机确实配置了系统代理（getproxies() 返回 http://127.0.0.1:4685），
        是否真正走代理取决于平台 bypass 名单，所以这里用显式代理把失败模式
        固定下来，避免测试结果随机器代理配置漂移。
        """
        import main

        httpd, port = self._serve()
        url = f"http://127.0.0.1:{port}/"
        try:
            bad = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": "http://127.0.0.1:1"})
            )
            with self.assertRaises(Exception):
                with bad.open(url, timeout=3) as r:
                    r.read()

            with main._local_opener().open(url, timeout=3) as r:
                self.assertEqual(r.read(), b"ok")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_wait_for_server_uses_local_opener(self):
        import main

        httpd, port = self._serve()
        try:
            self.assertTrue(
                main._wait_for_server(f"http://127.0.0.1:{port}/", timeout=3.0)
            )
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestConsoleEncodingResilience(unittest.TestCase):
    """回归 B62：控制台编码不支持中文时，错误处理路径不能自己崩掉。

    CI（Windows Server 2025，stdout 是 cp1252）实测：
        UnicodeEncodeError: 'charmap' codec can't encode characters ...
        File "settings.py", line 95, in dump
            print(f"[settings] 写入 settings.yaml 失败（本次修改未持久化）: {e}")
    这些 print 全在错误处理分支里：
    - dump() 里崩 → 本来「持久化失败返回 False」变成抛异常，接口重新变 500；
    - load() 里崩 → 异常从 except 块冒出去 → Settings.load() 失败 →
      模块级构造失败 → 整个后端起不来，恰好把「回落默认配置」的兜底废掉。
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_user_dir = settings_module.USER_DATA_DIR
        self._old_base_dir = settings_module.BASE_DIR
        settings_module.USER_DATA_DIR = self.tmp
        settings_module.BASE_DIR = self.tmp
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        # cp1252 表示不了中文，errors="strict" 才会真的抛异常
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")

    def tearDown(self):
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr
        settings_module.USER_DATA_DIR = self._old_user_dir
        settings_module.BASE_DIR = self._old_base_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dump_returns_false_when_console_cannot_encode(self):
        with patch("builtins.open", side_effect=OSError("read-only fs")):
            self.assertFalse(
                Settings().dump(),
                "写入失败应返回 False，而不是让 print 的编码异常冒出去",
            )

    def test_load_falls_back_when_console_cannot_encode(self):
        with open(os.path.join(self.tmp, "settings.yaml"), "w", encoding="utf-8") as f:
            f.write("coyote_max_power_a: [1,2\n")   # 语法错误，走回退分支
        loaded = Settings.load()
        self.assertEqual(loaded.coyote_max_power_a, Settings().coyote_max_power_a)

    def test_load_handles_scalar_root_when_console_cannot_encode(self):
        with open(os.path.join(self.tmp, "settings.yaml"), "w", encoding="utf-8") as f:
            f.write("just_a_string")
        loaded = Settings.load()
        self.assertEqual(loaded.coyote_max_power_a, Settings().coyote_max_power_a)

    def test_settings_module_has_no_bare_print(self):
        """错误处理路径禁止用 print()：它不可编码时会抛 UnicodeEncodeError。

        这里做源码级守卫，避免以后又被人加回去。
        """
        src = open(settings_module.__file__, encoding="utf-8").read()
        offenders = []
        for i, line in enumerate(src.splitlines(), 1):
            code = line.split("#", 1)[0]          # 注释里提到 print() 不算
            if re.search(r"(?<![\w.])print\s*\(", code):
                offenders.append(f"L{i}: {line.strip()}")
        self.assertEqual(offenders, [], f"settings.py 不应出现 print()：{offenders}")


if __name__ == "__main__":
    unittest.main()
