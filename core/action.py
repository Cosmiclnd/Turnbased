import item
import battle
import server

order = 0

def next_order():
    global order
    order += 1
    return order

class NormalTurn(item.Item):
    def __init__(self, t, actions=1):
        super().__init__(f"{t.nameid}_normal_turn", f"{t.name}'s Normal Turn", item.DeadToggle(t))
        self.target = t
        self.actions = actions
        self.next_run()
    
    def base_action_value(self):
        return 10000 / self.spd
    
    def refresh(self):
        spd = self.target.stats["spd"].calculate()
        if spd != self.spd:
            self.action_value *= self.spd / spd
            self.spd = spd
    
    def next_run(self):
        self.spd = self.target.stats["spd"].calculate()
        self.action_value = self.base_action_value()
        self.order = next_order()
    
    def advance(self, scale):
        self.action_value = max(0, self.action_value - self.base_action_value() * scale)
    
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
        return (self.action_value, -self.order)
    
    @classmethod
    def next_order(cls):
        cls.order += 1
        return cls.order

class ExtraTurn(item.Item):
    class Priority:
        ULTIMATE = 0
        FOLLOW_UP = 1

    def __init__(self, t, priority):
        super().__init__(f"{t.nameid}_extra_turn", f"{t.name}'s Extra Turn", item.DeadToggle(t))
        self.target = t
        self.priority = priority
        self.order = next_order()
    
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
        return await battle.current.check_targets()
    
    async def check_extra_turns(self):
        while self.extras:
            extra = self.extras.pop(0)
            await battle.current.event_bus.dispatch("extra_turn", extra)
            await self.ask_ultimate()
            if await self.refresh_targets():
                return True
        return False
    
    async def ask_ultimate(self):
        while True:
            message = await server.send_and_recv({"type": "ask_ultimate"})
            if message["type"] == "ask_ultimate":
                c = battle.current.characters[message["index"]]
                if c.ultimate_available():
                    await battle.current.event_bus.dispatch("prepare_ultimate", c)
            elif message["type"] == "empty":
                break
    
    async def next_normal_turn(self):
        if await self.refresh_targets():
            return
        current = self.normals[0]
        delta = current.action_value
        for turn in self.normals:
            turn.action_value -= delta
        await battle.current.event_bus.dispatch("normal_turn_start", current)
        for i in range(current.actions + 1):
            if i != 0:
                if i == 1:
                    current.next_run()
                await battle.current.event_bus.dispatch("normal_turn", current)
            if await self.refresh_targets():
                return
            await self.ask_ultimate()
            if await self.check_extra_turns():
                return
        await battle.current.event_bus.dispatch("normal_turn_end", current)
    
    def print(self):
        for turn in self.extras:
            print(f"{turn.name} ({turn.nameid}) <extra>")
        for turn in self.normals:
            print(f"{turn.name} ({turn.nameid}) - {turn.action_value}")
