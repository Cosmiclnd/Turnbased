import item
import enums

class ModifierFilter(enums.Enum):
    BASE = item.Item("base", "Base")
    SELF_CONVERSION = item.Item("self_conversion", "Self Conversion")
    CALCULATED = item.Item("calculated", "Calculated")
    ALL = (BASE, SELF_CONVERSION, CALCULATED)
ModifierFilter.init()

class Stat:
    __slots__ = ("name", "target", "base_value", "calculated_value", "modifiers")

    def __init__(self, name, target=None):
        self.name = name
        self.target = target
        self.base_value = 0
        self.calculated_value = 0
        self.modifiers = item.ItemList()
    
    def calculate(self, filter=ModifierFilter.CALCULATED, **kwargs):
        if filter is ModifierFilter.BASE:
            return self.base_value
        self.calculated_value = self.base_value
        for modifier in self.modifiers:
            modifier.modify(self, filter, **kwargs)
        return self.calculated_value

class StatDesc:
    __slots__ = ("desc",)

    def __init__(self, desc):
        # desc必须是元组
        self.desc = desc if type(desc[0]) is tuple else (desc,)
        # self.desc是元组的元组
        # 每个元素的格式是(stat, filter, value)
        # stat为None时value作为offset，此时filter也为None
        # stat不为None时value作为scale
    
    def calculate(self, **kwargs):
        result = 0
        for stat, filter, value in self.desc:
            if stat is None:
                result += value
            else:
                result += stat.calculate(filter, **kwargs) * value
        return result
    
    def scale(self, scale):
        return StatDesc(tuple((stat, filter, value * scale) for stat, filter, value in self.desc))
    
    def calcutale_self_conversion(self, target_stat):
        # 只计算自身转化得到的值
        result = 0
        for stat, filter, value in self.desc:
            if stat is None:
                result += value
            elif stat is target_stat:
                result += stat.calculate(filter) * value
        return result

class StatDict(dict[str, Stat]):
    def new_stats(self, names, target=None):
        for name in names:
            self[name] = Stat(name, target)

class Modifier(item.Item):
    def __init__(self, nameid, name, stat_desc, validator=None, master=None):
        super().__init__(nameid, name, master)
        self.stat_desc = stat_desc
        self.validator = validator
    
    def modify(self, stat, filter, **kwargs):
        if filter is ModifierFilter.BASE:
            return
        if self.validator is not None and not self.validator(stat, **kwargs):
            return
        # 属性相同时filter只能为ModifierFilter.BASE
        # 属性不同时filter只能为ModifierFilter.BASE或ModifierFilter.SELF_CONVERSION
        # 防止循环转化
        if filter is ModifierFilter.SELF_CONVERSION:
            stat.calculated_value += self.stat_desc.calcutale_self_conversion(stat)
        else:
            # 理论上几乎不会用到
            stat.calculated_value += self.stat_desc.calculate()
