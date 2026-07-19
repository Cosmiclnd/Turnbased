from collections.abc import Callable

from . import item
from . import enums

from ._modifier import ModifierFilter, Stat, StatDescUnit, StatDesc, StatDescFunc

class StatDesc:
    __slots__ = ("desc")

    def __init__(self, desc):
        # desc必须是元组
        self.desc = desc if type(desc[0]) is tuple else (desc,)
        # self.desc是元组的元组
        # 每个元素的格式是(stat, filter, func)
        # stat为None时func()作为offset，此时filter也为None
        # stat不为None时func()作为scale
        # func必须是数或StatDescFunc，当func为数时直接取该值
    
    def calculate(self, target=None, **kwargs):
        result = 0
        for stat, filter, func in self.desc:
            if stat is None:
                result += func(**kwargs) if isinstance(func, StatDescFunc) else func
            elif isinstance(stat, Stat):
                value = stat.calculate(filter, **kwargs)
                result += func(value, **kwargs) if isinstance(func, StatDescFunc) else value * func
            elif isinstance(stat, str):
                value = target.stats[stat].calculate(filter, **kwargs)
                result += func(value, **kwargs) if isinstance(func, StatDescFunc) else value * func
        return result
    
    def calculate_self_conversion(self, target_stat, target=None, **kwargs):
        # 只计算自身转化得到的值
        # target_stat必须是Stat的实例
        result = 0
        for stat, filter, func in self.desc:
            if stat is None:
                result += func(**kwargs) if isinstance(func, StatDescFunc) else func
            elif stat is target_stat:
                value = stat.calculate(filter, **kwargs)
                result += func(value, **kwargs) if isinstance(func, StatDescFunc) else value * func
            elif isinstance(stat, str) and stat == target_stat.name:
                value = target.stats[stat].calculate(filter, **kwargs)
                result += func(value, **kwargs) if isinstance(func, StatDescFunc) else value * func
        return result
    
    def scale(self, scale):
        return StatDesc(tuple((stat, filter, value.scale(scale) if isinstance(value, StatDescFunc) else value * scale)
            for stat, filter, value in self.desc))
    
    def print(self, target, indent=0):
        for stat, filter, func in self.desc:
            if stat is None:
                result = func(**kwargs) if isinstance(func, StatDescFunc) else func
            elif isinstance(stat, Stat):
                value = stat.calculate(filter)
                result = func(value) if isinstance(func, StatDescFunc) else value * func
                stat_name = f"{stat.target.nameid}.{stat.name}"
            elif isinstance(stat, str):
                value = target.stats[stat].calculate(filter)
                result = func(value) if isinstance(func, StatDescFunc) else value * func
                stat_name = f"*.{stat}"
            if stat is not None:
                if isinstance(func, StatDescFunc):
                    print(" " * indent + f"{result} <stat={stat_name}, filter={filter.name}, func>")
                else:
                    print(" " * indent + f"{result} <stat={stat_name}, filter={filter.name}, scale={func}>")
            else:
                print(" " * indent + f"{result}")

class StatDict(dict):
    def new_stats(self, names, target=None):
        for name in names:
            self[name] = Stat(name, target)
    
    def print(self, indent=0):
        for stat in self.values():
            print(" " * indent +
                f"{stat.target.nameid}.{stat.name}: {stat.calculate()} [{stat.calculate(ModifierFilter.SELF_CONVERSION)}] ({stat.base_value})")

class Modifier(item.Item):
    def __init__(self, nameid, name, stat_desc, validator=None, master=None):
        super().__init__(nameid, name, master)
        self.stat_desc = stat_desc
        self.validator = validator
    
    def modify(self, stat, filter, **kwargs):
        if filter is ModifierFilter.BASE:
            return 0
        if self.validator is not None and not self.validator(stat, **kwargs):
            return 0
        # 属性相同时filter只能为ModifierFilter.BASE
        # 属性不同时filter只能为ModifierFilter.BASE或ModifierFilter.SELF_CONVERSION
        # 防止循环转化
        if filter is ModifierFilter.SELF_CONVERSION:
            return self.stat_desc.calculate_self_conversion(stat, target=stat.target, **kwargs)
        else:
            return self.stat_desc.calculate(target=stat.target, **kwargs)
    
    def print(self, stat, indent=0):
        if self.validator is not None:
            print(" " * indent + f"{self.name} ({self.nameid}) <validator={self.validator(stat)}>")
        else:
            print(" " * indent + f"{self.name} ({self.nameid})")
        self.stat_desc.print(stat.target, indent + 2)

class StatDescFunc:
    def __call__(self, value=None, **kwargs):
        raise NotImplementedError
    
    def scale(self, scale):
        return self

class StatConverter(StatDescFunc):
    def __init__(self, threshold, step, scale, cap):
        self.threshold = threshold
        self.step = step
        self.scale = scale
        self.cap = cap
    
    def __call__(self, value, **kwargs):
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
