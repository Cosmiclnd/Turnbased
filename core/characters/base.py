import collections
import json
import uuid

from .. import target
from .. import skill
from .. import event
from .. import event_types
from .. import battle
from .. import config
from .. import enums
from .. import modifier
from .. import damage
from .. import effect
from .. import action
from .. import item
from ..decision import base as decision
from ..relics import base as relic

class Character(target.Target):
    class CharacterConfig(target.Target.TargetConfig):
        __slots__ = ("base_stat_scales", "base_stats", "traces_stats")
        
        def __init__(self, data, t):
            super().__init__(data, t)
            self.base_stat_scales = data["base_stat_scales"]
            self.base_stats = data["base_stats"]
            self.base_stats["crt_rate"] = 0.05
            self.base_stats["crt_dmg"] = 0.5
            self.base_stats["energy_regen_rate"] = 1
            self.traces_stats = data["traces_stats"]
        
        def init(self):
            self.target.rarity = self.data["rarity"]
            self.target.element = enums.Element.dict_nameid[self.data["element"]]
            self.target.path = enums.Path.dict_nameid[self.data["path"]]
        
        def set_base_stats(self):
            scale = 6.35 * (self.target.level - 1) / 79 + 1
            if self.target.rarity == 5:
                scale *= 1.1
            self.target.stats["hp"].base_value = self.base_stat_scales["hp"] * scale * 4.8
            self.target.stats["atk"].base_value = self.base_stat_scales["atk"] * scale * 2.4
            self.target.stats["def"].base_value = self.base_stat_scales["def"] * scale * 3
            for name, value in self.base_stats.items():
                self.target.stats[name].base_value = value
            self.target.stats["base_break_dmg"].base_value = self.get_base_stat("base_break_dmg", self.target.level)
            self.target.auto_battle.ultimate_priority = self.data["auto_battle"]["ultimate_priority"]
        
        def set_traces_stats(self):
            for i in range(len(self.traces_stats)):
                if self.target.traces_stats_unlocked[i]:
                    stat = self.traces_stats[i]
                    if stat["is_percentage"]:
                        stat_desc = modifier.StatDesc((self.target.stats[stat["stat_name"]], modifier.ModifierFilter.BASE, stat["value"]))
                    else:
                        stat_desc = modifier.StatDesc((None, None, stat["value"]))
                    mod = modifier.Modifier(stat["nameid"], stat["name"], stat_desc, None, self.target)
                    self.target.stats[stat["stat_name"]].modifiers.append(mod)
    
        def get_base_stat(self, name, level):
            return config.load_config_data("characters", "level_curve")[name][level - 1]

    class UltimateTurn(target.Target.ExtraTurn):
        def __init__(self, t):
            super().__init__(f"{t.nameid}_ultimate_turn", f"{t.name}'s Ultimate Turn", action.ExtraTurn.Priority.ULTIMATE, t)
            
            battle.current.event_bus.add_member_listener_legacy(self.extra_turn, self)
            if not battle.current.features.get("ultimate_turn_not_reset_at_new_wave"):
                battle.current.event_bus.add_member_listener_legacy(self.new_wave_start, self)
        
        def dead(self):
            if super().dead():
                return True
            return self.target.cur_energy < self.target.stats["energy"].calculate()
        
        def on_removed(self, list):
            super().on_removed(list)
            if list is battle.current.action_list.extras:
                self.target.ultimate_activated = False
        
        def is_ultimate(self):
            return True
        
        @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
        def extra_turn(self, turn):
            if self is not turn:
                return
            battle.current.event_bus.dispatch_legacy("ultimate_turn", self)
            self.master.dead_toggle = True
        
        @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
        def new_wave_start(self):
            self.master.dead_toggle = True

    class CharacterSkill(skill.Skill):
        def __init__(self, t, skill_name):
            self.skill_name = skill_name
            config_data = t.config.data["skills"][skill_name]
            nameid, name = t.config.get_skill_name(skill_name)
            type = skill.SkillType.dict_nameid[config_data["type"]]
            super().__init__(nameid, name, type, t)
            self.category = config_data["category"]
            self.delta_skillpoints = config_data["delta_skillpoints"]
            self.target_info = None
            if "target" in config_data:
                self.target_info = config_data["target"]
            self.bonus_level = 0
            event.bus.add_member_listener(self.before_skill_trigger_listener, self, t)
            event.bus.add_member_listener(self.after_skill_trigger_listener, self, t)
        
        def is_character_target(self):
            return self.target_info["type"] == "character"
        
        def get_value(self, name):
            level = self.level + self.bonus_level
            return self.target.config.get_skill_value(self.skill_name, name, level=level)
        
        def get_main_target(self):
            return battle.current.cur_main_target
        
        def get_adjacent_targets(self, k=1):
            idx = self.skill_targets.index(self.get_main_target())
            result = []
            for i in range(-k, k + 1):
                if i != 0 and 0 <= idx + i < len(self.skill_targets):
                    result.append(self.skill_targets[idx + i])
            return result
        
        def before_skill_trigger(self):
            self.skill_dead = item.DeadToggle(self.target)
            if self.target_info is not None:
                self.skill_targets = battle.current.characters.copy() if self.is_character_target() else battle.current.monsters.copy()
            else:
                self.skill_targets = None
            battle.current.skillpoints.modify(self.delta_skillpoints)
        
        def after_skill_trigger(self):
            self.skill_dead.dead_toggle = True
        
        @event.member_listener(event_types.SkillTrigger.BEFORE_TRIGGER)
        def before_skill_trigger_listener(self, e):
            self.before_skill_trigger()
        
        @event.member_listener(event_types.SkillTrigger.AFTER_TRIGGER)
        def after_skill_trigger_listener(self, e):
            self.after_skill_trigger()
    
    class CharacterUltimate(CharacterSkill):
        def before_skill_trigger(self):
            super().before_skill_trigger()
            self.target.cur_energy -= self.target.stats["energy"].calculate()
            self.target.ultimate_activated = False

    def __init__(self, nameid, record):
        self.config = self.CharacterConfig(config.load_config_data("characters", nameid), self)
        if nameid != self.config.nameid:
            logging.warning(f"Character nameid mismatch: {nameid} != {self.config['nameid']}")
        
        super().__init__(uuid.UUID(record["uuid"]), nameid, self.config.name, None)
        self.config.init()
        # break_eff = Break Effect
        # wb_eff = Weakness Break Efficiency
        self.stats.new_stats(
            ["crt_rate", "crt_dmg", "taunt", "energy", "max_energy", "energy_regen_rate", "break_eff", "wb_eff", "base_break_dmg",
            "outgoing_healing_boost", "incoming_healing_boost", "break_dmg_boost"], self)
        self.eidolons = None
        self.traces_stats_unlocked = None
        self.traces_unlocked = None
        self.lightcone = None
        self.relics = {}
        for type in relic.RelicType.ALL:
            self.relics[type.nameid] = None
        self.relic_effects = []
        self.use_technique = False
        self.cur_energy = 0
        self.ultimate_activated = False

        battle.current.event_bus.add_member_listener_legacy(self.target_action, self)
        battle.current.event_bus.add_member_listener_legacy(self.break_weakness, self)
        battle.current.event_bus.add_member_listener_legacy(self.regen_energy, self)
        battle.current.event_bus.add_member_listener_legacy(self.prepare_ultimate, self)
        battle.current.event_bus.add_member_listener_legacy(self.ultimate_turn, self)

        self.init_skills()
        self.set_record(record)
    
    def init_skills(self):
        self.skills = {
            "basic_atk": skill.SkillGroup(self),
            "skill": skill.SkillGroup(self),
            "ultimate": skill.SkillGroup(self),
            "talent": skill.SkillGroup(self),
            "technique": skill.SkillGroup(self)
        }
        self.skill_options = ["basic_atk", "skill"]
        self.skills["basic_atk"].add(self.BasicAtk(self, "basic_atk"))
        self.skills["skill"].add(self.Skill(self, "skill"))
        self.skills["ultimate"].add(self.Ultimate(self, "ultimate"))
        self.skills["talent"].add(self.Talent(self, "talent"))
        self.skills["technique"].add(self.Technique(self, "technique"))
    
    def get_current_skill(self, name):
        return self.skills[name].current_skill()
    
    def set_record(self, record):
        # 读取record
        self.level = record["level"]
        self.eidolons = record["eidolons"]
        self.skills["basic_atk"].set_level(record["basic_atk_level"])
        self.skills["skill"].set_level(record["skill_level"])
        self.skills["ultimate"].set_level(record["ultimate_level"])
        self.skills["talent"].set_level(record["talent_level"])
        self.skills["technique"].set_level(record["technique_level"])
        self.traces_stats_unlocked = record["traces_stats_unlocked"]
        self.traces_unlocked = record["traces_unlocked"]
        if "lightcone" in record:
            self.lightcone = config.load_class("lightcones", record["lightcone"]["name"])(record["lightcone"])
        if "relics" in record:
            for type, r in record["relics"].items():
                if r is not None:
                    r_class = config.load_class("relics", r["name"])
                    r_set = relic.relic_sets[r_class.id]
                    r_inst = relic.Relic(r_set, relic.RelicType.dict_nameid[type])
                    self.relics[type] = r_inst
                    r_inst.set_record(r)
        
        self.config.set_base_stats()
        self.config.set_traces_stats()
        self.update_lightcone_and_relics()

        self.set_break_effect_types()
    
    def get_record(self):
        record =  {
            "level": self.level,
            "eidolons": self.eidolons,
            "basic_atk_level": self.get_current_skill("basic_atk").level,
            "skill_level": self.get_current_skill("skill").level,
            "ultimate_level": self.get_current_skill("ultimate").level,
            "talent_level": self.get_current_skill("talent").level,
            "technique_level": self.get_current_skill("technique").level,
            "traces_stats_unlocked": self.traces_stats_unlocked,
            "traces_unlocked": self.traces_unlocked
        }
        if self.lightcone is not None:
            record["lightcone"] = self.lightcone.get_record()
        for type, r in self.relics.items():
            if r is not None:
                if "relics" not in record:
                    record["relics"] = {}
                record["relics"][type] = r.get_record()
        return record
    
    def update_lightcone_and_relics(self):
        if self.lightcone is not None:
            self.lightcone.apply(self)
        for r in self.relics.values():
            if r is not None:
                r.apply(self)
        relics = collections.defaultdict(int)
        for type, r in self.relics.items():
            if r is not None:
                relics[r.relic_set.id] += 1
        for id, pieces in relics.items():
            self.relic_effects.append(relic.relic_sets[id].get_pieces_effect(self, pieces))
    
    def set_break_effect_types(self):
        dmg_desc = damage.DamageDesc(self,
            modifier.StatDesc((self.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, 1)),
            enums.Element.ICE, (damage.DmgType.BREAK, damage.DmgType.ADDITIONAL), damage.DmgSource.WEAKNESS_BREAK)
        self.effect_types.add("break", effect.FrozenEffect(dmg_desc))
    
    def get_skills_info(self):
        result = {"basic_atk": [], "skill": [], "ultimate": [], "talent": [], "trace": [], "eidolon": []}
        for skill_name in self.config.skills:
            nameid, name = self.config.get_skill_name(skill_name)
            category = self.config.skills[skill_name]["category"]
            info = {
                "nameid": nameid,
                "name": name,
                "desc": self.config.get_skill_desc(skill_name)
            }
            if "type" in self.config.skills[skill_name]:
                info["type"] = self.config.skills[skill_name]["type"]
            result[category].append(info)
        return result
    
    def set_auto_battle(self, policy):
        self.auto_battle = policy

    @event.member_listener_legacy(event.ListenerPriority.START, "battle_start")
    def set_initial_state(self):
        # 这个listener在Target类中已经被添加
        super().set_initial_state()
        if "cur_energy" in self.initial_state:
            self.cur_energy = self.initial_state["cur_energy"]
        elif "cur_energy_rate" in self.initial_state:
            self.cur_energy = self.initial_state["cur_energy_rate"] * self.stats["energy"].calculate()
        else:
            self.cur_energy = 0.5 * self.stats["energy"].calculate()
    
    def check_technique(self):
        if self.use_technique:
            event.bus.dispatch(event_types.SkillGroupTrigger(self.skills["technique"]))
    
    def check_ultimate_energy(self):
        return self.cur_energy >= self.stats["energy"].calculate()
    
    def ultimate_available(self):
        return self.can_act()
    
    @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
    def target_action(self, t):
        if self is not t:
            return
        event.bus.dispatch(event_types.SkillGroupTrigger(decision.provider.provide_character_skill_option(self)))
    
    @event.member_listener_legacy(event.ListenerPriority.EXECUTE + 1, "weakness_break")
    def break_weakness(self, tr):
        if self is not tr.dealer:
            return
        dmg = damage.Damage.create(self, tr.target,
            modifier.StatDesc((self.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, 1)),
            self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK, False)
        battle.current.event_bus.dispatch_legacy("additional_damage", dmg)
        battle.current.event_bus.dispatch_legacy("action_delay", tr.target.cur_normal_turn, 0.25)
        if self.element is enums.Element.ICE:
            eff_add = effect.EffectAddition(self, tr.target, self.effect_types.get("break", "frozen"), 1)
            self.try_apply_debuff(eff_add, 1.5)
    
    @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
    def regen_energy(self, t, amount, fixed=False):
        if self is not t:
            return
        if fixed:
            self.cur_energy += amount
        else:
            self.cur_energy += amount * self.stats["energy_regen_rate"].calculate()
        max = self.stats["max_energy"].calculate()
        if self.cur_energy > max:
            self.cur_energy = max
    
    @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
    def prepare_ultimate(self, t):
        if self is not t:
            return
        self.ultimate_activated = True
        battle.current.action_list.extras.append(Character.UltimateTurn(self))
    
    @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
    def ultimate_turn(self, turn):
        if self is not turn.target:
            return
        decision.provider.notify({"name": "ultimate_turn", "target": str(self.uuid)})
        decision.provider.provide_ultimate_target(self)
        event.bus.dispatch(event_types.SkillGroupTrigger(self.skills["ultimate"]))
