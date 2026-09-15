"""Encoding functionality for communicating with bluetooth device.

Based on the official DG-LAB Coyote specification:
https://github-com.translate.goog/dg-lab-opensource?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=da

Byte encoding functionality ported from previous work by @rezreal (https://github.com/rezreal/coyote)

Licensed under the MIT License, (c) 2022 S. F. S.
"""

import struct


def encode_power(pow_a: int, pow_b: int) -> bytes:
    """
    Encodes e-stim power settings into a three-byte message for consumption by the bluetooth device.

    Valid input range (int): 0 <= pow_[a|b] <= 200.

    :param pow_a: output strength of channel a
    :param pow_b: output strength of channel b
    :return: three-byte bytes object
    """
    # Dark bit-wise magic courtesy of @rezreal (https://github.com/rezreal/coyote)
    b0 = (pow_a >> 5) & 0b00111111
    b1 = ((pow_a & 0b00011111) << 3) | ((pow_b & 0b11111111111) >> 8)
    b2 = pow_b & 0b11111111
    return bytes([b2, b1, b0])  # flip the first and third bytes


def encode_pattern(ax: int, ay: int, az: int) -> bytes:
    """
    Encodes e-stim pattern state into a three-byte message for consumption by the bluetooth device.

    Valid input range:
        0 <= ax <=   31 pulse length in ms
        0 <= ay <= 1023 pause duration (between pulses) in ms
        0 <= az <=   31 amplitude

        :param ax: pulse duration in ms
        :param ay: pause duration in ms
        :param az: amplitude
        :return: three-byte bytes object

    """

    # Dark bit-wise magic courtesy of @rezreal (https://github.com/rezreal/coyote)
    b0 = ((az & 0b00011110) >> 1)
    b_ = ((az & 0b00000001) << 15) | ((ay & 0b00000011_11111111) << 5 | (ax & 0b00011111))

    # Unpack the unsigned short (Uint16) into two unsigned chars (Uint8).
    b1, b2 = struct.pack("H", b_)

    # Verify split:
    # print(format(b_, "b"), "-->", format(b1, "b"), format(b2, "b"))

    # Identical: # struct.pack("BBB", b2, b1, b0)

    return bytes([b1, b2, b0])  # cut and append first byte behind the third byte


# 字节布局备忘（原先这里还有一个 test_function_validity()，用于拿
# fuzzy_power_data.json / fuzzy_pattern_data.json 逐条比对 JS 原版实现，
# 但那两个数据文件并不在仓库里，函数永远跑不起来，已删除）：
#
#   encode_power(pow_a, pow_b) → 3 字节
#     b0 = pow_a >> 5          (高 6 位)
#     b1 = (pow_a & 0x1F) << 3 | (pow_b >> 8)
#     b2 = pow_b & 0xFF
#     实际发送顺序：b2, b1, b0（首尾字节对调）
#
#   encode_pattern(ax, ay, az) → 3 字节
#     b_ = (az & 0x01) << 15 | (ay & 0x3FF) << 5 | (ax & 0x1F)
#     b0 = (az & 0x1E) >> 1
#     b1, b2 = struct.pack("H", b_)   # 小端拆成两个字节
#     实际发送顺序：b1, b2, b0
