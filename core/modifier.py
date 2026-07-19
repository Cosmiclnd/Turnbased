from collections.abc import Callable

from . import item
from . import enums

from ._modifier import ModifierFilter, Stat, StatDesc, StatDescFunc, Modifier

class StatDict(dict):
    def new_stats(self, names, target=None):
        for name in names:
            self[name] = Stat(name, target)
    
    def print(self, indent=0):
        for stat in self.values():
            print(" " * indent +
                f"{stat.target.nameid}.{stat.name}: {stat.calculate()} [{stat.calculate(ModifierFilter.SELF_CONVERSION)}] ({stat.base_value})")

class StatConverter(StatDescFunc):
    def __init__(self, threshold, step, scale, cap):
        self.threshold = threshold
        self.step = step
        self.scale = scale
        self.cap = cap
    
    def call(self, value, **kwargs):
        if value < self.threshold:
            return 0
        times = (value - self.threshold) // self.step
        if self.cap is None:
            return times * self.scale
        return min(times * self.scale, self.cap)
    
    def scale(self, scale):
        if self.cap is None:
            return StatConverter(self.threshold, self.step, self.scale * scale, None)
        return StatConverter(self.threshold, self.step, self.scale * scale, self.cap * scale)
