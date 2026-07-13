"""
The following makes available for integration into SkyrimToyInterface by "Min"
(https://www.loverslab.com/files/file/22380-skyrim-irl-toy-chastity-interface-le-se-ae-vr/) a class which interfaces
directly with the DG-Lab Coyote e-stim box over bluetooth.

Note: This code requires the bluetooth package "bleak" (https://pypi.org/project/bleak/) to be installed from pypi.
It is recommended that you use python's built-in package manager "pip":


>> pip install bleak


Code written based on the official DG-LAB Coyote specification:
https://github-com.translate.goog/dg-lab-opensource?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=da

Byte encoding functionality ported from previous work by @rezreal (https://github.com/rezreal/coyote)


Disclaimer:

USE THIS SOFTWARE AT YOUR OWN RISK. THE COMPATIBLE E-STIM DEVICE IS VERY POWERFUL, MEANING THAT HARDWARE MALFUNCTIONS
OR UNDETECTED SOFTWARE BUGS MAY LEAD TO SUDDEN AND/OR VERY PAINFUL ELECTRICAL STIMULATION. THERE IS NO GUARANTEE OF
IT BEING 100 % RELIABLE AND SAFE ON YOUR COMPUTER SYSTEM OR PLATFORM. CONSEQUENTLY, THE AUTHOR(S) ASSUME NO LIABILITY
OF ANY KIND.

TAKE SPECIAL CARE NOT TO SET THE E-STIM POWER TO AN ORDER OF MAGNITUDE HIGHER THAN YOU WANTED; ALL IT TAKES IS A SINGLE
TYPO. THE SAFE MODE IS THERE FOR A REASON.

REMEMBER: SUDDEN, UNEXPECTED ELECTRICAL STIMULATION IS FELT MUCH MORE STRONGLY THAN CONTINUOUS STIMULATION.


PLEASE USE COMMON SENSE AND USE E-STIM RESPONSIBLY.

DO NOT MOVE OR OTHERWISE INTERACT WITH THE ELECTRODES WHILE THE E-STIM DEVICE IS ACTIVE. YOU MIGHT ACCIDENTALLY
PROVIDE AN UNINTENDED PATH FOR THE CURRENT TO GO THROUGH VULNERABLE BODY PARTS.

DO NOT USE E-STIM ABOVE THE WAIST, ESPECIALLY NOT ACROSS THE CHEST.

DO NOT USE E-STIM WHILE IN AN ALTERED STATE OF MIND. BEING EXCITED LIKE A LUSTY ARGONIAN MAID IS OKAY, THOUGH.

DO NOT USE E-STIM ON A PARTNER WITHOUT THEIR EXPRESS CONSENT. TAKE EXTRA CARE WHEN PLAYING WITH A PARTNER.


THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Licensed under the MIT License, (c) 2022 S. F. S.
"""

import traceback
from typing import Tuple
import bleak  # bluetooth functionality

# custom functionality for encoding communication to the bluetooth device
import toys.estim.coyote.dg_encoding as dg_encoding
import logging
import time
import asyncio
from toys.estim.estim import Estim
from settings import settings

# can_update_power 超时兜底：记录 set_pwm 设置 can_update_power=False 的时间
# coyote.py 的 _check_power_lock_timeout 会读取此变量判断是否超时
_can_update_power_set_time: float = 0.0
_POWER_LOCK_TIMEOUT = 5.0  # 秒


class CoyoteInterface(Estim):
    """
    DG-LAB Coyote interface for SkyrimToyInterface integration.

    Attributes:
        device_uid (str): The Unique Identifier of the bluetooth e-stim device, usually a string of six base 16 values
                            joined by colons, for example: "D7:ED:72:AF:D7:18".
        power_multiplier (float): Regulates how powerful the e-stim scales compared to "vibration strength". Higher
                            values means stronger stimulation. Be careful!
        default_channel (str): Set default output channel, either "a" or "b".
        safe_mode (bool): Caps e-stim device power output to max 100 (50% of 0-200 range). Don't turn off unless you know
                            what you are doing! See self.set_pwm() for implementation details.
    """

    pattern_name_a: str
    pattern_name_b: str
    switch_pattern: bool = False

    def __init__(
        self,
        device_uid="C9:9F:E4:2E:31:60",
        power_multiplier=1.0,
        default_channel="a",
        safe_mode=True,
    ):
        """
        The constructor for the CoyoteInterface class.

        :param device_uid:
        :param power_multiplier:
        :param safe_mode:
        """
        super().__init__("coyote")
        self.battery = -1
        self.pow_a = 1
        self.pow_b = 1
        # Set bluetooth device uid and device reference
        if device_uid is not None and device_uid != "":
            self.device_uid = device_uid
            self.device = bleak.BleakClient(
                self.device_uid, timeout=settings.coyote_connect_timeout
            )
        else:
            # attempt to find device automatically if device_uid left blank.
            logging.info("Coyote UID was left blank. Trying to find the device automatically.")
            self.device = None

        # Bluetooth characteristic placeholders; populated in self.connect()
        self._battery_level = None  # battery level
        self._config = None  # configuration
        self._pwm_ab2 = None  # power
        self._pwm_a34 = None  # channel b
        self._pwm_b34 = None  # channel a

        # Caution: the channels a & b are actually switched compared to the official spec, so that a34 outputs to
        # channel b, and b34 to channel a. This is corrected automatically if the following flag is set.
        self.channels_switched = True

        # Set default output channel. This provides the default channel for self.vibrate().
        # You can override the default output channel with self.signal()
        self.default_channel = default_channel

        # Multiplier applied to mapped signal: power = min(safe_limit, max_power * signal * multiplier)
        # Default 1.0 so the UI max-power slider maps 1:1 at full signal.
        self.power_multiplier = power_multiplier

        # Flag to indicate connection status
        self.is_connected = False

        # Flag: Cap power intensity to 100 (out of 0-200) for safety reasons. The limit is enforced in
        # the self.set_pwm() method.
        # Do not disable unless absolutely certain that you know what you are doing!
        self.safe_mode = safe_mode

        # todo: import patterns from patterns.json and choose according to type of in-game event
        # Placeholder e-stim patterns
        #
        # Pattern schema is a list of lists [[x, y, z], [x, y, z], ...], where
        #
        # x pulse length: 0-31 ms
        # y pause length: 0-1023 ms
        # z amplitude: 0-31
        #
        # See https://github-com.translate.goog/dg-lab-opensource?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=da
        # for more information
        # self.patterns = [

        # ]

    #
    # Internal methods
    #

    async def set_pwm(self, pow_a: int, pow_b: int):
        """
        Set power level of channel a and channel b

        Valid input range (int): 0 <= pow_[a|b] <= 200
        (DG-Lab Coyote 官方强度范围为 0-200)

        :param pow_a: Output power of channel a, if set to -1, the power level will not be changed
        :param pow_b: Output power of channel b, if set to -1, the power level will not be changed
        """

        if pow_a < 0:
            pow_a = self.pow_a
        if pow_b < 0:
            pow_b = self.pow_b

        # 强度范围 0-200，变化阈值 1 保证精细调节
        if abs(pow_a - self.pow_a) < 1 and abs(pow_b - self.pow_b) < 1:
            return

        logging.info(f"set_pwm({pow_a}, {pow_b})")
        self.pow_a = pow_a
        self.pow_b = pow_b

        settings.can_update_power = False
        # 记录锁定时间，用于超时兜底
        global _can_update_power_set_time
        _can_update_power_set_time = time.time()

        # safe_mode 启用时限制最大强度为 100（约 50%），否则允许到 200
        if self.safe_mode:
            in_valid_range = 0 <= pow_a <= 100 and 0 <= pow_b <= 100
        else:
            in_valid_range = 0 <= pow_a <= 200 and 0 <= pow_b <= 200

        if in_valid_range:
            # Encode inputs to byte sequence
            message = dg_encoding.encode_power(pow_a, pow_b)

            # Communicate byte sequence to device
            await self.device.write_gatt_char(self._pwm_ab2.uuid, message)
            # Read & confirm new values
            output = await self.device.read_gatt_char(self._pwm_ab2)
            # logging.info(
            #     f"Wrote byte sequence to _pwm_ab2: {message}, confirmation: {output}")
        else:
            if self.safe_mode:
                logging.error("Caution, safe mode is enabled.")
                logging.error(
                    f"Input values pow_a ({pow_a}) & pow_b ({pow_b}) must both be within the range 0-100!"
                )
            else:
                logging.error(
                    f"Input values pow_a ({pow_a}) & pow_b ({pow_b}) must both be within the range 0-200!"
                )

    def _calculate_pattern_duration(self, pattern: list) -> int:
        """
        Calculates total duration of a pattern's combined pulses and pauses. Output duration is in milliseconds.

        :param pattern: List of lists of the schema [[ax, ay, az], [ax, ay, az], ...] representing an e-stim pattern.
        :return: Total duration of pattern duration in milliseconds.
        """
        return sum([x[0] + x[1] for x in pattern])

    #
    # User-facing functions
    #

    async def search_for_device(self):
        # BLEAK bluetooth device placeholders
        self.scanner = None
        self.device = None
        self.device_uid = None
        self.device_alias = "D-LAB ESTIM01"

        logging.info("Scanning for Bluetooth devices.")
        self.scanner = bleak.BleakScanner()
        bluetooth_devices = await self.scanner.discover(timeout=10)

        # Search for Coyote device with name/alias "DG-LAB ESTIM01".
        # on success, order the list to end with the devices with the strongest signal.
        # If there are several active DG-Lab Coyote devices active simultaneously for pairing,
        # then this will ensure that the code defaults to the device closest to the Bluetooth adapter.
        # todo: Allow for choosing between several e-stim devices, if present simultaneously.
        if bluetooth_devices:
            # Sort in descending order of signal strength
            bluetooth_devices.sort(key=lambda device: device.rssi, reverse=True)
            logging.info(bluetooth_devices)

            # Look for the DG-Lab Coyote device among the detected devices.
            for bluetooth_device in bluetooth_devices:
                # Is this the Coyote device?
                if bluetooth_device.name == self.device_alias:
                    # If we've already found one Coyote device, skip additional devices with same alias.
                    if self.device_uid:
                        logging.warning(
                            f"More than one Coyote was found. Skipping subsequent device: {bluetooth_device.name}"
                        )
                    else:
                        # Save UUID of found device to self.device_uid and instantiate BLEAK as normal.
                        self.device_uid = bluetooth_device.address
                        logging.info(f"Coyote found! UUID: {self.device_uid}")
                        self.device = bleak.BleakClient(
                            self.device_uid, timeout=settings.coyote_connect_timeout
                        )
            if not self.device_uid:
                raise RuntimeError(
                    "BLEAK failed to find the DG-Lab Coyote automatically."
                )
        else:
            raise RuntimeError("BLEAK failed to find any Bluetooth devices.")

    async def connect(self, retries: int = 3):
        """
        Connect to the device and register characteristics.

        :param retries: Indicates the number of attempts to connect before raising an exception and halting the program.
        """

        logging.info("Connecting to device: {} ...".format(self.device_uid))

        saved_exception = ConnectionError
        if not self.device.is_connected:
            for _ in range(retries):
                # Catch time-out errors while we retry
                try:
                    self.is_connected = await self.device.connect()
                    logging.info("Connected!")
                    break
                except Exception as e:
                    # Overwrite generic ConnectionError with actual exception
                    saved_exception = e
                    logging.error(traceback.format_exc())
                    logging.error(
                        f"Caught TimeoutError or CancelledError exception. Retrying... {type(e)}: {e}"
                    )
                    self.is_connected = False
                    self.device._backend._timeout *= 2

        if not self.device.is_connected:
            # raise ConnectionError("Failed to connect to bluetooth device")
            logging.error("Failed to connect to bluetooth device.")
            raise saved_exception

        # Get services
        # Obs: the following can also be accessed without functions through
        # device.services.services (list)
        # device.services.characteristics (list)

        logging.info("Getting services...")
        services = self.device.services
        # convert from async iterator to list
        services = [service for service in services]

        # Pick out and save services and characteristics according to Service UUID
        for service in services:
            if service.uuid == "955a180a-0fe2-f5aa-a094-84b8d4f3e8ad":
                battery_level_service = service
                # logging.info("found battery service: ", service.uuid)

                for characteristic in battery_level_service.characteristics:
                    if characteristic.uuid == "955a1500-0fe2-f5aa-a094-84b8d4f3e8ad":
                        self._battery_level = characteristic
                        # logging.info("found battery level characteristic: ", characteristic.uuid)

            if service.uuid == "955a180b-0fe2-f5aa-a094-84b8d4f3e8ad":
                pwm = service
                # logging.info("found power strength service: ", service.uuid)

                for characteristic in pwm.characteristics:
                    if characteristic.uuid == "955a1504-0fe2-f5aa-a094-84b8d4f3e8ad":
                        # logging.info("found channels strength characteristic: ", characteristic.uuid)
                        self._pwm_ab2 = characteristic

                    if characteristic.uuid == "955a1505-0fe2-f5aa-a094-84b8d4f3e8ad":
                        # logging.info("found channel A characteristic: ", characteristic.uuid)

                        # Caution: xxxx1505/PWM_A34 actually maps to channel b. Switch automatically if
                        # self.channels_switched flag is set to True.
                        if self.channels_switched:
                            self._pwm_b34 = characteristic
                        else:
                            self._pwm_a34 = characteristic

                    if characteristic.uuid == "955a1506-0fe2-f5aa-a094-84b8d4f3e8ad":
                        # logging.info("found channel B characteristic: ", characteristic.uuid)

                        # Caution: xxxx1506/PWM_B34 actually maps to channel a. Switch automatically if
                        # self.channels_switched flag is set to True.
                        if self.channels_switched:
                            self._pwm_a34 = characteristic
                        else:
                            self._pwm_b34 = characteristic

                    if characteristic.uuid == "955a1507-0fe2-f5aa-a094-84b8d4f3e8ad":
                        # logging.info("found config characteristic: ", characteristic.uuid)
                        self._config = characteristic

        # Test connectivity
        # Read the unit power level (%)
        logging.info("Querying battery level...")
        logging.info(f"Battery level characteristic: {self._battery_level.uuid}")
        battery_level = await self.device.read_gatt_char(self._battery_level.uuid)

        # Convert from bytearray to hex to decimal
        battery_level_dec = int(battery_level.hex(), 16)
        logging.info(f"Current device battery level: {battery_level_dec}")
        self.battery = battery_level_dec

        # write output power = 0 to device
        logging.info(
            "Attempting to communicate command 'set channels strength to 0' to device..."
        )
        message = bytes([0, 0, 0])
        logging.info(f"Writing {message} to {self._pwm_ab2.uuid}")

        # Communicate message to device
        output = await self.device.write_gatt_char(self._pwm_ab2.uuid, message)

        # Read output power from device
        logging.info(f"Reading current strength value from {self._pwm_ab2.uuid}")
        output = await self.device.read_gatt_char(self._pwm_ab2)

        if output == message:
            logging.info("Read: channels strength == {}".format(output))
            logging.info("Device read/write functionality confirmed.\nReady!")
        else:
            logging.error("Device read/write functionality could not be confirmed.")

    async def shutdown(self):
        await self.disconnect()

    async def disconnect(self):
        """Disconnect device."""
        if not self.is_connected:
            return

        logging.info("Disconnecting...")
        self.stop_signal = True
        self.is_connected = False
        output = await self.device.disconnect()

        if not self.device.is_connected:
            logging.info("Disconnected!")

    async def get_bettery_level(self) -> int:
        """Get battery level."""

        if not self.is_connected:
            return 0

        battery_level = await self.device.read_gatt_char(self._battery_level.uuid)

        # Convert from bytearray to hex to decimal
        battery_level_dec = int(battery_level.hex(), 16)
        self.battery = battery_level_dec
        return battery_level_dec

    async def signal(
        self, power: int, pattern_name: str, duration: int, channel: str = "a"
    ):
        """
        Send to device an e-stim pattern on channel a or b at a given power for a given duration.

        :param power: Set e-stim power (0 <= x <= 2047)
        :param pattern: Set pattern [ [ax, ay, az], [ax, ay, az], ...]
        :param duration: Set duration in milliseconds.
        :param channel: Set output channel a|b.
        """
        # todo: Enable multi-channel output, i.e. different patterns/power/durations on channels a & b simultaneously.

        # Set channel target (a/b)
        characteristic = self._pwm_b34 if channel == "b" else self._pwm_a34

        # Set killswitch
        self.stop_signal = False

        # Set power
        # todo: independent power strength for each individual channel. Perhaps thru
        await self.set_pwm(power, power)
        # self.get_pwm()?

        # if we assume that the given duration is in milliseconds (?), then we must calculate how many times the
        # pattern can be executed within that time-frame, depending on the length of the pattern, so that the pattern
        # does not run far longer than the intended duration.
        #
        # If the pattern is way longer than the given duration, just run the pattern once. I don't know whether this
        # will be a big issue, to be honest.

        if channel == "a":
            self.pattern_name_a = pattern_name
        else:
            self.pattern_name_b = pattern_name
        # pattern_duration = self._calculate_pattern_duration(ci.patterns[pattern_name])

        last_power_check = time.time()

        end_time = time.time() + duration / 1000
        cur_time = time.time()
        last_time = time.time() - 0.1
        # Iterate over the pattern and send each value (ax, ay, az) to the device in succession
        while cur_time < end_time:
            pattern_name = (
                self.pattern_name_a if channel == "a" else self.pattern_name_b
            )
            self.switch_pattern = False
            for state in self.patterns[pattern_name]:
                if self.switch_pattern:
                    break
                cur_time = time.time()
                if cur_time - last_time < 0.1:
                    await asyncio.sleep(0.01)
                    continue

                # info("cur time = {}, end time = {}".format(cur_time, end_time))
                if cur_time >= end_time:
                    logging.info("Shock - Hit time limit, stopping")
                    break
                if self.stop_signal:
                    return
                # Check to see if power output has been reduced to zero once per second
                if cur_time - last_power_check > 1.0:
                    if not await self.is_running():
                        return
                    last_power_check = time.time()
                # unpack pattern values
                ax, ay, az = state

                # Determine duration of state (ms)
                time_delta = (
                    ax + ay
                )  # consists of sum of pulse duration and pause duration

                # Encode pattern
                message = dg_encoding.encode_pattern(ax, ay, az)

                # Send message to bluetooth device
                output = await self.device.write_gatt_char(characteristic, message)
                last_time = time.time()

                settings.can_update_power = True

                # Sleep to avoid spamming the device and causing "frame tearing."
                # fixme: Might work worse than a flat time.sleep(0.1)?
                # time_delta / 1000)  # Convert from milliseconds to seconds
                # print("working")
                await asyncio.sleep(0.01)

    async def is_running(self):
        if not self.is_connected:  # Process is shutting down.
            return False
        try:
            output = await self.device.read_gatt_char(self._pwm_ab2)
            pass
        except Exception as e:
            logging.error(f"{e}\nReconnecting...")
            await self.connect()
            return False
        # If power is 0, stop() has been called outside this function.
        # TODO: Need a better way to check if the device is still running.
        # Because if the device is running, but the power is 0, this will return False.
        # if output == bytearray(b'\x00\x00\x00'):
        #     return False
        return True

    async def stop(self):
        """
        Set power to zero. Caution: This doesn't interrupt patterns already in progress.

        todo: Interrupt-based stop command.
        """
        if not self.is_connected:
            return
        self.stop_signal = True
        await self.set_pwm(0, 0)
