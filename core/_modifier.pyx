from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM

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
        object target
        double base_value
        ItemList modifiers
    
    def __cinit__(self, str name, object target=None):
        self.name = name
        self.target = target
        self.base_value = 0
        self.modifiers = ItemList()
    
    cdef _calculate(self, Item filter, dict kwargs):
        if filter is ModifierFilter.BASE:
            return self.base_value
        calculated_value = self.base_value
        self.modifiers.refresh()
        for modifier in self.modifiers:
            #modifier = <Modifier>item
            calculated_value += modifier.modify(self, filter, **kwargs)
        return calculated_value
    
    def calculate(self, Item filter=ModifierFilter.CALCULATED, **kwargs):
        return self._calculate(filter, kwargs)
    
    #def print(self, int indent=0):
    #    print(" " * indent +
    #        f"{self.target.nameid}.{self.name}: {self.calculate()} [{self.calculate(ModifierFilter.SELF_CONVERSION)}] ({self.base_value})")
    #    for modifier in self.modifiers:
    #        modifier.print(self, indent + 2)
