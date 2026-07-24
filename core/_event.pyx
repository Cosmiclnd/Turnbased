from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from ._item cimport Item, ItemList

DEF MAX_STACKS = 32
DEF TRACK_STACKS = False

cdef class Period:
    pass

cdef class Event:
    cdef readonly:
        type period
        object main_arg

    def __init__(self, type period, object main_arg):
        self.period = period
        self.main_arg = main_arg

cdef class EventStage:
    cdef readonly:
        type event_cls
        int value
    
    def __init__(self, type event_cls, int stage):
        self.event_cls = event_cls
        self.value = stage

cdef class EventInterrupt(Exception):
    cdef readonly:
        type event_cls
    
    def __init__(self, type event_cls):
        self.event_cls = event_cls

cdef class QueryResult:
    cdef readonly:
        object result

    def __init__(self, object result):
        self.result = result

cdef class Listener(Item):
    cdef readonly:
        object callback
        int stage

    def __init__(self, str nameid, str name, object callback, int stage, Item master=None):
        super().__init__(nameid, name, master)
        self.callback = callback
        self.stage = stage

cdef class EventBus:
    cdef:
        dict grouped_listeners, all_listeners, periods
    
    def __init__(self):
        self.grouped_listeners = {}
        self.all_listeners = {}
        self.periods = {}

    cdef void _add_listener(self, type event_cls, Listener listener, object main_arg):
        cdef:
            dict groups
            ItemList grouped_listeners, all_listeners
        groups = self.grouped_listeners.setdefault(event_cls, {})
        grouped_listeners = groups.setdefault(main_arg, ItemList())
        grouped_listeners.append(listener)
        grouped_listeners.sort(key=lambda x: x.stage)
        all_listeners = self.all_listeners.setdefault(event_cls, ItemList())
        all_listeners.append(listener)
        all_listeners.sort(key=lambda x: x.stage)
    
    def add_member_listener(self, object member_func, object main_arg, Item master=None, str nameid=None, str name=None, bint unique=False):
        # member_func必须是被@member_listener装饰的成员函数
        cdef:
            Listener listener
        nameid = master.nameid if nameid is None else nameid
        name = master.name if name is None else name
        listener = Listener(nameid, name, member_func, member_func.stage.value, master)
        if unique:
            for l in self.grouped_listeners[member_func.stage.event_cls][main_arg]:
                if l.callback.__func__ is member_func.__func__:
                    return
        self._add_listener(member_func.stage.event_cls, listener, main_arg)
    
    add_member_resolver = add_member_listener

    cdef void _call_merge_listeners(self, Event event, ItemList listeners1, ItemList listeners2):
        # 类似归并
        # 总是取出两个列表中优先级较大的调用
        cdef:
            list items1, items2
            Listener listener1, listener2
            Py_ssize_t i1 = 0, i2 = 0, n1, n2
            bint dirty1 = False, dirty2 = False
        items1 = listeners1.items
        items2 = listeners2.items
        n1 = PyList_GET_SIZE(items1)
        n2 = PyList_GET_SIZE(items2)
        while i1 < n1 and i2 < n2:
            listener1 = <Listener>PyList_GET_ITEM(items1, i1)
            listener2 = <Listener>PyList_GET_ITEM(items2, i2)
            if listener1.stage < listener2.stage:
                if not listener1.dead():
                    listener1.callback(event)
                else:
                    dirty1 = True
                i1 += 1
            elif listener1.stage > listener2.stage:
                if not listener2.dead():
                    listener2.callback(event)
                else:
                    dirty2 = True
                i2 += 1
            else:
                if not listener1.dead():
                    listener1.callback(event)
                else:
                    dirty1 = True
                if not listener2.dead():
                    listener2.callback(event)
                else:
                    dirty2 = True
                i1 += 1
                i2 += 1
        while i1 < n1:
            listener1 = <Listener>PyList_GET_ITEM(items1, i1)
            if not listener1.dead():
                listener1.callback(event)
            else:
                dirty1 = True
            i1 += 1
        while i2 < n2:
            listener2 = <Listener>PyList_GET_ITEM(items2, i2)
            if not listener2.dead():
                listener2.callback(event)
            else:
                dirty2 = True
            i2 += 1
        if dirty1:
            listeners1.refresh()
        if dirty2:
            listeners2.refresh()
    
    cdef void _call_listeners(self, Event event, ItemList listeners):
        cdef:
            list items
            Listener listener
            Py_ssize_t i, n
            bint dirty = False
        items = listeners.items
        n = PyList_GET_SIZE(items)
        for i in range(n):
            listener = <Listener>PyList_GET_ITEM(items, i)
            if not listener.dead():
                listener.callback(event)
            else:
                dirty = True
        if dirty:
            listeners.refresh()

    cdef object _call_merge_resolvers(self, Event event, ItemList listeners1, ItemList listeners2):
        cdef:
            list items1, items2
            Listener listener1, listener2
            object result = None
            Py_ssize_t i1 = 0, i2 = 0, n1, n2
            bint dirty1 = False, dirty2 = False
        items1 = listeners1.items
        items2 = listeners2.items
        n1 = PyList_GET_SIZE(items1)
        n2 = PyList_GET_SIZE(items2)
        while i1 < n1 and i2 < n2 and type(result) is not QueryResult:
            listener1 = <Listener>PyList_GET_ITEM(items1, i1)
            listener2 = <Listener>PyList_GET_ITEM(items2, i2)
            if listener1.stage < listener2.stage:
                if not listener1.dead():
                    result = listener1.callback(event)
                else:
                    dirty1 = True
                i1 += 1
            elif listener1.stage > listener2.stage:
                if not listener2.dead():
                    result = listener2.callback(event)
                else:
                    dirty2 = True
                i2 += 1
            else:
                if not listener1.dead():
                    result = listener1.callback(event)
                else:
                    dirty1 = True
                if not listener2.dead() and type(result) is not QueryResult:
                    result = listener2.callback(event)
                else:
                    dirty2 = True
                i1 += 1
                i2 += 1
        while i1 < n1 and type(result) is not QueryResult:
            listener1 = <Listener>PyList_GET_ITEM(items1, i1)
            if not listener1.dead():
                result = listener1.callback(event)
            else:
                dirty1 = True
            i1 += 1
        while i2 < n2 and type(result) is not QueryResult:
            listener2 = <Listener>PyList_GET_ITEM(items2, i2)
            if not listener2.dead():
                result = listener2.callback(event)
            else:
                dirty2 = True
            i2 += 1
        if dirty1:
            listeners1.refresh()
        if dirty2:
            listeners2.refresh()
        if type(result) is QueryResult:
            return result.result
    
    cdef object _call_resolvers(self, Event event, ItemList listeners):
        cdef:
            list items
            Listener listener
            object result
            Py_ssize_t i, n
            bint dirty = False
        items = listeners.items
        n = PyList_GET_SIZE(items)
        for i in range(n):
            listener = <Listener>PyList_GET_ITEM(items, i)
            if not listener.dead():
                result = listener.callback(event)
            else:
                dirty = True
            if type(result) is QueryResult:
                break
        if dirty:
            listeners.refresh()
        if type(result) is QueryResult:
            return result.result

    def dispatch(self, Event event):
        cdef:
            dict groups
            ItemList listeners1, listeners2
        if event.period is not None:
            self.periods[event.period] = (event.__class__ is event.period.Start)
        if event.__class__ in self.all_listeners:
            try:
                if event.main_arg is not None:
                    groups = self.grouped_listeners[event.__class__]
                    listeners1 = groups.setdefault(event.main_arg, ItemList())
                    listeners2 = groups.setdefault(None, ItemList())
                    self._call_merge_listeners(event, listeners1, listeners2)
                else:
                    listeners1 = self.all_listeners[event.__class__]
                    self._call_listeners(event, listeners1)
            except EventInterrupt as e:
                if e.event_cls is not event.__class__:
                    raise
    
    def query(self, Event event):
        cdef:
            dict groups
            ItemList resolvers1, resolvers2
        if event.period is not None:
            self.periods[event.period] = (event.__class__ is event.period.Start)
        if event.__class__ in self.all_listeners:
            try:
                if event.main_arg is not None:
                    groups = self.grouped_listeners[event.__class__]
                    resolvers1 = groups.setdefault(event.main_arg, ItemList())
                    resolvers2 = groups.setdefault(None, ItemList())
                    return self._call_merge_resolvers(event, resolvers1, resolvers2)
                else:
                    resolvers1 = self.all_listeners[event.__class__]
                    return self._call_resolvers(event, resolvers1)
            except EventInterrupt as e:
                if e.event_cls is not event.__class__:
                    raise
    
    def is_during(self, type period):
        return self.periods.get(period, False)
    
    def interrupt(self, type event_cls):
        raise EventInterrupt(event_cls)

def member_listener(EventStage stage=None, *, object override=None):
    def wrapper(object member_func):
        member_func.stage = stage
        if override is not None:
            member_func.stage = override.stage
        return member_func
    return wrapper

member_resolver = member_listener
