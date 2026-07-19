import uuid
import math

from . import item
from . import battle
from . import event
from .decision import base as decision

order = -1
add_order = 0

def next_order():
    global order
    order -= 1
    return order

def next_add_order():
    global add_order
    add_order += 1
    return add_order

class NormalTurn(item.Item):
    def __init__(self, nameid, name, spd_stat, master=None):
        super().__init__(nameid, name, master)
        self.cur_action = None
        self.spd_stat = spd_stat
        self.spd = spd_stat.calculate()
        self.action_value = self.base_action_value()
        self.order = next_add_order()
        self.next_advance = 0  # 用于实现“下一次行动提前X%”的效果
    
    def get_num_actions(self):
        return 1
    
    def base_action_value(self):
        return 10000 / self.spd
    
    def refresh(self):
        spd = self.spd_stat.calculate()
        if spd != self.spd:
            self.action_value *= self.spd / spd
            self.spd = spd
    
    def next_run(self):
        self.spd = self.spd_stat.calculate()
        self.action_value = self.base_action_value()
        self.order = next_order()
        if self.next_advance > 0:
            battle.current.event_bus.dispatch("action_advance", self, self.next_advance)
        elif self.next_advance < 0:
            battle.current.event_bus.dispatch("action_delay", self, -self.next_advance)
        self.next_advance = 0
    
    def advance(self, scale):
        self.action_value = max(0, self.action_value - self.base_action_value() * scale)
    
    def delay(self, scale):
        self.advance(-scale)
    
    def advance_next_turn(self, scale):
        self.next_advance += scale
    
    def delay_next_turn(self, scale):
        self.next_advance -= scale
    
    def sort_key(self):
        if self.cur_action is not None:
            return (self.action_value, -math.inf)
        return (self.action_value, self.order)
    
    def get_info(self):
        return {"name": self.nameid}
    
    @classmethod
    def next_order(cls):
        cls.order += 1
        return cls.order

class ExtraTurn(item.Item):
    class Priority:
        NORMAL = 0
        ULTIMATE = 0
        FOLLOW_UP = 1

    def __init__(self, nameid, name, priority, master=None):
        super().__init__(nameid, name, master)
        self.priority = priority
        self.order = next_add_order()
    
    def sort_key(self):
        return (-self.priority, self.order)
    
    def get_info(self):
        return {"name": self.nameid}
    
    def is_ultimate(self):
        return False
    
    def is_follow_up(self):
        return False

class ActionList:
    def __init__(self):
        self.normals = item.ItemList()
        self.extras = item.ItemList()
        self.cur_action_value = 0

        battle.current.event_bus.add_member_listener(self.action_advance, nameid="action_list", name="Action List")
        battle.current.event_bus.add_member_listener(self.action_delay, nameid="action_list", name="Action List")
    
    def clear(self):
        self.normals.clear()
        self.extras.clear()
    
    def refresh_turns(self):
        self.normals.refresh()
        self.normals.sort(key=NormalTurn.sort_key)
        self.extras.refresh()
        self.extras.sort(key=ExtraTurn.sort_key)
    
    def refresh_targets(self):
        for turn in self.normals:
            turn.refresh()
        self.refresh_turns()
        battle.current.refresh()
    
    def check_extra_turns(self):
        while self.extras:
            extra = self.extras[0]
            battle.current.event_bus.dispatch("extra_turn", extra)
            self.refresh_targets()
            self.ask_ultimate()
            self.refresh_targets()
    
    def ask_ultimate(self):
        while True:
            character = decision.provider.provide_ultimate()
            if character is not None:
                battle.current.event_bus.dispatch("prepare_ultimate", character)
            else:
                break
    
    def action_unit_interval(self):
        self.refresh_targets()
        self.ask_ultimate()
        self.check_extra_turns()
    
    def next_normal_turn(self):
        self.refresh_targets()
        self.check_extra_turns()
        current = self.normals[0]
        delta = current.action_value
        self.cur_action_value += delta
        for turn in self.normals:
            turn.action_value -= delta
        battle.current.event_bus.dispatch("normal_turn_start", current)
        current.cur_action = -1  # 回合已经开始但是还没有行动
        num_actions = current.get_num_actions()
        for i in range(num_actions):
            self.refresh_turns()
            if not current.target.can_act() or current is not self.normals[0]:
                break
            self.action_unit_interval()
            current.cur_action = i
            battle.current.event_bus.dispatch("normal_turn", current)
        if current is self.normals[0]:
            current.next_run()
            current.cur_action = None
        self.action_unit_interval()
        battle.current.event_bus.dispatch("normal_turn_end", current)
    
    def reset(self):
        for turn in self.normals:
            # TODO: order?
            turn.action_value = turn.base_action_value()
        self.refresh_targets()
    
    def print(self):
        for turn in self.extras:
            print(f"{turn.name} ({turn.nameid}) <extra>")
        for turn in self.normals:
            print(f"{turn.name} ({turn.nameid}) - {turn.action_value}")
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    def action_advance(self, turn, scale):
        decision.provider.notify({"name": "action_advance", "scale": scale, "turn": turn.get_info()})
        turn.advance(scale)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    def action_delay(self, turn, scale):
        decision.provider.notify({"name": "action_delay", "scale": scale, "turn": turn.get_info()})
        turn.delay(scale)
