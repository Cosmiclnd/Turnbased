import random
import uuid

from . import event
from . import event_types
from . import action
from . import item
from . import target
from . import modifier
from . import enums
from . import features
from .decision import base as decision
from .monsters import base as monster

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
    
    def rate(self, rate):
        if self.use_random:
            return self.random.random() < rate
        return decision.provider.provide_random_rate()
    
    def character_target(self, choices):
        if self.use_random:
            return self.random.choice(choices)
        return decision.provider.provide_random_character_target()
    
    def monster_target(self, choices, weights):
        if self.use_random:
            return self.random.choices(choices, weights=weights)[0]
        return decision.provider.provide_random_monster_target()

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
        self.event_bus = event.EventBusLegacy()
        event.bus = event.EventBus()  # 确保每场战斗都是新的EventBus
        self.action_list = None
        self.skillpoints = Skillpoints()
        self.characters = item.ItemList()
        self.monsters = item.ItemList()
        self.monster_setup = monster.Setup()
        self.cur_main_target = None
        self.suspended = False

        event.bus.add_member_listener(self.battle_start, None, nameid="battle", name="Battle")
        event.bus.add_member_listener(self.reset_action_list, None, nameid="battle", name="Battle")
        event.bus.add_member_listener(self.check_techniques, None, nameid="battle", name="Battle")
        event.bus.add_member_listener(self.add_monster, None, nameid="battle", name="Battle")
        event.bus.add_member_listener(self.normal_turn_start_message, None, nameid="battle", name="Battle")
        event.bus.add_member_listener(self.skill_trigger_message, None, nameid="battle", name="Battle")
    
    def type(self):
        return self.config["type"]
    
    def count_monsters(self):
        return sum(1 for m in self.monsters if m.countable())
    
    def all_targets(self):
        return self.characters.concat(self.monsters)
    
    def finish(self, win):
        self.action_list.clear()
        if win:
            decision.provider.notify({"name": "battle_win"})
        else:
            decision.provider.notify({"name": "battle_lose"})
        decision.provider.stop(win)
    
    def check_targets(self):
        if self.monster_setup.check():
            self.finish(True)
        if not self.characters:
            self.finish(False)
    
    def refresh(self):
        self.characters.refresh()
        self.monsters.refresh()
        self.check_targets()
    
    def start(self):
        decision.provider.on_battle_start()  # 必须单独通知，因为provider初始化比event_bus早
        event.bus.dispatch(event_types.BattleStart())
        while True:
            self.action_list.next_normal_turn()
    
    @event.member_listener(event_types.BattleStart.INIT_WAVE)
    def battle_start(self, e):
        for t in self.characters:
            self.action_list.normals.append(t.new_normal_turn())
        self.monster_setup.check()
    
    @event.member_listener(event_types.NewWave.RESET)
    def reset_action_list(self, e):
        self.action_list.reset()
    
    @event.member_listener(event_types.BattleStart.START)
    def check_techniques(self, e):
        for c in self.characters:
            c.check_technique()
    
    @event.member_listener(event_types.AddMonster.EXECUTE)
    def add_monster(self, e):
        self.monsters.append(e.target)
        turn = e.target.new_normal_turn()
        self.action_list.normals.append(turn)
        if e.target.first_turn_delay != 1:
            turn.advance(1 - e.target.first_turn_delay)
    
    @event.member_listener(event_types.NormalTurn.Start.MESSAGE)
    def normal_turn_start_message(self, e):
        if isinstance(e.turn, target.Target.NormalTurn):
            decision.provider.notify({"name": "normal_turn_start", "target": str(e.turn.target.uuid)})
    
    @event.member_listener(event_types.SkillTrigger.MESSAGE)
    def skill_trigger_message(self, e):
        decision.provider.notify({"name": "skill_trigger", "target": str(e.skill.target.uuid), "skill": e.skill.nameid})

current = None
