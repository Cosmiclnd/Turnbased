import json
import importlib
import collections
import logging

import item
import event
import modifier
import action
import battle
import skill
import server
import enums
import damage
import effect
import config
from relics import base as relic

class DyingStage(enums.Enum):
    ALIVE = item.Item("alive", "Alive")
    DIEABLE = item.Item("dieable", "Dieable")  # 已经受到致命伤害，即将转为濒死状态
    DYING = item.Item("dying", "Dying")  # 濒死状态，逻辑上已经死亡但是target还没有被清理
    DEAD = item.Item("dead", "Dead")
    ALL = (ALIVE, DIEABLE, DYING, DEAD)
DyingStage.init()

class Target(item.Item):
    class NormalTurn(action.ActionUnit):
        def __init__(self, target):
            super().__init__("normal_turn", "Normal Turn", action.ActionPriority.NORMAL_TURN, target)
            self.target = target
            self.start_action_value = 0
            self.scale = 1
        
        def action_value(self):
            return self.start_action_value + max(self.scale * 10000 / self.target.stats["spd"].calculate(), 0)
        
        def advance(self, scale):
            self.scale -= scale
        
        def delay(self, scale):
            self.advance(-scale)
        
        @classmethod
        def advance_target(cls, t, scale):
            for unit in battle.current.action_list:
                if isinstance(unit, Target.NormalTurn) and t is unit.target:
                    unit.advance(scale)
                    break
        
        @classmethod
        def delay_target(cls, t, scale):
            cls.advance_target(t, -scale)
    
    class ExtraTurn(action.ActionUnit):
        def __init__(self, target, priority):
            super().__init__("extra_turn", "Extra Turn", priority, target)
            self.target = target
            self.died = False
        
        def dead(self):
            if super().dead():
                return True
            return self.died
        
        def action_value(self):
            return 0
    
    class FollowUpTurn(ExtraTurn):
        def __init__(self, target):
            super().__init__(target, action.ActionPriority.FOLLOW_UP)

    def __init__(self, nameid, name, level):
        super().__init__(nameid, name, None)
        self.level = level
        self.stats = modifier.StatDict()
        stat_names = ["hp", "atk", "def", "spd", "dmg_boost", "res_pen"]
        for e in enums.Element.ALL:
            stat_names.append(f"{e.nameid}_dmg_boost")
            stat_names.append(f"{e.nameid}_res")
            stat_names.append(f"{e.nameid}_res_pen")
        stat_names.extend(["eff_hr", "eff_res"])
        for e in effect.Debuff.ALL:
            stat_names.append(f"{e.nameid}_res")
        self.stats.new_stats(stat_names, self)
        self.cur_hp = 0
        self.frozen = False
        self.dying_stage = None
        self.effects = {}

        battle.current.event_bus.add_member_listener(self.battle_start, self)
        battle.current.event_bus.add_member_listener(self.action_unit_trigger, self)
        battle.current.event_bus.add_member_listener(self.normal_turn_message, self)
        battle.current.event_bus.add_member_listener(self.attack, self)
        battle.current.event_bus.add_member_listener(self.hit, self)
        battle.current.event_bus.add_member_listener(self.receive_damage, self)
        battle.current.event_bus.add_member_listener(self.cur_hp_modify, self)
        battle.current.event_bus.add_member_listener(self.die, self)
        battle.current.event_bus.add_member_listener(self.receive_heal, self)
        battle.current.event_bus.add_member_listener(self.add_effect, self)
    
    def dead(self):
        return self.dying_stage is DyingStage.DEAD
    
    def get_stats_info(self):
        return {name: (stat.calculate(modifier.ModifierFilter.BASE), stat.calculate()) for name, stat in self.stats.items()}
    
    async def try_apply_debuff(self, t, debuff, base_chance):
        chance = base_chance
        chance *= 1 + self.stats["eff_hr"].calculate(effect=debuff)
        chance *= 1 - t.stats["eff_res"].calculate(effect=debuff)
        chance *= 1 - debuff.get_debuff_res(t)
        if battle.current.random.random() < chance:
            await battle.current.event_bus.dispatch("add_effect", t, debuff)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        self.cur_hp = self.stats["hp"].calculate()
        self.dying_stage = DyingStage.ALIVE
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def action_unit_trigger(self, action_unit):
        if isinstance(action_unit, Target.NormalTurn) and action_unit.target is self:
            battle.current.current_action_value = action_unit.action_value()
            action_unit.start_action_value = battle.current.current_action_value
            action_unit.order = action.ActionUnit.next_order()
            action_unit.scale = 1
            await battle.current.event_bus.dispatch("normal_turn", self)
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1, "normal_turn")
    async def normal_turn_message(self, t):
        if self is not t:
            return
        message = {"type": "start_normal_turn"} | self.get_info()
        await server.send_and_recv(message)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def attack(self, damage):
        if self is not damage.dealer:
            return
        await damage.on_attack()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def hit(self, damage):
        if self is not damage.target:
            return
        await damage.on_hit()
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "deal_damage")
    async def receive_damage(self, damage):
        if self is not damage.target:
            return
        dmg = damage.calculate()
        message = {"type": "deal_damage", "dealer": damage.dealer.get_info(), "target": self.get_info(), "amount": dmg, "dmg_type": damage.types[0].get_info()}
        await server.send_and_recv(message)
        # cur_hp_modify不能单独触发
        # 至少需要deal_damage才能使target死亡
        last_alive = self.dying_stage is DyingStage.ALIVE
        await battle.current.event_bus.dispatch("cur_hp_modify", self, -dmg)
        if last_alive and self.dying_stage is DyingStage.DIEABLE:
            self.dying_stage = DyingStage.DYING
            await battle.current.event_bus.dispatch("die", damage)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def cur_hp_modify(self, t, amount):
        if self is not t:
            return
        self.cur_hp += amount
        if self.cur_hp <= 0:
            self.dying_stage = DyingStage.DIEABLE
            return
        self.dying_stage = DyingStage.ALIVE
        hp = self.stats["hp"].calculate()
        if self.cur_hp > hp:
            self.cur_hp = hp
        
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def die(self, dmg):
        if self is not dmg.target:
            return
        # 真正清除死亡的target
        # TODO
        #message = {"type": "die"} | self.get_info()
        #await server.send_and_recv(message)
        self.dying_stage = DyingStage.DEAD
        battle.current.refresh()
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "heal")
    async def receive_heal(self, heal):
        if self is not heal.target:
            return
        amount = heal.calculate()
        message = {"type": "heal", "healer": heal.healer.get_info(), "target": self.get_info(), "amount": amount}
        await server.send_and_recv(message)
        await battle.current.event_bus.dispatch("cur_hp_modify", self, amount)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def add_effect(self, t, effect):
        if self is not t:
            return
        effect.apply(self)

class Character(Target):
    class UltimateTurn(Target.ExtraTurn):
        def __init__(self, target):
            super().__init__(target, action.ActionPriority.EXTRA_TURN)
        
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
        self.config = config.CharacterConfig(config.load_config_data("characters", nameid), self)
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
        battle.current.event_bus.add_member_listener(self.ultimate_action_unit_trigger, self)
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
            self.lightcone = load_class("lightcones", record["lightcone"]["name"])()
            self.lightcone.set_record(record["lightcone"])
        if "relics" in record:
            for type, r in record["relics"].items():
                if r is not None:
                    r_class = load_class("relics", r["name"])
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

    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        # 这个listener在Target类中已经被添加
        await super().battle_start()
        self.cur_energy = 0.5 * self.stats["energy"].calculate()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def normal_turn(self, t):
        if self is not t or self.frozen:
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
        Target.NormalTurn.delay_target(tr.target, 0.25)
        if self.element is enums.Element.ICE:
            dmg = damage.Damage(self, tr.target,
                modifier.StatDesc((self.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, 1)),
                self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
            del dmg.factors[damage.DamageFactorType.MULTIPLIER]  # 击破造成的附加伤害没有击破倍率
            dmg.types = (damage.DmgType.ADDITIONAL, damage.DmgType.BREAK)  # 附加伤害类型是副类型，单独设置
            await self.try_apply_debuff(tr.target, effect.FrozenEffect(1, dmg), 1.5)
    
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
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "action_unit_trigger")
    async def ultimate_action_unit_trigger(self, action_unit):
        if isinstance(action_unit, Character.UltimateTurn) and action_unit.target is self:
            action_unit.died = True
            await battle.current.event_bus.dispatch("ultimate_turn", self)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def ultimate_turn(self, t):
        if self is not t:
            return
        message = {"type": "start_ultimate_turn"} | self.get_info()
        await server.send_and_recv(message)
        await battle.current.event_bus.dispatch("skill_group_trigger", self.skills["ultimate"])

class Monster(Target):
    class MonsterSkill(skill.Skill):
        def get_target(self):
            taunts = [c.stats["taunt"].calculate() for c in battle.current.characters]
            return battle.current.random.choices(battle.current.characters, weights=taunts)[0]

    def __init__(self, nameid, name, level, moc, tier, base_weakness):
        super().__init__(nameid, name, level)
        self.moc = moc
        self.tier = tier
        self.base_weakness = base_weakness
        self.additional_weakness = []
        self.hp_layers = 1
        self.toughness_layers = 1
        self.stats.new_stats(["toughness"], self)
        self.skills = skill.SkillGroup(self)
        self.cur_toughness = 0
        self.weakness_broken = False

        battle.current.event_bus.add_member_listener(self.normal_turn, self)
        battle.current.event_bus.add_member_listener(self.reduce_toughness, self)
        battle.current.event_bus.add_member_listener(self.check_weakness_break, self)
        battle.current.event_bus.add_member_listener(self.weakness_break, self)
        battle.current.event_bus.add_member_listener(self.restore_toughness, self)
    
    def has_weakness(self, elem):
        return elem in self.base_weakness or elem in self.additional_weakness
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        # 这个listener在Target类中已经被添加
        await super().battle_start()
        self.cur_toughness = self.stats["toughness"].calculate()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def normal_turn(self, t):
        if self is not t or self.frozen:
            return
        await battle.current.event_bus.dispatch("skill_group_trigger", self.skills)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def reduce_toughness(self, tr):
        if self is not tr.target:
            return
        self.cur_toughness -= tr.calculate()

    @event.member_listener(event.ListenerPriority.POST_PROCESS, "reduce_toughness")
    async def check_weakness_break(self, tr):
        if self is not tr.target:
            return
        if self.cur_toughness <= 0:
            self.cur_toughness = 0
            if not self.weakness_broken:
                await battle.current.event_bus.dispatch("weakness_break", tr)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def weakness_break(self, tr):
        if self is not tr.target:
            return
        self.weakness_broken = True
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1, "normal_turn")
    async def restore_toughness(self, t):
        if self is not t:
            return
        if self.weakness_broken:
            self.cur_toughness = self.stats["toughness"].calculate()
            self.weakness_broken = False
    
    @classmethod
    def get_base_stat(cls, name, level, moc):
        if name == "def":
            return 200 + min(level, 100) * 10
        if not hasattr(cls, "level_curve"):
            with open("core/monsters/level_curve.json", "r") as f:
                cls.level_curve = json.load(f)
        curve = cls.level_curve["3" if moc else "1"]
        return curve[name][level - 1]

def lerp(a, b, t):
    return a + (b - a) * t

def load_class(category, nameid):
    name = nameid.replace("_", " ").title().replace(" ", "")
    module = importlib.import_module(category + "." + nameid)
    return getattr(module, name)
