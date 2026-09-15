from typing import Dict, Any
from toys.base import Toy, FEATURE_ESTIM
import json
import logging
import os
from common.paths import BASE_DIR


# default 波形内置在代码里：data/estim 整个丢失时程序也必须能起来。
# load_patterns 由 Estim.__init__ 调用，而 CoyoteInterface 是在 routers/coyote.py
# 模块级构造的 —— 一旦这里抛异常，整个后端 import 就失败，
# 表现为「双击 exe 没有任何窗口、38080 无监听」，用户完全没有自助恢复的余地。
_DEFAULT_VARIANTS = [
    [
        [10, 90, 10]
    ],  # Default pattern - simple, one-state pattern of 10 ms pulse, 90 ms pause, amplitude 10
    [
        [5, 135, 20],
        [5, 135, 20],
        [5, 135, 20],
        [5, 135, 20],
        [5, 135, 20],
        [5, 135, 20],
        [5, 135, 20],
        [5, 135, 20],
        [5, 135, 20],
        [5, 95, 20],
        [4, 86, 20],
        [4, 76, 20],
        [4, 66, 20],
        [3, 57, 20],
        [3, 37, 20],
        [3, 37, 20],
        [2, 28, 20],
        [2, 18, 20],
        [1, 14, 20],
        [1, 9, 20],
    ],  # varied pattern of 20 states
]


class Estim(Toy):
    patterns: Dict[str, Any]

    def load_patterns(self) -> Dict[str, Any]:
        """加载波形数据。任何单个文件的问题都不允许影响程序启动。

        波形文件在打包后位于只读资源目录，可能因磁盘错误、杀软误删、用户手动
        清理而缺失。以前是裸 open()，任何一个文件缺失都会让 load_patterns 抛
        FileNotFoundError，进而让后端整个起不来（而且没有任何界面提示）。
        """
        patterns: Dict[str, Any] = {}

        dict_path = os.path.join(BASE_DIR, "data", "estim", "pattern_dict.json")
        try:
            with open(dict_path, encoding="utf-8") as pf:
                raw = json.loads(pf.read())
        except Exception as e:
            logging.error("读取波形索引失败，将只提供内置 default 波形：%s（%s）", dict_path, e)
            raw = {}

        if not isinstance(raw, dict):
            logging.error("波形索引顶层不是键值对，已忽略：%s", dict_path)
            raw = {}

        for name, files in raw.items():
            if not isinstance(files, list):
                logging.warning("波形 %s 的定义不是文件列表，已跳过", name)
                continue
            states = []
            for pattern in files:
                path = os.path.join(BASE_DIR, "data", "estim", "patterns", str(pattern))
                try:
                    with open(path, encoding="utf-8") as psf:
                        data = json.loads(psf.read())
                except Exception as e:
                    logging.warning("波形文件缺失或损坏，已跳过：%s（%s）", path, e)
                    continue
                if isinstance(data, list):
                    states.extend(data)
            if states:
                patterns[name] = states
            else:
                logging.warning("波形 %s 没有任何可用数据，已从列表移除", name)

        # default 与其它波形保持相同的「状态列表」结构 [[pulse, pause, amp], ...]。
        # 若保留原始的「变体列表」（三层嵌套），dg_interface.signal() 里的
        # `ax, ay, az = state` 会抛 ValueError，导致选中后设备完全无输出。
        patterns["default"] = [
            state for variant in _DEFAULT_VARIANTS for state in variant
        ]
        return patterns

    def __init__(self, name):
        self.patterns = self.load_patterns()
        super().__init__(name, [FEATURE_ESTIM])
