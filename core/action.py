import uuid

import item
import battle
import server
import target

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
    def __init__(self, t):
        super().__init__(f"{t.nameid}_normal_turn", f"{t.name}'s Normal Turn", item.DeadToggle(t))
        self.target = t
        self.cur_action = None
        self.spd = self.target.stats["spd"].calculate()
        self.action_value = self.base_action_value()
        self.order = next_add_order()
        self.next_scale = 1  # 用于实现“下一次行动提前X%”的效果
    
    def get_num_actions(self):
        return 1
    
    def base_action_value(self):
        return 10000 / self.spd
    
    def refresh(self):
        spd = self.target.stats["spd"].calculate()
        if spd != self.spd:
            self.action_value *= self.spd / spd
            self.spd = spd
    
    def next_run(self):
        self.spd = self.target.stats["spd"].calculate()
        self.action_value = self.next_scale * self.base_action_value()
        self.next_scale = 1
        self.order = next_order()
    
    def advance(self, scale):
        if self.cur_action is None:
            self.action_value = max(0, self.action_value - self.base_action_value() * scale)
        else:
            self.next_scale = max(0, self.next_scale - scale)
    
    def delay(self, scale):
        self.advance(-scale)
    
    @classmethod
    def advance_target(cls, t, scale):
        for turn in battle.current.action_list.normals:
            if t is turn.target:
                turn.advance(scale)
                break
    
    @classmethod
    def delay_target(cls, t, scale):
        cls.advance_target(t, -scale)
    
    def sort_key(self):
        return (self.action_value, self.order)
    
    @classmethod
    def next_order(cls):
        cls.order += 1
        return cls.order

class ExtraTurn(item.Item):
    class Priority:
        NORMAL = 0
        ULTIMATE = 0
        FOLLOW_UP = 1

    def __init__(self, t, priority):
        super().__init__(f"{t.nameid}_extra_turn", f"{t.name}'s Extra Turn", item.DeadToggle(t))
        self.target = t
        self.priority = priority
        self.order = next_add_order()
    
    def sort_key(self):
        return (-self.priority, self.order)
    
    def is_ultimate(self):
        return False
    
    def is_follow_up(self):
        return False

class ActionList:
    def __init__(self):
        self.normals = item.ItemList()
        self.extras = item.ItemList()
    
    async def refresh_targets(self):
        self.normals.refresh()
        for turn in self.normals:
            turn.refresh()
        self.normals.sort(key=NormalTurn.sort_key)
        self.extras.refresh()
        self.extras.sort(key=ExtraTurn.sort_key)
        await battle.current.check_targets()
    
    async def check_extra_turns(self):
        while self.extras:
            extra = self.extras.pop(0)
            await battle.current.event_bus.dispatch("extra_turn", extra)
            await self.ask_ultimate()
            await self.refresh_targets()
    
    @server.server_handler
    async def ultimate_handler(self, message):
        if message.get("type") == "empty":
            return "ok"
        if message.get("type") != "ask" or message.get("name") != "ultimate":
            return "invalid_message_type"
        try:
            id = uuid.UUID(message["character"])
            c = target.from_uuid(id)
            if c is None:
                return "target_not_found"
            from characters import base as character  # TODO: Python 3.15 lazy import
            if not isinstance(c, character.Character):
                return "target_not_character"
            info = await c.check_ultimate(message)
            if info == "ok":
                await battle.current.event_bus.dispatch("prepare_ultimate", c)
                return "ok"
            else:
                return info
        except KeyError:
            return "invalid_message"
        return "internal_error"
    
    async def ask_ultimate(self):
        while True:
            response = await server.handler.ask_client({"name": "ultimate"}, self.ultimate_handler)
            if response["type"] == "empty":
                break
    
    async def next_normal_turn(self):
        await self.refresh_targets()
        await self.check_extra_turns()
        current = self.normals[0]
        delta = current.action_value
        for turn in self.normals:
            turn.action_value -= delta
        await battle.current.event_bus.dispatch("normal_turn_start", current)
        await self.refresh_targets()
        await self.ask_ultimate()
        await self.check_extra_turns()
        for i in range(current.get_num_actions()):
            if not current.target.can_act() or current is not self.normals[0]:
                break
            current.cur_action = i
            await battle.current.event_bus.dispatch("normal_turn", current)
            await self.refresh_targets()
            await self.ask_ultimate()
            await self.check_extra_turns()
        if current is self.normals[0]:
            current.next_run()
        current.cur_action = None
        await battle.current.event_bus.dispatch("normal_turn_end", current)
    
    async def reset(self):
        for turn in self.normals:
            # TODO: order?
            turn.action_value = turn.base_action_value()
        await self.refresh_targets()
    
    def print(self):
        for turn in self.extras:
            print(f"{turn.name} ({turn.nameid}) <extra>")
        for turn in self.normals:
            print(f"{turn.name} ({turn.nameid}) - {turn.action_value}")
