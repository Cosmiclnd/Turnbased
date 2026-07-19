from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from ._item cimport Item, ItemList

DEF MAX_STACKS = 32
DEF TRACK_STACKS = False

cdef class Listener(Item):
    cdef readonly:
        object callback
        int priority

    def __init__(self, str nameid, str name, object callback, Item master=None, int priority=0):
        super().__init__(nameid, name, master)
        self.callback = callback
        self.priority = priority

class ListenerPriority:
    START = 1000
    PRE_PROCESS = 100
    EXECUTE = 0
    POST_PROCESS = -100
    END = -1000

cdef class EventInterrupt(Exception):
    cdef readonly:
        str name

    def __init__(self, str name):
        self.name = name

cdef class QueryResult:
    cdef readonly:
        object result

    def __init__(self, object result):
        self.result = result

# 事件有两类
# 一类是瞬时事件，如hit
# 一类是持续事件，如normal_turn_start和normal_turn_end
cdef class EventBus:
    cdef:
        dict listeners
        list stack

    def __init__(self):
        self.listeners = {}
        if TRACK_STACKS:
            self.stack = []
    
    cdef void _add_listener(self, str event_name, Listener listener):
        if event_name not in self.listeners:
            self.listeners[event_name] = ItemList()
        self.listeners[event_name].append(listener)
        self.listeners[event_name].sort(key=lambda x: x.priority, reverse=True)
    
    def add_member_listener(self, object member_func, Item master=None, str nameid=None, str name=None, bint unique=False):
        # member_func必须是被@member_listener装饰的成员函数
        if unique:
            for listener in self.listeners[member_func.name]:
                if listener.callback.__func__ is member_func.__func__:
                    return
        nameid = nameid or master.nameid
        name = name or master.name
        self._add_listener(member_func.name, Listener(nameid, name, member_func, master, member_func.priority))
    
    add_member_resolver = add_member_listener
    
    def dispatch(self, str event_name, *args, **kwargs):
        cdef:
            ItemList listeners
            list items
            Listener listener
            Py_ssize_t i, n
            bint dirty = False
        if event_name in self.listeners:
            listeners = <ItemList>self.listeners[event_name]
            items = listeners.items[:]
            n = PyList_GET_SIZE(items)
            for i in range(n):
                listener = <Listener>PyList_GET_ITEM(items, i)
                if listener.dead():
                    dirty = True
                    continue
                if TRACK_STACKS:
                    self.stack.append((event_name, listener))
                    if len(self.stack) > MAX_STACKS:
                        raise RuntimeError(f"Max event stack depth exceeded: {len(self.stack)}")
                try:
                    listener.callback(*args, **kwargs)
                except EventInterrupt as e:
                    if e.name != event_name:
                        if TRACK_STACKS:
                            self.stack.pop()
                        if dirty:
                            listeners.refresh()
                        raise
                    else:
                        if TRACK_STACKS:
                            self.stack.pop()
                        break
                if TRACK_STACKS:
                    self.stack.pop()
            if dirty:
                listeners.refresh()
    
    def query(self, str event_name, *args, **kwargs):
        cdef:
            ItemList listeners
            list items
            Listener listener
            Py_ssize_t i, n
            bint dirty = False
        if event_name in self.listeners:
            listeners = <ItemList>self.listeners[event_name]
            items = listeners.items[:]
            n = PyList_GET_SIZE(items)
            for i in range(n):
                listener = <Listener>PyList_GET_ITEM(items, i)
                if listener.dead():
                    dirty = True
                    continue
                if TRACK_STACKS:
                    self.stack.append((event_name, listener))
                    if len(self.stack) > MAX_STACKS:
                        raise RuntimeError(f"Max event stack depth exceeded: {len(self.stack)}")
                try:
                    result = listener.callback(*args, **kwargs)
                    if type(result) is QueryResult:
                        if TRACK_STACKS:
                            self.stack.pop()
                        if dirty:
                            listeners.refresh()
                        return result.result
                except EventInterrupt as e:
                    if e.name != event_name:
                        if TRACK_STACKS:
                            self.stack.pop()
                        if dirty:
                            listeners.refresh()
                        raise
                    else:
                        if TRACK_STACKS:
                            self.stack.pop()
                        break
                if TRACK_STACKS:
                    self.stack.pop()
            if dirty:
                listeners.refresh()
    
    def interrupt(self, str name):
        raise EventInterrupt(name)
    
    def format_stack(self):
        msg = "Event stack (most recent dispatch last):"
        for event_name, listener in self.stack:
            msg += f"\n  {event_name} -> {listener.name} ({listener.nameid})"
        return msg

def member_listener(int priority, name=None):
    def decorator(object func):
        func.priority = priority
        func.name = name if name else func.__name__
        return func
    return decorator

member_resolver = member_listener  # 用于提示语义
