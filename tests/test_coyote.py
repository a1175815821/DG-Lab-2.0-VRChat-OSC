"""Coyote 后端核心逻辑的单元测试。

覆盖：
- map_signal / get_raw_avg / _window_size 的信号映射与边界
- /api/coyote/max_power 的非负钳制
- signal() / is_running() 在 BLE 断开时的 fail-safe 行为

运行：py -m unittest tests.test_coyote -v
"""

import asyncio
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.coyote as coyote
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

    async def read_gatt_char(self, *args, **kwargs):
        if self.read_raises:
            raise ConnectionError("read boom")
        return b"\x00\x00\x00"

    async def write_gatt_char(self, *args, **kwargs):
        if self.write_raises:
            raise ConnectionError("write boom")
        return None


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


if __name__ == "__main__":
    unittest.main()
