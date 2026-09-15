import os
import time
import yaml
from pydantic import BaseModel
from common.paths import BASE_DIR, USER_DATA_DIR


class Settings(BaseModel):
    # Set to the Bluetooth UID for your particular Coyote device
    # if `coyote_uid` is empty, the program will try detecting coyote automatically
    coyote_uid: str = ""
    # Multiplier applied to mapped signal: power = min(200, max_power * s * multiplier)
    # Default 1.0 so the UI max-power slider maps 1:1 at full signal.
    coyote_multiplier: float = 1.0
    # Enable or disable safe mode. This caps the max e-stim output of the device. Warning: Don't touch unless you know what you're doing!
    coyote_safe_mode: bool = True
    coyote_max_power_a: int = 50
    coyote_max_power_b: int = 50
    coyote_pattern_a: str = "vibrator_4"
    coyote_pattern_b: str = "vibrator_4"
    # OSC address bind to channel A.
    # The value of this address must be a float number between 0 and 1.
    coyote_addr_a: str = "/avatar/parameters/EarLDis"
    # OSC address bind to channel B.
    # The value of this address must be a float number between 0 and 1.
    coyote_addr_b: str = "/avatar/parameters/EarRDis"
    # bluetooth connection timeout (in seconds) of coyote
    coyote_connect_timeout: int = 40
    # 蓝牙扫描超时（秒）
    coyote_scan_timeout: int = 10
    # 连接失败重试次数
    coyote_connect_retries: int = 3

    # Host ip of VRChat client.
    vrc_host: str = "127.0.0.1"
    # OSC port of VRChat client.
    # If you have no idea what it is, leave it as default.
    vrc_osc_port: int = 9001

    # Window size of the moving average filter (in seconds).
    window_size: float = 0.1

    # When the average value of the signal is below this value, the power will be set to `0`.
    start_limit: float = 0.05
    # When the average value of the signal is below this value, the power will be set to `min_power * COYOTE_MAX_POWER`.
    min_limit: float = 0.2
    # When the average value of the signal is above this value, the power will be set to `1.0 * COYOTE_MAX_POWER`.
    max_limit: float = 0.8
    # The minimum power rate of the e-stim device.
    min_power: float = 0.5

    can_update_power: bool = True

    def connect_budget(self) -> float:
        """蓝牙连接的最坏耗时（秒）：扫描 + 重试次数 × 单次连接超时。

        前端用它做连接倒计时/超时预算。以前前端硬编码 40s，而后端最坏是
        10s 扫描 + 3×40s 重试 = 130s，倒计时先到点就 abort 并调 /stop，
        结果「慢一点的蓝牙永远连不上」。
        """
        return float(
            max(0, self.coyote_scan_timeout)
            + max(1, self.coyote_connect_retries) * max(1, self.coyote_connect_timeout)
        )

    def _as_dict(self) -> dict:
        """兼容 pydantic v1 / v2 的序列化入口。

        本机实际装的是 pydantic v2，`self.dict()` 在 v2 下已弃用
        （requirements.txt 里锁的还是 1.10.7，两边已经不一致）。
        v2 提供 model_dump()，v1 没有，因此做一次能力探测。
        """
        model_dump = getattr(self, "model_dump", None)
        if callable(model_dump):
            return model_dump()
        return self.dict()

    def dump(self) -> bool:
        """持久化配置，返回是否写成功。

        打包后 USER_DATA_DIR 就是 exe 所在目录；放在 Program Files 之类只读位置时
        写文件会抛 OSError。以前异常一路冒泡，把 /max_power、/pattern、/osc_addr
        全变成 500 —— 用户只是把软件放进了系统目录，结果一项设置都存不下来。
        持久化失败不该打断当前操作，这里只记录原因并返回 False。
        """
        # 运行时锁不应持久化为 false，否则下次启动会短暂无输出
        self.can_update_power = True
        path = os.path.join(USER_DATA_DIR, "settings.yaml")
        try:
            # 显式 utf-8：Windows 默认编码是 GBK，历史文件也是靠回落本地编码读的
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self._as_dict(), f)
            return True
        except Exception as e:
            print(f"[settings] 写入 settings.yaml 失败（本次修改未持久化）: {e}")
            return False

    @classmethod
    def _backup_broken(cls, user_yaml: str):
        """把损坏的配置文件另存为带时间戳的 .bak，避免覆盖上一次的备份。"""
        try:
            if os.path.exists(user_yaml):
                import shutil
                stamp = time.strftime("%Y%m%d-%H%M%S")
                shutil.copyfile(user_yaml, f"{user_yaml}.{stamp}.bak")
        except Exception as e:
            print(f"[settings] 备份损坏的 settings.yaml 失败: {e}")

    @classmethod
    def _read_yaml(cls, path: str):
        """读取 yaml 文本。优先 UTF-8，失败时回落系统本地编码（历史文件可能是 GBK）。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except UnicodeDecodeError:
            with open(path, "r") as f:
                return yaml.safe_load(f)

    @classmethod
    def load(cls):
        user_yaml = os.path.join(USER_DATA_DIR, "settings.yaml")
        # 打包模式下首次运行：USER_DATA_DIR（exe 同目录）还没有 settings.yaml，
        # 从打包内置的只读副本（BASE_DIR）复制一份到外部，便于用户后续修改持久化。
        if not os.path.exists(user_yaml):
            builtin_yaml = os.path.join(BASE_DIR, "settings.yaml")
            if os.path.exists(builtin_yaml):
                import shutil
                try:
                    shutil.copyfile(builtin_yaml, user_yaml)
                except Exception as e:
                    print(f"[settings] 复制内置 settings.yaml 失败: {e}")

        try:
            settings_dict = cls._read_yaml(user_yaml)
        except FileNotFoundError:
            # 首次运行且没有内置副本可复制，直接用默认值，不算错误
            return cls()
        except Exception as e:
            # 文件不可读 / YAML 语法错误：备份后回落默认值。
            # 这里不能让异常冒泡——load() 在模块级执行，一旦崩溃整个后端起不来，
            # 用户改坏了配置就再也打不开程序，且没有任何自助恢复路径。
            print(f"[settings] 读取 settings.yaml 失败，已备份为 .bak 并使用默认配置: {e}")
            cls._backup_broken(user_yaml)
            return cls()

        if not isinstance(settings_dict, dict):
            # 空文件（safe_load 返回 None）或纯标量 / 列表，均按默认配置处理
            if settings_dict is not None:
                print(f"[settings] settings.yaml 顶层格式异常"
                      f"（{type(settings_dict).__name__}，应为键值对），使用默认配置")
            return cls()

        try:
            return cls(**settings_dict)
        except Exception as e:
            # 字段类型错误等校验失败，同样回落默认值而不是崩溃
            print(f"[settings] settings.yaml 字段校验失败，已备份为 .bak 并使用默认配置: {e}")
            cls._backup_broken(user_yaml)
            return cls()


settings = Settings.load()
