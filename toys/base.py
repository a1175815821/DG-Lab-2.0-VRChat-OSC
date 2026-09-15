#
# This module defines a common interface for toys. Some toy types will extend this.
#
# 说明：本项目只用到 estim 一类玩具，上游 GIFT 接口里的 vibrator/chastity/edge
# 常量与 check_in()/action()/get_toys() 桩方法从未被调用过，已移除。


FEATURE_ESTIM = "estim"


class Toy:
    def __init__(self, name, features=None, min_strength=0, max_strength=100):
        self.properties = {
            "name": name,
            # 注意不要写成 features=[]：可变默认参数会在多次实例化之间共享。
            "features": list(features) if features else [],
            "min_strength": min_strength,
            "max_strength": max_strength,
        }

    def connect(self):
        pass

    def stop(self):
        pass

    def shutdown(self):
        pass
