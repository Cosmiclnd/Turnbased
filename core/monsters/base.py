import json
import uuid

from .. import target
from .. import skill
from .. import event
from .. import event_types
from .. import battle
from .. import config
from .. import enums
from .. import effect
from .. import item
from ..decision import base as decision

class AdditionalWeakness(item.Item):
    def __init__(self, nameid, name, adder, t, element, master=None):
        super().__init__(nameid, name, master)
        self.adder = adder
        self.target = t
        self.element = element

class WeaknessList:
    def __init__(self, t):
        self.target = t
        self.base = []
        self.additions = item.ItemList()
    
    def has_weakness(self, element):
        if element is None or element in self.base:
            return True
        self.additions.refresh()
        for a in self.additions:
            if a.element is element:
                return True
        return False

class Monster(target.Target):
    class Tier(enums.Enum):
        NORMAL = item.Item("normal", "Normal")
        ELITE = item.Item("elite", "Elite")
        BOSS = item.Item("boss", "Boss")
        EOW = item.Item("eow", "Echo of War")
        ALL = (NORMAL, ELITE, BOSS, EOW)
    Tier.init()

    class MonsterConfig(target.Target.TargetConfig):
        __slots__ = ("base_stat_scales", "base_stat_flats")

        def __init__(self, data, stat_scales, stat_flats, t):
            super().__init__(data, t)
            self.base_stat_scales = stat_scales
            self.base_stat_flats = stat_flats
        
        def init(self):
            self.target.tier = Monster.Tier.dict_nameid[self.data["tier"]]
            self.target.first_turn_delay = self.data["first_turn_delay"]
        
        def set_base_stats(self):
            self.target.weaknesses.base = list(map(lambda x: enums.Element.dict_nameid[x], self.data["weakness"]))
            for stat_name in ("hp", "atk", "def", "spd"):
                self.target.stats[stat_name].base_value = self.get_base_stat(
                    stat_name, self.target.level, self.target.moc) * self.data["base_stat_scales"][stat_name]
            for stat_name in ("eff_hr", "eff_res"):
                self.target.stats[stat_name].base_value = self.get_base_stat(
                    stat_name, self.target.level, self.target.moc) + self.data["base_stat_flats"][stat_name]
            for element in enums.Element.ALL:
                self.target.stats[f"{element.nameid}_res"].base_value = self.data["base_dmg_res"][element.nameid]
            for debuff in effect.Debuff.ALL:
                self.target.stats[f"{debuff.nameid}_res"].base_value = self.data["base_debuff_res"][debuff.nameid]
            self.target.stats["toughness"].base_value = self.data["toughness"]
            for stat, value in self.base_stat_scales.items():
                self.target.stats[stat].base_value *= value
            for stat, value in self.base_stat_flats.items():
                self.target.stats[stat].base_value += value
    
        def get_base_stat(self, name, level, moc):
            if name == "def":
                return 200 + min(level, 100) * 10
            curve = config.load_config_data("monsters", "level_curve")["3" if moc else "1"]
            return curve[name][level - 1]

    class MonsterSkill(skill.Skill):
        def __init__(self, t, skill_name):
            self.skill_name = skill_name
            config_data = t.config.data["skills"][skill_name]
            nameid, name = t.config.get_skill_name(skill_name)
            type = skill.SkillType.dict_nameid[config_data["type"]]
            super().__init__(nameid, name, type, t)
        
        def get_value(self, name):
            return self.target.config.get_skill_value(self.skill_name, name)

    def __init__(self, uuid, nameid, level, moc, stat_scales, stat_flats):
        self.config = self.MonsterConfig(config.load_config_data("monsters", nameid), stat_scales, stat_flats, self)
        if nameid != self.config.nameid:
            logging.warning(f"Monster nameid mismatch: {nameid} != {self.config['nameid']}")

        super().__init__(uuid, nameid, self.config.name, level)
        self.config.init()
        self.moc = moc
        self.weaknesses = WeaknessList(self)
        self.stats.new_stats(["toughness", "toughness_vulnerability"], self)
        self.skills = skill.SkillGroup(self)
        self.cur_toughness = 0
        self.weakness_broken = False

        event.bus.add_member_listener(self.target_action, self, self)
        event.bus.add_member_listener(self.reduce_toughness, None, self)
        event.bus.add_member_listener(self.check_weakness_break, None, self)
        event.bus.add_member_listener(self.weakness_break, None, self)
        event.bus.add_member_listener(self.toughness_recover, self, self)
        event.bus.add_member_listener(self.killed_energy_regen, self, self)
        event.bus.add_member_resolver(self.get_monster_skill_target, self, self)

        self.config.set_base_stats()

    def init_skills(self, skill_classes):
        for i, skill in enumerate(skill_classes):
            self.skills.add(skill(self, f"skill{i + 1}"))
    
    def countable(self):
        return True
    
    @event.member_listener(override=target.Target.set_initial_state)
    def set_initial_state(self, e):
        # 这个listener在Target类中已经被添加
        super().set_initial_state(e)
        self.cur_toughness = self.stats["toughness"].calculate()
    
    @event.member_listener(event_types.TargetAction.EXECUTE)
    def target_action(self, e):
        if self.weakness_broken:
            event.bus.dispatch(event_types.RecoverToughness(self))
        event.bus.dispatch(event_types.SkillGroupTrigger(self.skills))
    
    @event.member_listener(event_types.ReduceToughness.EXECUTE)
    def reduce_toughness(self, e):
        if self is not e.tr.target:
            return
        amount = e.tr.calculate()
        decision.provider.notify({"name": "reduce_toughness", "dealer": str(e.tr.dealer.uuid), "target": str(self.uuid),
            "amount": amount})
        self.cur_toughness -= amount

    @event.member_listener(event_types.ReduceToughness.CHECK)
    def check_weakness_break(self, e):
        if self is not e.tr.target:
            return
        if self.cur_toughness <= 0:
            self.cur_toughness = 0
            if not self.weakness_broken:
                event.bus.dispatch(event_types.BreakWeakness(e.tr))
    
    @event.member_listener(event_types.BreakWeakness.BREAK)
    def weakness_break(self, e):
        if self is not e.tr.target:
            return
        decision.provider.notify({"name": "weakness_break", "target": str(self.uuid)})
        self.weakness_broken = True
    
    @event.member_listener(event_types.RecoverToughness.EXECUTE)
    def toughness_recover(self, e):
        self.cur_toughness = self.stats["toughness"].calculate()
        self.weakness_broken = False
    
    @event.member_listener(event_types.Clean.ENERGY)
    def killed_energy_regen(self, e):
        # TODO: config?
        event.bus.dispatch(event_types.RegenEnergy(self.death_state.killing_dmg.dealer, 10))

    @event.member_resolver(event_types.GetMonsterSkillTarget.DEFAULT)
    def get_monster_skill_target(self, e):
        targets = [c for c in battle.current.characters if c.death_state.alive]
        if not targets:
            return
        taunts = [c.stats["taunt"].calculate() for c in targets]
        return event.QueryResult(battle.current.random.monster_target(targets, taunts))

class Group:
    def __init__(self, name, record):
        self.name = name
        self.monsters = []
        self.condition = []
        self.summoned = False
        self.set_record(record)
    
    def set_record(self, record):
        for monster in record["monsters"]:
            self.monsters.append(config.load_class("monsters", monster["name"])(uuid.UUID(monster["uuid"]), monster["level"], monster["moc"],
                monster.get("stat_scales", {}), monster.get("stat_flats", {})))
        self.condition = record["condition"]
    
    def all_cleared(self):
        for monster in self.monsters:
            if not monster.dead():
                return False
        return True
    
    def check_condition(self):
        for condition in self.condition:
            if not battle.current.monster_setup.current_wave().groups[condition].all_cleared():
                return False
        return True

class Wave:
    def __init__(self, record):
        self.groups = {}
        self.set_record(record)
    
    def set_record(self, record):
        for name, group in record.items():
            self.groups[name] = Group(name, group)
    
    def check(self):
        result = []
        for group in self.groups.values():
            if not group.summoned and group.check_condition():
                result.append(group)
                group.summoned = True
        return result

class Setup:
    def __init__(self):
        self.waves = []
        self.monster_queue = []
        self.cur_wave = -1
    
    def current_wave(self):
        return self.waves[self.cur_wave]
    
    def set_record(self, record):
        for wave in record:
            self.waves.append(Wave(wave))
    
    def check_add_monsters(self):
        for group in self.current_wave().check():
            for monster in group.monsters:
                self.monster_queue.append(monster)
        added = False
        while battle.current.count_monsters() < 5:
            if len(self.monster_queue) == 0:
                break
            event.bus.dispatch(event_types.AddMonster(self.monster_queue.pop(0)))
            added = True
        if added:
            battle.current.action_list.refresh_targets()
    
    def check(self):
        if self.cur_wave >= 0:
            self.check_add_monsters()
        if not battle.current.monsters:
            self.cur_wave += 1
            if self.cur_wave >= len(self.waves):
                return True
            self.check_add_monsters()
            decision.provider.notify({"name": "new_wave", "wave": self.cur_wave + 1, "total": len(self.waves)})
            event.bus.dispatch(event_types.NewWave())
        return False
