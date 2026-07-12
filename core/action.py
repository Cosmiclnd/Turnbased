import uuid
import math

import item
import battle
import server
import event

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
    
    async def next_run(self):
        self.spd = self.spd_stat.calculate()
        self.action_value = self.base_action_value()
        self.order = next_order()
        if self.next_advance > 0:
            await battle.current.event_bus.dispatch("action_advance", self, self.next_advance)
        elif self.next_advance < 0:
            await battle.current.event_bus.dispatch("action_delay", self, -self.next_advance)
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

        battle.current.event_bus.add_member_listener(self.action_advance, nameid="action_list", name="Action List")
        battle.current.event_bus.add_member_listener(self.action_delay, nameid="action_list", name="Action List")

        server.handler.add_answer_handler("action_order", self.respond_action_order)
    
    def refresh_turns(self):
        self.normals.refresh()
        self.normals.sort(key=NormalTurn.sort_key)
        self.extras.refresh()
        self.extras.sort(key=ExtraTurn.sort_key)
    
    async def refresh_targets(self):
        for turn in self.normals:
            turn.refresh()
        self.refresh_turns()
        await battle.current.check_targets()
    
    async def check_extra_turns(self):
        while self.extras:
            extra = self.extras.pop(0)
            await battle.current.event_bus.dispatch("extra_turn", extra)
            await self.refresh_targets()
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
            import target  # TODO: Python 3.15 lazy import
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
    
    async def action_unit_interval(self):
        await self.refresh_targets()
        await self.ask_ultimate()
        await self.check_extra_turns()
    
    async def next_normal_turn(self):
        await self.refresh_targets()
        await self.check_extra_turns()
        current = self.normals[0]
        delta = current.action_value
        for turn in self.normals:
            turn.action_value -= delta
        await battle.current.event_bus.dispatch("normal_turn_start", current)
        current.cur_action = -1  # 回合已经开始但是还没有行动
        num_actions = current.get_num_actions()
        for i in range(num_actions):
            self.refresh_turns()
            if not current.target.can_act() or current is not self.normals[0]:
                break
            await self.action_unit_interval()
            current.cur_action = i
            await battle.current.event_bus.dispatch("normal_turn", current)
        if current is self.normals[0]:
            await current.next_run()
            current.cur_action = None
        await self.action_unit_interval()
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
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def action_advance(self, turn, scale):
        await server.handler.update_client({"name": "action_advance", "scale": scale, "turn": turn.get_info()})
        turn.advance(scale)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def action_delay(self, turn, scale):
        await server.handler.update_client({"name": "action_delay", "scale": scale, "turn": turn.get_info()})
        turn.delay(scale)

    @server.server_responder
    @classmethod
    async def respond_action_order(cls, message):
        self = battle.current.action_list
        self.refresh_turns()
        extras = [turn.get_info() for turn in self.extras]
        normals = [turn.get_info() | {"num_actions": turn.get_num_actions(), "cur_action": turn.cur_action, "action_value": turn.action_value}
            for turn in self.normals]
        return {"extras": extras, "normals": normals}
