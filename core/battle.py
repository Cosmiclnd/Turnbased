import random
import uuid

import event
import action
import item
import target
import modifier
import server
import enums
import features
from monsters import base as monster

class Skillpoints:
    __slots__ = ("current", "max")

    def __init__(self):
        self.current = 3
        self.max = modifier.Stat("skillpoints")
        self.max.base_value = 5
    
    def refresh(self):
        m = int(self.max.calculate())
        if self.current > m:
            self.current = m
    
    def available(self, delta_skillpoints):
        self.refresh()
        return self.current + delta_skillpoints >= 0
    
    def modify(self, delta_skillpoints):
        self.current += delta_skillpoints
        self.refresh()

class Random:
    def __init__(self, config):
        self.use_random = config["use_random"]
        if self.use_random:
            self.random = random.Random(config.get("seed"))
    
    @server.server_handler
    async def rate_handler(self, message):
        try:
            if type(message["result"]) is not bool:
                return "invalid_message"
            return "ok"
        except KeyError:
            return "invalid_message"
    
    async def rate(self, rate):
        if self.use_random:
            return self.random.random() < rate
        response = await server.handler.ask_client({"name": "random_rate"}, self.rate_handler)
        return response["result"]
    
    @server.server_handler
    async def monster_target_handler(self, message):
        try:
            self.temp_target = target.from_uuid(uuid.UUID(message["result"]))
            if self.temp_target is None:
                return "target_not_found"
            return "ok"
        except KeyError:
            return "invalid_message"
    
    async def monster_target(self, choices, weights):
        if self.use_random:
            return self.random.choices(choices, weights=weights)[0]
        response = await server.handler.ask_client({"name": "random_monster_target"}, self.monster_target_handler)
        return self.temp_target

class BattleType(enums.Enum):
    DEFAULT = item.Item("default", "Default")
    MOC = item.Item("moc", "MoC")
    ALL = (DEFAULT, MOC)
BattleType.init()

class BattleConfig:
    __slots__ = ("type")

    def __init__(self, type):
        self.type = type

class Battle:
    def __init__(self):
        self.random = None
        self.config = None
        self.features = features.Features()
        self.event_bus = event.EventBus()
        self.action_list = None
        self.skillpoints = Skillpoints()
        self.characters = item.ItemList()
        self.monsters = item.ItemList()
        self.monster_setup = monster.Setup()
        self.cur_main_target = None
        self.suspended = False

        self.event_bus.add_member_listener(self.battle_start, nameid="battle", name="Battle")
        self.event_bus.add_member_listener(self.new_wave_start, nameid="battle", name="Battle")
        self.event_bus.add_member_listener(self.check_techniques, nameid="battle", name="Battle")
        self.event_bus.add_member_listener(self.add_monster, nameid="battle", name="Battle")
        self.event_bus.add_member_listener(self.normal_turn_start_message, nameid="battle", name="Battle")
        self.event_bus.add_member_listener(self.skill_trigger_message, nameid="battle", name="Battle")
    
    def type(self):
        return self.config["type"]
    
    def refresh(self):
        self.characters.refresh()
        self.monsters.refresh()
    
    def count_monsters(self):
        return sum(1 for m in self.monsters if m.countable())
    
    def all_targets(self):
        return self.characters + self.monsters
    
    async def check_targets(self):
        if await self.monster_setup.check():
            await server.handler.update_client({"name": "battle_win"})
            await server.handler.flush_updates()
            server.handler.close()
        if not self.characters:
            await server.handler.update_client({"name": "battle_lose"})
            await server.handler.flush_updates()
            server.handler.close()
    
    async def start(self):
        await self.event_bus.dispatch("battle_start")
        while True:
            await self.action_list.next_normal_turn()
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS)
    async def battle_start(self):
        for t in self.characters[::-1]:
            self.action_list.normals.append(t.new_normal_turn())
        await self.monster_setup.check()
    
    @event.member_listener(event.ListenerPriority.EXECUTE - 1)
    async def new_wave_start(self):
        await self.action_list.reset()
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS - 1, "battle_start")
    async def check_techniques(self):
        for c in self.characters:
            await c.check_technique()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def add_monster(self, m):
        self.monsters.append(m)
        turn = m.new_normal_turn()
        self.action_list.normals.append(turn)
        turn.advance(1 - m.first_turn_delay)
    
    @event.member_listener(event.ListenerPriority.START, "normal_turn_start")
    async def normal_turn_start_message(self, turn):
        if not isinstance(turn, target.Target.NormalTurn):
            return
        await server.handler.update_client({"name": "normal_turn_start", "target": str(turn.target.uuid)})
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 2, "skill_trigger")
    async def skill_trigger_message(self, skill):
        await server.handler.update_client({"name": "skill_trigger", "target": str(skill.target.uuid), "skill": skill.nameid})

current = None
