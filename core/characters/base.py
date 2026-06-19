import collections

import target
import skill
import event
import battle
import config
import enums
import modifier
import server
import damage
import effect
import action
from relics import base as relic

class Character(target.Target):
    class CharacterConfig(target.Target.TargetConfig):
        __slots__ = ("base_stats", "traces_stats")
        
        def __init__(self, data, t):
            super().__init__(data, t)
            self.base_stats = data["base_stats"]
            self.base_stats["base_break_dmg"] = [54, 3767.5533]
            self.base_stats["crt_rate"] = [0.05, 0.05]
            self.base_stats["crt_dmg"] = [0.5, 0.5]
            self.base_stats["energy_regen_rate"] = [1, 1]
            self.traces_stats = data["traces_stats"]
        
        def init(self):
            self.target.element = enums.Element.dict_nameid[self.data["element"]]
            self.target.path = enums.Path.dict_nameid[self.data["path"]]
        
        def set_base_stats(self):
            for name, stats in self.base_stats.items():
                self.target.stats[name].base_value = target.lerp(stats[0], stats[1], (self.target.level - 1) / 79)
        
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

    class UltimateTurn(target.Target.ExtraTurn):
        def __init__(self, t):
            super().__init__(t, action.ActionPriority.EXTRA_TURN)
        
        def dead(self):
            if super().dead():
                return True
            energy = self.target.stats["energy"].calculate()
            if self.target.cur_energy < energy:
                self.target.ultimate_activated = False
                return True

    class CharacterSkill(skill.Skill):
        def __init__(self, t, skill_name):
            self.skill_name = skill_name
            config_data = t.config.data["skills"][skill_name]
            nameid, name = t.config.get_skill_name(skill_name)
            type = skill.SkillType.dict_nameid[config_data["type"]]
            super().__init__(nameid, name, type, t)
            self.category = config_data["category"]
            self.delta_skillpoints = config_data["delta_skillpoints"]
            self.bonus_level = 0
            battle.current.event_bus.add_member_listener(self.skill_trigger_pre, t)
        
        def get_value(self, name):
            level = self.level + self.bonus_level
            return self.target.config.get_skill_value(self.skill_name, name, level=level)
        
        @classmethod
        def get_target(cls, list, idx):
            if 0 <= idx < len(list):
                return list[idx]
            return None

        def get_main_target(self):
            if self.type in (skill.SkillType.SINGLE, skill.SkillType.BLAST, skill.SkillType.BOUNCE, skill.SkillType.AOE):
                list = battle.current.monsters
            elif self.type in (skill.SkillType.RESTORE, skill.SkillType.SUPPORT):
                list = battle.current.characters
            return self.get_target(list, battle.current.target_index)
        
        def get_blast_targets(self, n=1):
            if self.type in (skill.SkillType.SINGLE, skill.SkillType.BLAST, skill.SkillType.BOUNCE, skill.SkillType.AOE):
                list = battle.current.monsters
            elif self.type in (skill.SkillType.RESTORE, skill.SkillType.SUPPORT):
                list = battle.current.characters
            result = []
            for i in range(-n, n + 1):
                if i != 0:
                    t = self.get_target(list, battle.current.target_index + i)
                    if t is not None:
                        result.append(t)
            return result
        
        def available(self):
            if not battle.current.skillpoints.available(self.delta_skillpoints):
                return "not_enough_skillpoints"
            try:
                self.get_main_target()
            except IndexError:
                return "invalid_target"
            return "ok"
        
        @event.member_listener(event.ListenerPriority.PRE_PROCESS, "skill_trigger")
        async def skill_trigger_pre(self, skill):
            if self is not skill:
                return
            battle.current.skillpoints.modify(self.delta_skillpoints)

    def __init__(self, nameid, record):
        self.config = self.CharacterConfig(config.load_config_data("characters", nameid), self)
        if nameid != self.config.nameid:
            logging.warning(f"Character nameid mismatch: {nameid} != {self.config['nameid']}")
        
        super().__init__(nameid, self.config.name, None)
        self.config.init()
        self.stats.new_stats(
            ["crt_rate", "crt_dmg", "taunt", "energy", "max_energy", "energy_regen_rate", "break_eff", "base_break_dmg",
            "outgoing_healing_boost", "incoming_healing_boost"], self)
        self.eidolons = None
        self.traces_stats_unlocked = None
        self.traces_unlocked = None
        self.skills = {
            "basic_atk": skill.SkillGroup(self),
            "skill": skill.SkillGroup(self),
            "ultimate": skill.SkillGroup(self),
            "talent": skill.SkillGroup(self),
            "technique": skill.SkillGroup(self)
        }
        self.lightcone = None
        self.relics = {}
        for type in relic.RelicType.ALL:
            self.relics[type.nameid] = None
        self.relic_effects = []
        self.cur_energy = 0
        self.ultimate_activated = False

        battle.current.event_bus.add_member_listener(self.normal_turn, self)
        battle.current.event_bus.add_member_listener(self.break_weakness, self)
        battle.current.event_bus.add_member_listener(self.regen_energy, self)
        battle.current.event_bus.add_member_listener(self.prepare_ultimate, self)
        battle.current.event_bus.add_member_listener(self.ultimate_turn, self)

        self.skills["basic_atk"].add(self.BasicAtk(self, "basic_atk"))
        self.skills["skill"].add(self.Skill(self, "skill"))
        self.skills["ultimate"].add(self.Ultimate(self, "ultimate"))
        self.skills["talent"].add(self.Talent(self, "talent"))
        self.set_record(record)
    
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
    
    def get_record(self):
        record =  {
            "level": self.level,
            "eidolons": self.eidolons,
            "basic_atk_level": self.skills["basic_atk"][0].level,
            "skill_level": self.skills["skill"][0].level,
            "ultimate_level": self.skills["ultimate"][0].level,
            "talent_level": self.skills["talent"][0].level,
            "technique_level": self.skills["technique"][0].level,
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

    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        # 这个listener在Target类中已经被添加
        await super().battle_start()
        self.cur_energy = 0.5 * self.stats["energy"].calculate() * 2
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def normal_turn(self, t):
        if self is not t:
            return
        self.frozen = self.effects.has_debuff(effect.Debuff.FROZEN)
        if self.frozen:
            target.Target.NormalTurn.advance_target(self, 0.5)
            return
        message = {"type": "character_normal_turn_option", "options": list(self.skills.keys()), "info": None} | self.get_info()
        while True:
            response = await server.send_and_recv(message)
            message["info"] = None
            if response["type"] == "character_normal_turn_option":
                option = response["option"]
                if option not in ("basic_atk", "skill"):
                    message["info"] = "bad_option"
                    continue
                battle.current.target_index = response["index"]
                info = self.skills[option].available()
                if info == "ok":
                    break
                message["info"] = info
        skill_group = self.skills[option]
        await battle.current.event_bus.dispatch("skill_group_trigger", skill_group)
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "weakness_break")
    async def break_weakness(self, tr):
        if self is not tr.dealer:
            return
        dmg = damage.Damage(self, tr.target,
            modifier.StatDesc((self.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, 1)),
            self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
        await battle.current.event_bus.dispatch("deal_damage", dmg)
        target.Target.NormalTurn.delay_target(tr.target, 0.25)
        if self.element is enums.Element.ICE:
            dmg = damage.Damage(self, tr.target,
                modifier.StatDesc((self.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, 1)),
                self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
            del dmg.factors[damage.DamageFactorType.MULTIPLIER]  # 击破造成的附加伤害没有击破倍率
            dmg.types = (damage.DmgType.ADDITIONAL, damage.DmgType.BREAK)  # 附加伤害类型是副类型，单独设置
            eff = effect.FrozenEffect(dmg)
            await self.try_apply_debuff(effect.EffectAddition(self, tr.target, eff, 1), 1.5)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def regen_energy(self, t, amount, fixed=False):
        if self is not t:
            return
        if fixed:
            self.cur_energy += amount
        else:
            self.cur_energy += amount * self.stats["energy_regen_rate"].calculate()
        max = self.stats["max_energy"].calculate()
        if self.cur_energy > max:
            self.cur_energy = max
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def prepare_ultimate(self, t):
        if self is not t:
            return
        if self.ultimate_activated:
            return
        energy = self.stats["energy"].calculate()
        if self.cur_energy >= energy:
            self.ultimate_activated = True
            battle.current.action_list.append(Character.UltimateTurn(self))
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def action_unit_trigger(self, action_unit):
        # 这个listener在Target类中已经被添加
        await super().action_unit_trigger(action_unit)
        if isinstance(action_unit, Character.UltimateTurn) and action_unit.target is self:
            action_unit.master.dead_toggle = True
            await battle.current.event_bus.dispatch("ultimate_turn", self)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def ultimate_turn(self, t):
        if self is not t:
            return
        message = {"type": "start_ultimate_turn"} | self.get_info()
        await server.send_and_recv(message)
        await battle.current.event_bus.dispatch("skill_group_trigger", self.skills["ultimate"])
