from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM, PyList_Append
from cpython.tuple cimport PyTuple_GET_SIZE, PyTuple_GET_ITEM

from ._item cimport Item, ItemList
from . import enums

class ModifierFilter(enums.Enum):
    BASE = Item("base", "Base")
    SELF_CONVERSION = Item("self_conversion", "Self Conversion")
    CALCULATED = Item("calculated", "Calculated")
    ALL = (BASE, SELF_CONVERSION, CALCULATED)
ModifierFilter.init()

cdef class Stat:
    cdef public:
        str name
        Item target
        double base_value
        ItemList modifiers
    
    def __init__(self, str name, Item target=None):
        self.name = name
        self.target = target
        self.base_value = 0
        self.modifiers = ItemList()
    
    cdef _calculate(self, Item filter, dict kwargs):
        cdef:
            double calculated_value
            Modifier modifier
            Py_ssize_t i, n
        if filter is ModifierFilter.BASE:
            return self.base_value
        calculated_value = self.base_value
        self.modifiers.refresh()
        n = PyList_GET_SIZE(self.modifiers.items)
        for i in range(n):
            modifier = <Modifier>PyList_GET_ITEM(self.modifiers.items, i)
            calculated_value += modifier._modify(self, filter, kwargs)
        return calculated_value
    
    def calculate(self, Item filter=ModifierFilter.CALCULATED, **kwargs):
        return self._calculate(filter, kwargs)
    
    def format(self, int indent=0):
        cdef:
            list lines = []
        lines.append(" " * indent + f"{self.target.nameid}.{self.name}: {self._calculate(ModifierFilter.CALCULATED, {})} "
            f"[{self._calculate(ModifierFilter.SELF_CONVERSION, {})}] ({self.base_value})")
        for modifier in self.modifiers:
            lines.append(modifier.format(self, indent + 2))
        return "\n".join(lines)

cdef class StatDescUnit:
    cdef:
        bint is_pure_value
        # is_pure_value=True时value为要加的数值
        # is_pure_value=False且is_func=False时value为要乘的数值
        double value
        bool is_stat
        Stat stat
        str stat_name
        Item filter
        bint is_func
        StatDescFunc func

    def __init__(self, bint is_pure_value, double value, bint is_stat, Stat stat, str stat_name, Item filter, bint is_func, StatDescFunc func):
        self.is_pure_value = is_pure_value
        self.value = value
        self.is_stat = is_stat
        self.stat = stat
        self.stat_name = stat_name
        self.filter = filter
        self.is_func = is_func
        self.func = func
    
    cdef double _calculate(self, Item target, dict kwargs):
        cdef:
            Stat stat
            double stat_value
        if self.is_pure_value:
            return self.value
        if self.is_stat:
            stat = self.stat
        else:
            stat = target.stats[self.stat_name]
        stat_value = stat._calculate(self.filter, kwargs)
        if self.is_func:
            return self.func.call(stat_value, **kwargs)
        return stat_value * self.value
    
    cdef StatDescUnit _scale(self, double scale):
        if self.is_pure_value or not self.is_func:
            return StatDescUnit(self.is_pure_value, self.value * scale, self.is_stat, self.stat, self.stat_name, self.filter,
                self.is_func, self.func)
        return StatDescUnit(self.is_pure_value, self.value, self.is_stat, self.stat, self.stat_name, self.filter,
            self.is_func, self.func.scale(scale))
    
    def format(self, Item target, int indent=0):
        cdef:
            str stat_name
            double value
        if self.is_pure_value:
            return " " * indent + str(self.value)
        if self.is_stat:
            stat_name = f"{self.stat.target.nameid}.{self.stat.name}"
        else:
            stat_name = f"*.{self.stat_name}"
        value = self._calculate(target, {})
        if self.is_func:
            return " " * indent + f"{value} <stat={stat_name}, filter={self.filter.nameid}, func>"
        return " " * indent + f"{value} <stat={stat_name}, filter={self.filter.nameid}, scale={self.value}>"

cdef class StatDesc:
    cdef:
        list units
    
    def __init__(self, tuple desc=None):
        self.units = []
        if desc is not None:
            self._to_unit(desc)
    
    cdef _to_unit(self, tuple desc):
        cdef:
            tuple d
            object stat, func
            Py_ssize_t i, n
            StatDescUnit unit
        # desc必须是元组
        # 每个元素的格式是(stat, filter, func)
        # stat为None时func()作为offset，此时filter也为None
        # stat不为None时func()作为scale
        # func必须是数或StatDescFunc，当func为数时直接取该值
        if type(desc[0]) is not tuple:
            desc = (desc,)
        n = PyTuple_GET_SIZE(desc)
        for i in range(n):
            d = <tuple>PyTuple_GET_ITEM(desc, i)
            stat = <object>PyTuple_GET_ITEM(d, 0)
            if stat is None:
                unit = StatDescUnit(True, <object>PyTuple_GET_ITEM(d, 2), False, None, None, None, False, None)
            elif type(stat) is Stat:
                func = <object>PyTuple_GET_ITEM(d, 2)
                if isinstance(func, StatDescFunc):
                    unit = StatDescUnit(False, 0, True, stat, None, <Item>PyTuple_GET_ITEM(d, 1), True, func)
                else:
                    unit = StatDescUnit(False, func, True, stat, None, <Item>PyTuple_GET_ITEM(d, 1), False, None)
            else:
                func = <object>PyTuple_GET_ITEM(d, 2)
                if isinstance(func, StatDescFunc):
                    unit = StatDescUnit(False, 0, False, None, stat, <Item>PyTuple_GET_ITEM(d, 1), True, func)
                else:
                    unit = StatDescUnit(False, func, False, None, stat, <Item>PyTuple_GET_ITEM(d, 1), False, None)
            self.add(unit)
    
    cpdef void add(self, StatDescUnit unit):
        self.units.append(unit)
    
    cdef double _calculate(self, Item target, dict kwargs):
        cdef:
            double result = 0
            StatDescUnit unit
            Py_ssize_t i, n = PyList_GET_SIZE(self.units)
        for i in range(n):
            unit = <StatDescUnit>PyList_GET_ITEM(self.units, i)
            result += unit._calculate(target, kwargs)
        return result
    
    def calculate(self, Item target=None, **kwargs):
        return self._calculate(target, kwargs)
    
    cdef double _calculate_self_conversion(self, Stat stat, Item target, dict kwargs):
        # 只计算自身转化得到的值
        cdef:
            double result = 0
            StatDescUnit unit
            Py_ssize_t i, n = PyList_GET_SIZE(self.units)
        for i in range(n):
            unit = <StatDescUnit>PyList_GET_ITEM(self.units, i)
            if unit.is_pure_value:
                result += unit.value
            elif (unit.is_stat and unit.stat is stat) or (not unit.is_stat and unit.stat_name == stat.name):
                result += unit._calculate(target, kwargs)
        return result
    
    def calculate_self_conversion(self, Stat stat, Item target=None, **kwargs):
        return self._calculate_self_conversion(stat, target, kwargs)
    
    cpdef StatDesc scale(self, double scale):
        cdef:
            StatDesc result = StatDesc()
            StatDescUnit unit
            Py_ssize_t i, n = PyList_GET_SIZE(self.units)
        for i in range(n):
            unit = <StatDescUnit>PyList_GET_ITEM(self.units, i)
            result.add(unit._scale(scale))
        return result
    
    def format(self, Item target, int indent=0):
        cdef:
            list lines = []
        for unit in self.units:
            lines.append(unit.format(target, indent))
        return "\n".join(lines)

cdef class StatDescFunc:
    cdef dict __dict__

    def call(self, double value, **kwargs):
        raise NotImplementedError
    
    def scale(self, double scale):
        return self

cdef class Modifier(Item):
    cdef public:
        StatDesc stat_desc
        object validator
    
    def __init__(self, str nameid, str name, StatDesc stat_desc, object validator=None, Item master=None):
        super().__init__(nameid, name, master)
        self.stat_desc = stat_desc
        self.validator = validator
    
    cdef double _modify(self, Stat stat, Item filter, dict kwargs):
        # filter一定不为ModifierFilter.BASE
        if self.validator is not None and not self.validator(stat, **kwargs):
            return 0
        if filter is ModifierFilter.CALCULATED:
            return self.stat_desc._calculate(stat.target, kwargs)
        return self.stat_desc._calculate_self_conversion(stat, stat.target, kwargs)
    
    def format(self, Stat stat, int indent=0):
        cdef:
            list lines = []
        if self.validator is not None:
            lines.append(" " * indent + f"{self.name} ({self.nameid}) <validator={self.validator(stat)}>")
        else:
            lines.append(" " * indent + f"{self.name} ({self.nameid})")
        lines.append(self.stat_desc.format(stat.target, indent + 2))
        return "\n".join(lines)
