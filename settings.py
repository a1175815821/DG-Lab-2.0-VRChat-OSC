# Configuration if using DG-Lab Coyote:

# Set to the Bluetooth UID for your particular Coyote device
# if `COYOTE_UID` is `None`, the program will try detactig cotoye automatically
COYOTE_UID = "C9:9F:E4:2E:31:60"
# Multiplier to translate between 0-100 vibration intensity and e-stim intensity.
COYOTE_MULTIPLIER = 6.0
# Enable or disable safe mode. This caps the max e-stim output of the device. Warning: Don't touch unless you know what you're doing!
COYOTE_SAFE_MODE = True
COYOTE_MAX_POWER_A = 100
COYOTE_MAX_POWER_B = 100
COYOTE_PATTERN = "vibrator_4"
# OSC address bind to channel A.
# The value of this address must be a float number between 0 and 1.
COYOTE_ADDR_A = "/avatar/parameters/EarLDis"
# OSC address bind to channel B.
# The value of this address must be a float number between 0 and 1.
COYOTE_ADDR_B = "/avatar/parameters/EarRDis"

# Host ip of VRChat client.
VRC_HOST = "127.0.0.1"
# OSC port of VRChat client.
# If you have no idea what it is, leave it as default.
VRC_OSC_PORT = 9001

# Window size of the moving average filter (in seconds).
WINDOW_SIZE = 0.1

#             ▲
#             │
#             │
#             │                max_limit
#         1.0 │               xx───────
#             │              xx
#             │             xx
#             │            xx
#             │           xx
#             │          xx
#   min_power │   ┌─────xx
#             │   │       min_limit
#             └───┴──────────────────────────►
#             start_limit

# When the average value of the signal is below this value, the power will be set to `0`.
START_LIMIT = 0.05
# When the average value of the signal is below this value, the power will be set to `min_power * COYOTE_MAX_POWER`.
MIN_LIMIT = 0.2
# When the average value of the signal is above this value, the power will be set to `1.0 * COYOTE_MAX_POWER`.
MAX_LIMIT = 0.8
# The minimum power rate of the e-stim device.
MIN_POWER = 0.5

CAN_UPDATE_POWER = True
WARN_ON_STACK_DUMP_SOUND = True

from pydantic import BaseModel


class Settings(BaseModel):
    # Set to the Bluetooth UID for your particular Coyote device
    # if `coyote_uid` is `None`, the program will try detactig cotoye automatically
    coyote_uid: str = "C9:9F:E4:2E:31:60"
    # Multiplier to translate between 0-100 vibration intensity and e-stim intensity.
    coyote_multiplier: float = 6.0
    # Enable or disable safe mode. This caps the max e-stim output of the device. Warning: Don't touch unless you know what you're doing!
    coyote_safe_mode: bool = True
    coyote_max_power_a: int = 100
    coyote_max_power_b: int = 100
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

    # Host ip of VRChat client.
    vrc_host: str = "127.0.0.1"
    # OSC port of VRChat client.
    # If you have no idea what it is, leave it as default.
    vrc_osc_port: int = 9001

    # Window size of the moving average filter (in seconds).
    window_size: float = 0.1

    #             ▲
    #             │
    #             │
    #             │                max_limit
    #         1.0 │               xx───────
    #             │              xx
    #             │             xx
    #             │            xx
    #             │           xx
    #             │          xx
    #   min_power │   ┌─────xx
    #             │   │       min_limit
    #             └───┴──────────────────────────►
    #             start_limit

    # When the average value of the signal is below this value, the power will be set to `0`.
    start_limit: float = 0.05
    # When the average value of the signal is below this value, the power will be set to `min_power * COYOTE_MAX_POWER`.
    min_limit: float = 0.2
    # When the average value of the signal is above this value, the power will be set to `1.0 * COYOTE_MAX_POWER`.
    max_limit: float = 0.8
    # The minimum power rate of the e-stim device.
    min_power: float = 0.5

    can_update_power: bool = True
    warn_on_stack_dump_sound: bool = True

    def dump(self):
        with open(os.path.join(USER_DATA_DIR, "settings.yaml"), "w") as f:
            yaml.dump(self.dict(), f)

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
        with open(user_yaml, "r") as f:
            settings_dict = yaml.safe_load(f)
        return Settings(**settings_dict)


import os
import yaml

from common.paths import BASE_DIR, USER_DATA_DIR


def load_settings():
    user_yaml = os.path.join(USER_DATA_DIR, "settings.yaml")
    if not os.path.exists(user_yaml):
        builtin_yaml = os.path.join(BASE_DIR, "settings.yaml")
        if os.path.exists(builtin_yaml):
            import shutil
            try:
                shutil.copyfile(builtin_yaml, user_yaml)
            except Exception as e:
                print(f"[settings] 复制内置 settings.yaml 失败: {e}")
    with open(user_yaml, "r") as f:
        settings_dict = yaml.safe_load(f)
    return Settings(**settings_dict)


# settings = load_settings()

settings = Settings.load()
