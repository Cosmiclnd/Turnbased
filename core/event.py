import logging

import item

MAX_STACKS = 32

class Listener(item.Item):
    def __init__(self, nameid, name, callback, master=None, priority=0):
        super().__init__(nameid, name, master)
        self.callback = callback
        self.priority = priority

class ListenerPriority:
    START = 1000
    PRE_PROCESS = 100
    EXECUTE = 0
    POST_PROCESS = -100
    END = -1000

class EventInterrupt(Exception):
    def __init__(self, name):
        self.name = name

class QueryResult:
    __slots__ = ("result",)

    def __init__(self, result):
        self.result = result

# 事件有两类
# 一类是瞬时事件，如hit
# 一类是持续事件，如normal_turn_start和normal_turn_end
class EventBus:
    def __init__(self):
        self.listeners = {}
        self.stack = []
    
    def add_listener(self, event_name, listener):
        if event_name not in self.listeners:
            self.listeners[event_name] = item.ItemList()
        self.listeners[event_name].append(listener)
    
    def add_member_listener(self, member_func, master=None, nameid=None, name=None, unique=False):
        # member_func必须是被@member_listener装饰的成员函数
        if unique:
            for listener in self.listeners[member_func.name]:
                if listener.callback.__func__ is member_func.__func__:
                    return
        nameid = nameid or master.nameid
        name = name or master.name
        self.add_listener(member_func.name, Listener(nameid, name, member_func, master, member_func.priority))
    
    add_member_resolver = add_member_listener
    
    async def dispatch(self, event_name, *args, **kwargs):
        if event_name in self.listeners:
            self.listeners[event_name].refresh()
            self.listeners[event_name].sort(key=lambda x: x.priority, reverse=True)
            for listener in self.listeners[event_name]:
                self.stack.append((event_name, listener))
                if len(self.stack) > MAX_STACKS:
                    logging.warning(f"Max event stack depth exceeded: {len(self.stack)}")
                    logging.warning(self.format_stack())
                    self.stack.pop()
                    return
                try:
                    await listener.callback(*args, **kwargs)
                except EventInterrupt as e:
                    if e.name != event_name:
                        self.stack.pop()
                        raise
                self.stack.pop()
        if event_name not in self.listeners or not self.listeners[event_name]:
            logging.warning(f"No listener for event {event_name}")
    
    async def query(self, event_name, *args, **kwargs):
        if event_name in self.listeners:
            self.listeners[event_name].refresh()
            self.listeners[event_name].sort(key=lambda x: x.priority, reverse=True)
            for listener in self.listeners[event_name]:
                self.stack.append((event_name, listener))
                if len(self.stack) > MAX_STACKS:
                    logging.warning(f"Max event stack depth exceeded: {len(self.stack)}")
                    logging.warning(self.format_stack())
                    self.stack.pop()
                    return
                try:
                    result = await listener.callback(*args, **kwargs)
                    if type(result) is QueryResult:
                        self.stack.pop()
                        return result.result
                except EventInterrupt as e:
                    if e.name != event_name:
                        self.stack.pop()
                        raise
                self.stack.pop()
        if event_name not in self.listeners or not self.listeners[event_name]:
            logging.warning(f"No resolver for event {event_name}")
    
    def interrupt(self, name):
        raise EventInterrupt(name)
    
    def format_stack(self):
        msg = "Event stack (most recent dispatch last):"
        for event_name, listener in self.stack:
            msg += f"\n  {event_name} -> {listener.name} ({listener.nameid})"
        return msg

def member_listener(priority=0, name=None):
    def decorator(func):
        func.priority = priority
        func.name = name if name else func.__name__
        return func
    return decorator

member_resolver = member_listener  # 用于提示语义
