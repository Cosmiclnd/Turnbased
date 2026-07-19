from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM, PyList_Append

from ._item cimport Item, DeadToggle, ItemList

cdef class Item:
    def __init__(self, nameid, name, master=None):
        self.nameid = nameid
        self.name = name
        self.master = master
    
    cpdef bint dead(self):
        return self.master is not None and self.master.dead()
    
    cpdef void on_removed(self, ItemList list):
        pass

cdef class DeadToggle(Item):
    def __init__(self, master=None):
        if master is None:
            Item.__init__(self, master.nameid, master.name, master)
        else:
            Item.__init__(self, "dead_toggle", "Dead Toggle")
        self.dead_toggle = False
    
    cpdef bint dead(self):
        if self.dead_toggle:
            return True
        return Item.dead(self)

cdef class ItemList:
    def __init__(self):
        self.items = []
    
    cpdef void refresh(self):
        cdef:
            Item item
            Py_ssize_t i, n = PyList_GET_SIZE(self.items)
            list alive = []
            list dead = []
        for i in range(n):
            item = <Item>PyList_GET_ITEM(self.items, i)
            if item.dead():
                dead.append(item)
            else:
                alive.append(item)
        n = PyList_GET_SIZE(dead)
        for i in range(n):
            item = <Item>PyList_GET_ITEM(dead, i)
            item.on_removed(self)
        self.items = alive
    
    cpdef void append(self, Item item):
        PyList_Append(self.items, item)
    
    cpdef void extend(self, object list):
        self.items.extend(list)
    
    cpdef Item pop(self, Py_ssize_t index):
        return self.items.pop(index)
    
    cpdef void clear(self):
        self.items.clear()
    
    cpdef void sort(self, object key=None, bint reverse=False):
        if key is None:
            self.items.sort(reverse=reverse)
        else:
            self.items.sort(key=key, reverse=reverse)
    
    def copy(self):
        return self.items[:]
    
    def concat(self, ItemList other):
        return self.items + other.items
    
    def index(self, Item item):
        return self.items.index(item)
    
    def __bool__(self):
        return bool(self.items)
    
    def __len__(self):
        return len(self.items)
    
    def __getitem__(self, Py_ssize_t index):
        return self.items[index]

    def __iter__(self):
        return iter(self.items)
