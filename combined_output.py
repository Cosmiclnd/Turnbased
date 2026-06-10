####################
# .\core\action.py
####################

import item

class ActionUnit(item.Item):
    order = 0

    def __init__(self, nameid, name, priority, master=None):
        super().__init__(nameid, name, master)
        self.priority = priority
        self.order = ActionUnit.next_order()
    
    def action_value(self):
        return 0
    
    def sort_key(self):
        return (self.action_value(), -self.priority, self.order)
    
    @classmethod
    def next_order(cls):
        cls.order += 1
        return cls.order

class ActionPriority:
    NORMAL_TURN = 0
    EXTRA_TURN = 1
    FOLLOW_UP = 2

####################
# .\core\battle.py
####################

import random

import event
import action
import item
import target
import modifier
import server

class Skillpoints:
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

class Battle:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.event_bus = event.EventBus()
        self.action_list = item.ItemList()
        self.current_action_value = 0
        self.skillpoints = Skillpoints()
        self.characters = item.ItemList()
        self.monsters = item.ItemList()
        self.target_index = 0

        self.event_bus.add_member_listener(self.battle_start, nameid="battle", name="Battle")
    
    def refresh(self):
        self.characters.refresh()
        self.monsters.refresh()
    
    async def prepare_next_action_unit(self):
        verbose = True
        while True:
            message = await server.send_and_recv({"type": "prepare_next_action_unit", "verbose": verbose})
            if message["type"] == "empty":
                break
            if message["type"] == "prepare_ultimate":
                await self.event_bus.dispatch("prepare_ultimate", self.characters[message["index"]])
            verbose = False
    
    async def start(self):
        await self.event_bus.dispatch("battle_start")
        while True:
            await self.prepare_next_action_unit()
            self.action_list.refresh()
            self.action_list.sort(key=lambda x: x.sort_key())
            await self.event_bus.dispatch("action_unit_trigger", self.action_list[0])
            if not self.monsters:
                await server.send_and_recv({"type": "battle_win"})
                break
            if not self.characters:
                await server.send_and_recv({"type": "battle_lose"})
                break
    
    @event.member_listener(event.ListenerPriority.END)
    async def battle_start(self):
        for t in self.characters + self.monsters:
            self.action_list.append(target.Target.NormalTurn(t))

current = None

####################
# .\core\characters\herta.py
####################

import target
import skill
import battle
import event
import damage
import modifier
import enums
import effect

class Herta(target.Character):
    class BasicAtk(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("what_are_you_looking_at", "What Are You Looking At?", skill.SkillType.SINGLE, t, 1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            t = self.get_main_target()
            dmg = damage.Damage(self.target, t, self.target.stats["atk"], self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATTACK)
            dmg.factors[damage.DamageFactorType.MULTIPLIER] = 0.4 + 0.1 * level
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 10, self.target.element)
            dmg.energy_regen = 20
            await battle.current.event_bus.dispatch("attack", dmg)
            if self.target.eidolons >= 1:
                hp = t.stats["hp"].calculate()
                if t.cur_hp <= hp * 0.5:
                    dmg = damage.Damage(self.target, t, self.target.stats["atk"], self.target.element, damage.DmgType.ADDITIONAL, damage.DmgSource.BASIC_ATTACK)
                    dmg.factors[damage.DamageFactorType.MULTIPLIER] = 0.4
                    await battle.current.event_bus.dispatch("deal_damage", dmg)

    class Skill(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("one_time_offer", "One-Time Offer", skill.SkillType.AOE, t, -1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            mult = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8125, 0.875, 0.9375, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25)[level - 1]
            for t in battle.current.monsters[:]:
                dmg = damage.Damage(self.target, t, self.target.stats["atk"], self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
                dmg.factors[damage.DamageFactorType.MULTIPLIER] = mult
                dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 10, self.target.element)
                dmg.energy_regen = 30 / len(battle.current.monsters)
                dmg.hit_split = (0.3, 0.7)
                if t.cur_hp >= t.stats["hp"].calculate() * 0.5:
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.2
                    if self.target.traces_unlocked[0]:
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.25
                await battle.current.event_bus.dispatch("attack", dmg)
    
    class Ultimate(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("its_magic_i_added_some_magic", "It's Magic, I Added Some Magic", skill.SkillType.AOE, t, 0)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            self.target.cur_energy -= self.target.stats["energy"].calculate()
            self.target.ultimate_activated = False
            level = self.level + self.bonus_level
            mult = (1.2, 1.28, 1.36, 1.44, 1.52, 1.6, 1.7, 1.8, 1.9, 2, 2.08, 2.16, 2.24, 2.32, 2.4)[level - 1]
            for t in battle.current.monsters[:]:
                dmg = damage.Damage(self.target, t, self.target.stats["atk"], self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ULTIMATE)
                dmg.factors[damage.DamageFactorType.MULTIPLIER] = mult
                dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 20, self.target.element)
                dmg.energy_regen = 5 / len(battle.current.monsters)
                if self.target.traces_unlocked[2] and t.frozen:
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.2
                await battle.current.event_bus.dispatch("attack", dmg)
            if self.target.eidolons >= 6:
                nameid = "no_one_can_betray_me"
                name = "No One Can Betray Me"
                mod = modifier.Modifier(nameid, name, self.target.stats["atk"], modifier.ModifierFilter.BASE, 0.25, 0, None, self)
                eff = effect.ModifierEffect(nameid, name, self.target.effect_ids[nameid], effect.Effect.Type.BUFF, 1, effect.CommonEffect.DurationType.TURN_END, 1, mod, self.target.stats["atk"])
                await battle.current.event_bus.dispatch("add_effect", self.target, eff)
    
    class Talent(target.Character.CharacterSkill):
        class FollowUp(target.Target.FollowUpTurn):
            pass

        def __init__(self, t):
            super().__init__("fine_i_ll_do_it_myself", "Fine, I'll Do It Myself", skill.SkillType.AOE, t, 0)
            self.attacks = 0
            self.follow_up_launched = False
            battle.current.event_bus.add_member_listener(self.cur_hp_modify, t)
            battle.current.event_bus.add_member_listener(self.action_unit_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        async def cur_hp_modify(self, t, amount):
            if not isinstance(t, target.Monster):
                return
            hp = t.stats["hp"].calculate()
            if t.cur_hp <= hp * 0.5 and t.cur_hp - amount > hp * 0.5:
                self.attacks += 1
                if not self.follow_up_launched:
                    self.follow_up_launched = True
                    battle.current.action_list.append(Herta.Talent.FollowUp(self.target))
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def action_unit_trigger(self, action_unit):
            if isinstance(action_unit, Herta.Talent.FollowUp) and action_unit.target is self.target:
                action_unit.died = True
                level = self.level + self.bonus_level
                mult = (0.25, 0.265, 0.28, 0.295, 0.31, 0.325, 0.34375, 0.3625, 0.38125, 0.4, 0.415, 0.43, 0.445, 0.46, 0.475)[level - 1]
                i = 0
                while i < self.attacks:
                    for t in battle.current.monsters[:]:
                        dmg = damage.Damage(self.target, t, self.target.stats["atk"], self.target.element, damage.DmgType.NORMAL, damage.DmgSource.FOLLOW_UP)
                        dmg.factors[damage.DamageFactorType.MULTIPLIER] = mult
                        dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 5, self.target.element)
                        dmg.energy_regen = 5 / len(battle.current.monsters)
                        if self.target.eidolons >= 4:
                            dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.1
                        await battle.current.event_bus.dispatch("attack", dmg)
                    if self.target.eidolons >= 2:
                        nameid = "keep_the_ball_rolling"
                        name = "Keep the Ball Rolling"
                        mod = modifier.Modifier(nameid, name, None, None, 0, 0.03, None, self)
                        eff = effect.ModifierEffect(nameid, name, self.target.effect_ids[nameid], effect.Effect.Type.BUFF, -1, effect.CommonEffect.DurationType.PERMANENT, 5, mod, self.target.stats["crt_rate"])
                        await battle.current.event_bus.dispatch("add_effect", self.target, eff)
                    i += 1
                self.attacks = 0
                self.follow_up_launched = False

    def __init__(self, record):
        super().__init__("herta", "Herta", enums.Element.ICE, enums.Path.ERUDITION)
        self.skills["basic_atk"].add(self.BasicAtk(self))
        self.skills["skill"].add(self.Skill(self))
        self.skills["ultimate"].add(self.Ultimate(self))
        self.skills["talent"].add(self.Talent(self))
        self.set_record(record)

        self.effect_ids = {
            "keep_the_ball_rolling": effect.Effect.next_id(),
            "no_one_can_betray_me": effect.Effect.next_id()
        }
    
    def set_record(self, record):
        super().set_record(record)

        t = (self.level - 1) / 79
        self.stats["hp"].base_value = target.lerp(130, 953, t)
        self.stats["atk"].base_value = target.lerp(79.2, 582.12, t)
        self.stats["def"].base_value = target.lerp(54, 396.9, t)
        self.stats["base_break_dmg"].base_value = target.lerp(54, 3767.5533, t)
        self.stats["spd"].base_value = 100
        self.stats["crt_rate"].base_value = 0.05
        self.stats["crt_dmg"].base_value = 0.5
        self.stats["taunt"].base_value = 0.75
        self.stats["energy"].base_value = 110
        self.stats["max_energy"].base_value = 110
        self.stats["energy_regen_rate"].base_value = 1

        self.update_lightcone_and_relics()

        if self.traces_stats_unlocked[0]:
            self.stats["def"].modifiers.append(modifier.Modifier(
                "herta.trace0", "DEF Boost", self.stats["def"], modifier.ModifierFilter.BASE, 0.05, 0, None, self))
        if self.traces_stats_unlocked[1]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace1", "DMG Boost: Ice", None, None, 0, 0.032, None, self))
        if self.traces_stats_unlocked[2]:
            self.stats["crt_rate"].modifiers.append(modifier.Modifier(
                "herta.trace2", "CRT Rate Boost", None, None, 0, 0.027, None, self))
        if self.traces_stats_unlocked[3]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace3", "DMG Boost: Ice", None, None, 0, 0.048, None, self))
        if self.traces_stats_unlocked[4]:
            self.stats["def"].modifiers.append(modifier.Modifier(
                "herta.trace4", "DEF Boost", self.stats["def"], modifier.ModifierFilter.BASE, 0.075, 0, None, self))
        if self.traces_stats_unlocked[5]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace5", "DMG Boost: Ice", None, None, 0, 0.048, None, self))
        if self.traces_stats_unlocked[6]:
            self.stats["crt_rate"].modifiers.append(modifier.Modifier(
                "herta.trace6", "CRT Rate Boost", None, None, 0, 0.04, None, self))
        if self.traces_stats_unlocked[7]:
            self.stats["def"].modifiers.append(modifier.Modifier(
                "herta.trace7", "DEF Boost", self.stats["def"], modifier.ModifierFilter.BASE, 0.1, 0, None, self))
        if self.traces_stats_unlocked[8]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace8", "DMG Boost: Ice", None, None, 0, 0.032, None, self))
        if self.traces_stats_unlocked[9]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace9", "DMG Boost: Ice", None, None, 0, 0.064, None, self))
        if self.traces_unlocked[1]:
            self.stats["control_res"].modifiers.append(modifier.Modifier(
                "puppet", "Puppet", None, None, 0, 0.35, None, self))
        
        if self.eidolons >= 3:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
        if self.eidolons >= 5:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)

####################
# .\core\characters\huohuo.py
####################

import target
import skill
import battle
import event
import damage
import modifier
import enums
import effect

class Huohuo(target.Character):
    class BasicAtk(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("banner_stormcaller", "Banner: Stormcaller", skill.SkillType.SINGLE, t, 1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            t = self.get_main_target()
            dmg = damage.Damage(self.target, t, self.target.stats["hp"], self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATTACK)
            dmg.factors[damage.DamageFactorType.MULTIPLIER] = 0.2 + 0.05 * level
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 10, self.target.element)
            dmg.energy_regen = 20
            await battle.current.event_bus.dispatch("attack", dmg)
    
    class Skill(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("tailsman_protection", "Tailsman: Protection", skill.SkillType.RESTORE, t, -1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            t = self.get_main_target()
            # TODO
    
    class Ultimate(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("tail_spiritual_domination", "Tail: Spiritual Domination", skill.SkillType.SUPPORT, t, 0)
    
    class Talent(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("possession_ethereal_metaflow", "Possession: Ethereal Metaflow", skill.SkillType.RESTORE, t, 0)

    def __init__(self, record):
        super().__init__("huohuo", "Huohuo", enums.Element.WIND, enums.Path.ABUNDANCE)
        self.skills["basic_atk"].add(self.BasicAtk(self))
        self.skills["skill"].add(self.Skill(self))
        self.skills["ultimate"].add(self.Ultimate(self))
        self.skills["talent"].add(self.Talent(self))
        self.set_record(record)
    
    def set_record(self, record):
        super().set_record(record)

        t = (self.level - 1) / 79
        self.stats["hp"].base_value = target.lerp(185, 1358, t)
        self.stats["atk"].base_value = target.lerp(81.84, 601.52, t)
        self.stats["def"].base_value = target.lerp(69.3, 509.36, t)
        self.stats["base_break_dmg"].base_value = target.lerp(54, 3767.5533, t)
        self.stats["spd"].base_value = 98
        self.stats["crt_rate"].base_value = 0.05
        self.stats["crt_dmg"].base_value = 0.5
        self.stats["taunt"].base_value = 1
        self.stats["energy"].base_value = 140
        self.stats["max_energy"].base_value = 140
        self.stats["energy_regen_rate"].base_value = 1

        self.update_lightcone_and_relics()

        if self.traces_stats_unlocked[0]:
            self.stats["eff_res"].modifiers.append(modifier.Modifier(
                "huohuo.trace1", "Effect RES Boost", None, None, 0, 0.04, None, self))
        if self.traces_stats_unlocked[1]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace2", "HP Boost", self.stats["hp"], modifier.ModifierFilter.BASE, 0.04, 0, None, self))
        if self.traces_stats_unlocked[2]:
            self.stats["spd"].modifiers.append(modifier.Modifier(
                "huohuo.trace3", "SPD Boost", None, None, 0, 2, None, self))
        if self.traces_stats_unlocked[3]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace4", "HP Boost", self.stats["hp"], modifier.ModifierFilter.BASE, 0.06, 0, None, self))
        if self.traces_stats_unlocked[4]:
            self.stats["eff_res"].modifiers.append(modifier.Modifier(
                "huohuo.trace5", "Effect RES Boost", None, None, 0, 0.06, None, self))
        if self.traces_stats_unlocked[5]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace6", "HP Boost", self.stats["hp"], modifier.ModifierFilter.BASE, 0.06, 0, None, self))
        if self.traces_stats_unlocked[6]:
            self.stats["spd"].modifiers.append(modifier.Modifier(
                "huohuo.trace7", "SPD Boost", None, None, 0, 3, None, self))
        if self.traces_stats_unlocked[7]:
            self.stats["eff_res"].modifiers.append(modifier.Modifier(
                "huohuo.trace8", "Effect RES Boost", None, None, 0, 0.08, None, self))
        if self.traces_stats_unlocked[8]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace9", "HP Boost", self.stats["hp"], modifier.ModifierFilter.BASE, 0.04, 0, None, self))
        if self.traces_stats_unlocked[9]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace10", "HP Boost", self.stats["hp"], modifier.ModifierFilter.BASE, 0.08, 0, None, self))
        if self.traces_unlocked[1]:
            self.stats["control_res"].modifiers.append(modifier.Modifier(
                "the_cursed_one", "The Cursed One", None, None, 0, 0.35, None, self))
        
        if self.eidolons >= 3:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)
        if self.eidolons >= 5:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)

####################
# .\core\damage.py
####################

import copy

import target
import battle
import enums
import modifier
import item

class DmgType(enums.Enum):
    NORMAL = item.Item("normal", "Normal")
    ADDITIONAL = item.Item("additional", "Additional")
    BREAK = item.Item("break", "Break")
    ALL = (NORMAL, ADDITIONAL, BREAK)
DmgType.init()

class DmgSource(enums.Enum):
    BASIC_ATTACK = item.Item("basic_attack", "Basic Attack")
    SKILL = item.Item("skill", "Skill")
    ULTIMATE = item.Item("ultimate", "Ultimate")
    FOLLOW_UP = item.Item("follow_up", "Follow-Up")
    WEAKNESS_BREAK = item.Item("weakness_break", "Weakness Break")
    MONSTER = item.Item("monster", "Monster")
    ALL = (BASIC_ATTACK, SKILL, ULTIMATE, FOLLOW_UP, WEAKNESS_BREAK, MONSTER)
DmgSource.init()

class DamageFactorType:
    def __init__(self, func, base_func):
        self.func = func
        self.base_func = base_func

def multiplier_base_func(dmg):
    if dmg.has_types(DmgType.BREAK):
        mult = dmg.target.stats["toughness"].calculate(damage=dmg) / 40 + 0.5
        if dmg.element in (enums.Element.FIRE, enums.Element.PHYSICAL):
            mult *= 2
        elif dmg.element is enums.Element.WIND:
            mult *= 1.5
        elif dmg.element in (enums.Element.QUANTUM, enums.Element.IMAGINARY):
            mult *= 0.5
        return mult
    return 1

def crit_factor_func(dmg, value):
    if battle.current.random.random() < dmg.dealer.stats["crt_rate"].calculate(damage=dmg):
        return 1 + value
    return 1

def crit_factor_base_func(dmg):
    return dmg.dealer.stats["crt_dmg"].calculate(damage=dmg)

def dmg_boost_base_func(dmg):
    value = dmg.dealer.stats["dmg_boost"].calculate(damage=dmg)
    if dmg.element is not None:
        value += dmg.dealer.stats[f"{dmg.element.nameid}_dmg_boost"].calculate(damage=dmg)
    return value

def defence_factor_func(dmg, value):
    value += dmg.target.stats["def"].calculate(modifier.ModifierFilter.BASE) * dmg.factors[DamageFactorType.DEF_BOOST]
    value = max(0, value)
    return 1 - value / (value + 200 + 10 * dmg.dealer.level)

def defence_factor_base_func(dmg):
    return dmg.target.stats["def"].calculate(damage=dmg)

def resistance_base_func(dmg):
    value = -dmg.dealer.stats["res_pen"].calculate(damage=dmg)
    if dmg.element is not None:
        value += dmg.target.stats[f"{dmg.element.nameid}_res"].calculate(damage=dmg)
        value -= dmg.dealer.stats[f"{dmg.element.nameid}_res_pen"].calculate(damage=dmg)
    return value

def mitigation_factor_base_func(dmg):
    if isinstance(dmg.target, target.Monster) and not dmg.target.weakness_broken:
        return 0.9
    return 1

def break_eff_base_func(dmg):
    return dmg.dealer.stats["break_eff"].calculate(damage=dmg)

DamageFactorType.MULTIPLIER = DamageFactorType(lambda dmg, value: value, multiplier_base_func)
DamageFactorType.CRIT = DamageFactorType(crit_factor_func, crit_factor_base_func)
DamageFactorType.DMG_BOOST = DamageFactorType(lambda dmg, value: 1 + value, dmg_boost_base_func)
DamageFactorType.WEAKEN = DamageFactorType(lambda dmg, value: 1 - value, lambda dmg: 0)
DamageFactorType.DEFENCE = DamageFactorType(defence_factor_func, defence_factor_base_func)
DamageFactorType.DEF_BOOST = DamageFactorType(lambda dmg, value: 1, lambda dmg: 0)
DamageFactorType.RESISTANCE = DamageFactorType(lambda dmg, value: min(max(1 - value, 0.1), 2), resistance_base_func)
DamageFactorType.VUNERABILITY = DamageFactorType(lambda dmg, value: 1 + value, lambda dmg: 0)
DamageFactorType.MITIGATION = DamageFactorType(lambda dmg, value: max(value, 0.01), mitigation_factor_base_func)
DamageFactorType.BREAK_EFF = DamageFactorType(lambda dmg, value: 1 + value, break_eff_base_func)
DamageFactorType.BREAK_DMG_BOOST = DamageFactorType(lambda dmg, value: 1 + value, lambda dmg: 0)

class Damage:
    def __init__(self, dealer, t, stat, element, types, source):
        self.dealer = dealer
        self.target = t
        self.stat = stat
        self.element = element
        self.types = types if isinstance(types, tuple) else (types,)
        self.source = source
        self.factors = {}
        self.toughness_reduction = None
        self.hit_split = None
        self.energy_regen = None
        self.damage = None

        if self.has_types(DmgType.NORMAL, DmgType.ADDITIONAL):
            for factor in (
                DamageFactorType.MULTIPLIER,
                DamageFactorType.DMG_BOOST,
                DamageFactorType.WEAKEN,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VUNERABILITY,
                DamageFactorType.MITIGATION
            ):
                self.new_factor(factor)
            if isinstance(self.dealer, target.Character):
                self.new_factor(DamageFactorType.CRIT)
        if self.has_types(DmgType.BREAK):
            for factor in (
                DamageFactorType.MULTIPLIER,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VUNERABILITY,
                DamageFactorType.MITIGATION,
                DamageFactorType.BREAK_EFF,
                DamageFactorType.BREAK_DMG_BOOST
            ):
                self.new_factor(factor)
    
    def has_types(self, *types):
        # 只要有相同的伤害类型即可
        return any(t in self.types for t in types)

    def new_factor(self, factor):
        if factor in self.factors:
            return
        self.factors[factor] = factor.base_func(self)
    
    def calculate(self):
        damage = self.stat.calculate(damage=self)
        for factor, value in self.factors.items():
            damage *= factor.func(self, value)
        self.damage = damage
        return damage

    def damage(self):
        if self.damage is None:
            raise ValueError("damage not calculated")
        return self.damage
    
    async def on_attack(self):
        if self.hit_split is None:
            await battle.current.event_bus.dispatch("hit", self)
        else:
            mult = self.factors[DamageFactorType.MULTIPLIER]
            toughness_reduction = self.toughness_reduction.base_amount if self.toughness_reduction is not None else None
            energy_regen = self.energy_regen
            for rate in self.hit_split:
                dmg = copy.copy(self)
                dmg.hit_split = None
                dmg.factors[DamageFactorType.MULTIPLIER] = mult * rate
                if dmg.toughness_reduction is not None:
                    dmg.toughness_reduction.base_amount = toughness_reduction * rate
                if dmg.energy_regen is not None:
                    dmg.energy_regen = energy_regen * rate
                await battle.current.event_bus.dispatch("hit", dmg)
            self.factors[DamageFactorType.MULTIPLIER] = mult
            if toughness_reduction is not None:
                self.toughness_reduction.base_amount = toughness_reduction
            self.energy_regen = energy_regen
    
    async def on_hit(self):
        await battle.current.event_bus.dispatch("deal_damage", self)
        if self.toughness_reduction is not None:
            await battle.current.event_bus.dispatch("reduce_toughness", self.toughness_reduction)
        if self.energy_regen is not None:
            t = self.target if isinstance(self.target, target.Character) else self.dealer
            await battle.current.event_bus.dispatch("regen_energy", t, self.energy_regen)

class ToughnessReduction:
    def __init__(self, dealer, target, base_amount, element):
        self.dealer = dealer
        self.target = target
        self.base_amount = base_amount
        self.element = element
    
    def calculate(self):
        return self.base_amount if self.element is None or self.target.has_weakness(self.element) else 0

####################
# .\core\effect.py
####################

import item
import event
import battle
import target
import enums

class Debuff(enums.Enum):
    # 在需要时指定
    BLEED = item.Item("bleed", "Bleed")
    BURN = item.Item("burn", "Burn")
    FROZEN = item.Item("frozen", "Frozen")
    SHOCK = item.Item("shock", "Shock")
    WIND_SHEER = item.Item("wind_sheer", "Wind Sheer")
    ENTANGLEMENT = item.Item("entanglement", "Entanglement")
    IMPRISONMENT = item.Item("imprisonment", "Imprisonment")
    CONTROL = item.Item("control", "Control")
    ALL = (BLEED, BURN, FROZEN, SHOCK, WIND_SHEER, ENTANGLEMENT, IMPRISONMENT, CONTROL)
Debuff.init()

class Effect(item.Item):
    id = 0

    class Type:
        BUFF = 0
        DEBUFF = 1
        OTHER = 2

    def __init__(self, nameid, name, id, type):
        super().__init__(nameid, name)
        self.id = id
        self.type = type
        self.target = None
    
    def dead(self):
        return self.target is None or self.target.dead()
    
    def apply(self, target):
        target.effects[self.id] = self
        self.target = target
    
    def remove(self, target):
        if self.id in target.effects:
            del target.effects[self.id]
        self.target = None
    
    def get_debuff_res(self, target):
        # 仅对Debuff有效
        return 0

    @classmethod
    def next_id(cls):
        cls.id += 1
        return cls.id

class CommonEffect(Effect):
    class DurationType:
        PERMANENT = 0
        TURN_START = 1
        TURN_END = 2

    def __init__(self, nameid, name, id, type, duration, duration_type, max_stacks):
        # duration=-1表示永久持续
        super().__init__(nameid, name, id, type)
        self.durations = {duration: 1}
        self.duration_type = duration_type
        self.max_stacks = max_stacks
    
    def refresh(self, target):
        pass
    
    def apply(self, target):
        if self.id in target.effects:
            target.effects[self.id].add_stacks(self.durations)
            target.effects[self.id].refresh(target)
        else:
            super().apply(target)
            self.refresh(target)
            if self.duration_type == self.DurationType.TURN_START:
                battle.current.event_bus.add_member_listener(self.turn_start, self)
            elif self.duration_type == self.DurationType.TURN_END:
                battle.current.event_bus.add_member_listener(self.turn_end, self)
    
    def remove(self, target):
        duration = min(filter(lambda x: x >= 0, self.durations.keys()))
        self.durations[duration] -= 1
        if self.durations[duration] == 0:
            del self.durations[duration]
        if self.get_stacks() == 0 and self.id in target.effects:
            del target.effects[self.id]
            self.target = None
            self.refresh(target)
    
    def get_stacks(self):
        return sum(self.durations.values())
    
    def add_stacks(self, durations):
        for duration, stacks in durations.items():
            if duration in self.durations:
                self.durations[duration] += stacks
            else:
                self.durations[duration] = stacks
        excess = self.get_stacks() - self.max_stacks
        if excess > 0:
            for duration in sorted(self.durations.keys()):
                if excess <= 0:
                    break
                if duration < 0:
                    continue
                stacks = self.durations[duration]
                remove = min(excess, stacks)
                self.durations[duration] -= remove
                excess -= remove
                if self.durations[duration] == 0:
                    del self.durations[duration]
    
    def advance_turn(self):
        target = self.target
        self.durations = {k - 1 if k > 0 else -1: v for k, v in self.durations.items() if k != 1}
        if self.get_stacks() == 0 and self.id in self.target.effects:
            del self.target.effects[self.id]
            self.target = None
            self.refresh(target)
    
    @event.member_listener(event.ListenerPriority.START, "normal_turn")
    async def turn_start(self, t):
        if self.target is not t:
            return
        self.advance_turn()
    
    @event.member_listener(event.ListenerPriority.END, "normal_turn")
    async def turn_end(self, t):
        if self.target is not t:
            return
        self.advance_turn()

class ModifierEffect(CommonEffect):
    def __init__(self, nameid, name, id, type, duration, duration_type, max_stacks, modifier, stat):
        super().__init__(nameid, name, id, type, duration, duration_type, max_stacks)
        self.modifier = modifier
        self.scale = modifier.scale
        self.offset = modifier.offset
        self.stat = stat
    
    def refresh(self, target):
        stacks = self.get_stacks()
        self.modifier.scale = self.scale * stacks
        self.modifier.offset = self.offset * stacks
        if self.target is not None and  self.modifier not in self.stat.modifiers:
            self.stat.modifiers.append(self.modifier)
        if self.target is None and self.modifier in self.stat.modifiers:
            self.stat.modifiers.remove(self.modifier)

class FrozenEffect(CommonEffect):
    eff_id = Effect.next_id()

    def __init__(self, duration, additional_dmg=None):
        super().__init__("frozen", "Frozen", self.eff_id, Effect.Type.DEBUFF, duration, CommonEffect.DurationType.TURN_END, 1)
        self.additional_dmg = additional_dmg
    
    def refresh(self, target):
        target.frozen = self.get_stacks() > 0
    
    def get_debuff_res(self, target):
        return target.stats["control_res"].calculate(effect=self)
    
    @event.member_listener(event.ListenerPriority.END, "normal_turn")
    async def turn_end(self, t):
        if self.target is not t:
            return
        if self.additional_dmg is not None:
            await battle.current.event_bus.dispatch("deal_damage", self.additional_dmg)
        target.Target.NormalTurn.advance_target(t, 0.5)
        self.advance_turn()

####################
# .\core\enums.py
####################

import item

class Enum:
    @classmethod
    def init(cls):
        cls.dict_nameid = {}
        cls.dict_name = {}
        for e in cls.ALL:
            cls.dict_nameid[e.nameid] = e
            cls.dict_name[e.name] = e

class Element(Enum):
    PHYSICAL = item.Item("physical", "Physical")
    FIRE = item.Item("fire", "Fire")
    ICE = item.Item("ice", "Ice")
    LIGHTNING = item.Item("lightning", "Lightning")
    WIND = item.Item("wind", "Wind")
    QUANTUM = item.Item("quantum", "Quantum")
    IMAGINARY = item.Item("imaginary", "Imaginary")
    ALL = (PHYSICAL, FIRE, ICE, LIGHTNING, WIND, QUANTUM, IMAGINARY)
Element.init()

class Path(Enum):
    DESTRUCTION = item.Item("destruction", "Destruction")
    THE_HUNT = item.Item("the_hunt", "The Hunt")
    ERUDITION = item.Item("erudition", "Erudition")
    HARMONY = item.Item("harmony", "Harmony")
    NIHILITY = item.Item("nihility", "Nihility")
    PRESERVATION = item.Item("preservation", "Preservation")
    ABUNDANCE = item.Item("abundance", "Abundance")
    ALL = (DESTRUCTION, THE_HUNT, ERUDITION, HARMONY, NIHILITY, PRESERVATION, ABUNDANCE)
Path.init()

class MonsterTier(Enum):
    NORMAL = item.Item("normal", "Normal")
    ELITE = item.Item("elite", "Elite")
    BOSS = item.Item("boss", "Boss")
    EOW = item.Item("eow", "Echo of War")
    ALL = (NORMAL, ELITE, BOSS, EOW)
MonsterTier.init()

####################
# .\core\event.py
####################

import logging

import item

class Listener(item.Item):
    def __init__(self, nameid, name, callback, master=None, priority=0):
        super().__init__(nameid, name, master)
        self.callback = callback
        self.priority = priority

class ListenerPriority:
    START = 1000
    PRE_PROCESS = 100
    EXECUTE = 0
    POST_PROCESS = -100
    END = -1000

class EventBus:
    def __init__(self):
        self.listeners = {}
        self.stack = []
    
    def add_listener(self, event_name, listener):
        if event_name not in self.listeners:
            self.listeners[event_name] = item.ItemList()
        self.listeners[event_name].append(listener)
    
    def add_member_listener(self, member_func, master=None, nameid=None, name=None):
        # member_func必须是被@member_listener装饰的成员函数
        nameid = nameid or master.nameid
        name = name or master.name
        self.add_listener(member_func.name, Listener(nameid, name, member_func, master, member_func.priority))
    
    async def dispatch(self, event_name, *args, **kwargs):
        if event_name in self.listeners:
            self.listeners[event_name].refresh()
            self.listeners[event_name].sort(key=lambda x: x.priority, reverse=True)
            for listener in self.listeners[event_name]:
                self.stack.append((event_name, listener))
                await listener.callback(*args, **kwargs)
                self.stack.pop()
        if event_name not in self.listeners or not self.listeners[event_name]:
            logging.warning(f"No listener for event {event_name}")

def member_listener(priority=0, name=None):
    def decorator(func):
        func.priority = priority
        func.name = name if name else func.__name__
        return func
    return decorator

####################
# .\core\item.py
####################

class Item:
    def __init__(self, nameid, name, master=None):
        self.nameid = nameid
        self.name = name
        self.master = master
    
    def dead(self):
        return self.master.dead() if self.master else False
    
    def get_info(self):
        return {"nameid": self.nameid, "name": self.name}

class ItemList(list[Item]):
    def refresh(self):
        self[:] = [item for item in self if not item.dead()]

####################
# .\core\lightcones\base.py
####################

import item

class LightCone(item.Item):
    def __init__(self, nameid, name, path):
        super().__init__(nameid, name)
        self.path = path
        self.target = None
        self.level = None
        self.stacks = None
    
    def apply(self, t):
        self.target = t
    
    def get_record(self):
        return {
            "name": self.nameid,
            "level": self.level,
            "stacks": self.stacks
        }
    
    def set_record(self, record):
        # `name`在target中被处理
        self.level = record["level"]
        self.stacks = record["stacks"]

####################
# .\core\lightcones\the_birth_of_the_self.py
####################

import target
import enums
import modifier
import event
import battle
import damage

from lightcones import base

class TheBirthOfTheSelf(base.LightCone):
    def __init__(self):
        super().__init__("the_birth_of_the_self", "The Birth of the Self", enums.Path.ERUDITION)
    
    def apply(self, tar):
        super().apply(tar)
        t = (self.level - 1) / 79
        self.target.stats["hp"].base_value += target.lerp(43, 953, t)
        self.target.stats["atk"].base_value += target.lerp(21.6, 476.28, t)
        self.target.stats["def"].base_value += target.lerp(15, 330.75, t)
        if self.path is self.target.path:
            dmg_boost = 0.18 + 0.06 * self.stacks
            mod1 = modifier.Modifier(self.nameid, self.name, None, None, 0, dmg_boost, self.validator_mod1, self.target)
            mod2 = modifier.Modifier(self.nameid, self.name, None, None, 0, dmg_boost, self.validator_mod2, self.target)
            self.target.stats["dmg_boost"].modifiers.extend((mod1, mod2))
    
    def validator_mod1(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.source is damage.DmgSource.FOLLOW_UP
    
    def validator_mod2(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.source is damage.DmgSource.FOLLOW_UP and dmg.target.cur_hp <= dmg.target.stats["hp"].calculate() * 0.5

####################
# .\core\main.py
####################

import logging
import asyncio
import websockets

import battle
import server

async def main():
    async with websockets.serve(server.handle, "localhost", server.port):
        await asyncio.Future()

logging.basicConfig(filename="latest.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logging.root.addHandler(logging.StreamHandler())

logging.info("Hello world! from Turnbased")

asyncio.run(main())

####################
# .\core\modifier.py
####################

import item

class ModifierFilter:
    BASE = 0
    SELF_CONVERSION = 1
    CALCULATED = 2

class Stat:
    __slots__ = ("name", "target", "base_value", "calculated_value", "modifiers")

    def __init__(self, name, target=None):
        self.name = name
        self.target = target
        self.base_value = 0
        self.calculated_value = 0
        self.modifiers = item.ItemList()
    
    def calculate(self, filter=ModifierFilter.CALCULATED, **kwargs):
        if filter is ModifierFilter.BASE:
            return self.base_value
        self.calculated_value = self.base_value
        for modifier in self.modifiers:
            modifier.modify(self, filter, **kwargs)
        return self.calculated_value

class StatDict(dict[str, Stat]):
    def new_stats(self, names, target=None):
        for name in names:
            self[name] = Stat(name, target)

class Modifier(item.Item):
    def __init__(self, nameid, name, src_stat, src_filter, scale, offset, validator=None, master=None):
        super().__init__(nameid, name, master)
        self.src_stat = src_stat
        self.src_filter = src_filter
        self.scale = scale
        self.offset = offset
        self.validator = validator
    
    def modify(self, stat, filter, **kwargs):
        if filter is ModifierFilter.BASE:
            return
        if self.validator is not None and not self.validator(stat, **kwargs):
            return
        # 当self.src_stat is None时，只有self.offset生效
        # 当stat is self.src_stat时，filter不能为ModifierFilter.CALCULATED，防止循环转化
        if self.src_stat is None:
            stat.calculated_value += self.offset
        elif stat is self.src_stat or filter is not ModifierFilter.CALCULATED:
            stat.calculated_value += self.scale * self.src_stat.calculate(self.src_filter, **kwargs) + self.offset

####################
# .\core\monsters\antibaryon.py
####################

import target
import event
import skill
import battle
import damage
import enums

class Antibaryon(target.Monster):
    class Skill(target.Monster.MonsterSkill):
        def __init__(self, t):
            super().__init__("obliterate", "Obliterate", skill.SkillType.SINGLE, t)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_target()
            dmg = damage.Damage(self.target, t, self.target.stats["atk"], enums.Element.IMAGINARY, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.factors[damage.DamageFactorType.MULTIPLIER] = 2.5
            dmg.energy_regen = 10
            await battle.current.event_bus.dispatch("attack", dmg)

    def __init__(self, level, moc):
        super().__init__("antibaryon", "Antibaryon", level, moc, enums.MonsterTier.NORMAL, [enums.Element.PHYSICAL, enums.Element.QUANTUM])
        self.skills.add(self.Skill(self))
        self.stats["hp"].base_value = target.Monster.get_base_stat("hp", level, moc) * 0.6
        self.stats["atk"].base_value = target.Monster.get_base_stat("atk", level, moc) * 18
        self.stats["def"].base_value = target.Monster.get_base_stat("def", level, moc)
        self.stats["spd"].base_value = target.Monster.get_base_stat("spd", level, moc) * 83
        self.stats["eff_hr"].base_value = target.Monster.get_base_stat("eff_hr", level, moc)
        self.stats["eff_res"].base_value = target.Monster.get_base_stat("eff_res", level, moc)
        self.stats["toughness"].base_value = 10
        self.stats["physical_res"].base_value = 0.2
        self.stats["fire_res"].base_value = 0.2
        self.stats["lightning_res"].base_value = 0.2
        self.stats["quantum_res"].base_value = 0.2
        self.stats["imaginary_res"].base_value = 0.2

####################
# .\core\monsters\baryon.py
####################

import target
import event
import skill
import battle
import damage
import enums

class Baryon(target.Monster):
    class Skill(target.Monster.MonsterSkill):
        def __init__(self, t):
            super().__init__("obliterate", "Obliterate", skill.SkillType.SINGLE, t)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_target()
            dmg = damage.Damage(self.target, t, self.target.stats["atk"], enums.Element.QUANTUM, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.factors[damage.DamageFactorType.MULTIPLIER] = 2.5
            dmg.energy_regen = 10
            await battle.current.event_bus.dispatch("attack", dmg)

    def __init__(self, level, moc):
        super().__init__("baryon", "Baryon", level, moc, enums.MonsterTier.NORMAL, [enums.Element.ICE, enums.Element.WIND])
        self.skills.add(self.Skill(self))
        self.stats["hp"].base_value = target.Monster.get_base_stat("hp", level, moc) * 0.6
        self.stats["atk"].base_value = target.Monster.get_base_stat("atk", level, moc) * 18
        self.stats["def"].base_value = target.Monster.get_base_stat("def", level, moc)
        self.stats["spd"].base_value = target.Monster.get_base_stat("spd", level, moc) * 83
        self.stats["eff_hr"].base_value = target.Monster.get_base_stat("eff_hr", level, moc)
        self.stats["eff_res"].base_value = target.Monster.get_base_stat("eff_res", level, moc)
        self.stats["toughness"].base_value = 10
        self.stats["physical_res"].base_value = 0.2
        self.stats["fire_res"].base_value = 0.2
        self.stats["lightning_res"].base_value = 0.2
        self.stats["quantum_res"].base_value = 0.2
        self.stats["imaginary_res"].base_value = 0.2

####################
# .\core\monsters\dummy.py
####################

import target
import event
import skill
import battle
import damage
import enums

class Dummy(target.Monster):
    class Skill(target.Monster.MonsterSkill):
        def __init__(self, t):
            super().__init__("dummy", "Dummy", skill.SkillType.SINGLE, t)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_target()
            dmg = damage.Damage(self.target, t, self.target.stats["atk"], None, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.factors[damage.DamageFactorType.MULTIPLIER] = 0
            dmg.energy_regen = 10
            await battle.current.event_bus.dispatch("attack", dmg)

    def __init__(self, level, moc):
        super().__init__("dummy", "Dummy", level, moc, enums.MonsterTier.NORMAL, [])
        self.skills.add(self.Skill(self))
        self.stats["hp"].base_value = target.Monster.get_base_stat("hp", level, moc) * 600
        self.stats["atk"].base_value = target.Monster.get_base_stat("atk", level, moc) * 18
        self.stats["def"].base_value = target.Monster.get_base_stat("def", level, moc)
        self.stats["spd"].base_value = target.Monster.get_base_stat("spd", level, moc) * 80
        self.stats["eff_hr"].base_value = target.Monster.get_base_stat("eff_hr", level, moc)
        self.stats["eff_res"].base_value = target.Monster.get_base_stat("eff_res", level, moc)
        self.stats["toughness"].base_value = 100

####################
# .\core\relics\base.py
####################

import item
import enums
import modifier

class RelicType(enums.Enum):
    HEAD = item.Item("head", "Head")
    HANDS = item.Item("hands", "Hands")
    BODY = item.Item("body", "Body")
    FEET = item.Item("feet", "Feet")
    PLANAR_SPHERE = item.Item("planar_sphere", "Planar Sphere")
    LINK_ROPE = item.Item("link_rope", "Link Rope")
    ALL = (HEAD, HANDS, BODY, FEET, PLANAR_SPHERE, LINK_ROPE)
RelicType.init()

class RelicStatType:
    def name(self):
        return self.stat_name + ("%" if self.is_percentage else "")

    @classmethod
    def init(cls):
        cls.dict = {}
        for stat in cls.ALL:
            cls.dict[stat.name()] = stat

class RelicMainStatType(RelicStatType):
    def __init__(self, stat_name, base, step, is_percentage=False):
        self.stat_name = stat_name
        self.base = base
        self.step = step
        self.is_percentage = is_percentage
    
    def get_stat(self, t):
        return t.stats[self.stat_name]
    
    def get_modifier(self, t, level):
        value = self.base + self.step * level
        if self.is_percentage:
            mod = modifier.Modifier(self.stat_name, self.stat_name, self.get_stat(t), modifier.ModifierFilter.BASE, value, 0, None, t)
        else:
            mod = modifier.Modifier(self.stat_name, self.stat_name, None, None, 0, value, None, t)
        return mod

RelicMainStatType.SPD = RelicMainStatType("spd", 4.032, 1.4)
RelicMainStatType.HP = RelicMainStatType("hp", 112.896, 39.5136)
RelicMainStatType.ATK = RelicMainStatType("atk", 56.448, 19.7568)
RelicMainStatType.HP_PERCENT = RelicMainStatType("hp", 0.06912, 0.024192, True)
RelicMainStatType.ATK_PERCENT = RelicMainStatType("atk", 0.06912, 0.024192, True)
RelicMainStatType.DEF_PERCENT = RelicMainStatType("def", 0.0864, 0.03024, True)
RelicMainStatType.BREAK_EFFECT = RelicMainStatType("break_effect", 0.10368, 0.036288)
RelicMainStatType.EFF_HR = RelicMainStatType("eff_hr", 0.06912, 0.024192)
RelicMainStatType.ENERGY_REGEN_RATE = RelicMainStatType("energy_regen_rate", 0.031104, 0.010886)
RelicMainStatType.HEALING_BOOST = RelicMainStatType("healing_boost", 0.055296, 0.019354)
RelicMainStatType.PHYSICAL_DMG_BOOST = RelicMainStatType("physical_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.FIRE_DMG_BOOST = RelicMainStatType("fire_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.ICE_DMG_BOOST = RelicMainStatType("ice_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.WIND_DMG_BOOST = RelicMainStatType("wind_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.LIGHTNING_DMG_BOOST = RelicMainStatType("lightning_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.QUANTUM_DMG_BOOST = RelicMainStatType("quantum_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.IMAGINARY_DMG_BOOST = RelicMainStatType("imaginary_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.CRT_RATE = RelicMainStatType("crt_rate", 0.05184, 0.018144)
RelicMainStatType.CRT_DMG = RelicMainStatType("crt_dmg", 0.10368, 0.036288)
RelicMainStatType.ALL = (RelicMainStatType.SPD,
    RelicMainStatType.HP, RelicMainStatType.ATK,
    RelicMainStatType.HP_PERCENT, RelicMainStatType.ATK_PERCENT, RelicMainStatType.DEF_PERCENT,
    RelicMainStatType.BREAK_EFFECT, RelicMainStatType.EFF_HR, RelicMainStatType.ENERGY_REGEN_RATE, RelicMainStatType.HEALING_BOOST,
    RelicMainStatType.PHYSICAL_DMG_BOOST, RelicMainStatType.FIRE_DMG_BOOST, RelicMainStatType.ICE_DMG_BOOST, RelicMainStatType.WIND_DMG_BOOST,
    RelicMainStatType.LIGHTNING_DMG_BOOST, RelicMainStatType.QUANTUM_DMG_BOOST, RelicMainStatType.IMAGINARY_DMG_BOOST,
    RelicMainStatType.CRT_RATE, RelicMainStatType.CRT_DMG)
RelicMainStatType.init()

RelicMainStatType.CHOICES = {
    RelicType.HEAD: {RelicMainStatType.HP: 1},
    RelicType.HANDS: {RelicMainStatType.ATK: 1},
    RelicType.BODY: {
        RelicMainStatType.HP_PERCENT: 0.2,
        RelicMainStatType.ATK_PERCENT: 0.2,
        RelicMainStatType.DEF_PERCENT: 0.2,
        RelicMainStatType.EFF_HR: 0.1,
        RelicMainStatType.HEALING_BOOST: 0.1,
        RelicMainStatType.CRT_RATE: 0.1,
        RelicMainStatType.CRT_DMG: 0.1
    },
    RelicType.FEET: {
        RelicMainStatType.HP_PERCENT: 0.3,
        RelicMainStatType.ATK_PERCENT: 0.3,
        RelicMainStatType.DEF_PERCENT: 0.3,
        RelicMainStatType.SPD: 0.1
    },
    RelicType.PLANAR_SPHERE: {
        RelicMainStatType.HP_PERCENT: 4 / 33,
        RelicMainStatType.ATK_PERCENT: 4 / 33,
        RelicMainStatType.DEF_PERCENT: 4 / 33,
        RelicMainStatType.PHYSICAL_DMG_BOOST: 1 / 11,
        RelicMainStatType.FIRE_DMG_BOOST: 1 / 11,
        RelicMainStatType.ICE_DMG_BOOST: 1 / 11,
        RelicMainStatType.WIND_DMG_BOOST: 1 / 11,
        RelicMainStatType.LIGHTNING_DMG_BOOST: 1 / 11,
        RelicMainStatType.QUANTUM_DMG_BOOST: 1 / 11,
        RelicMainStatType.IMAGINARY_DMG_BOOST: 1 / 11
    },
    RelicType.LINK_ROPE: {
        RelicMainStatType.HP_PERCENT: 0.25,
        RelicMainStatType.ATK_PERCENT: 0.25,
        RelicMainStatType.DEF_PERCENT: 0.25,
        RelicMainStatType.BREAK_EFFECT: 0.18,
        RelicMainStatType.ENERGY_REGEN_RATE: 0.7
    }
}

class RelicSubStatType(RelicStatType):
    def __init__(self, stat_name, weight, values, is_percentage=False):
        self.stat_name = stat_name
        self.weight = weight
        self.values = values
        self.is_percentage = is_percentage

    def get_stat(self, t):
        return t.stats[self.stat_name]
    
    def get_modifier(self, t, enhancements):
        value = 0
        for i in enhancements:
            value += self.values[i]
        if self.is_percentage:
            mod = modifier.Modifier(self.stat_name, self.stat_name, self.get_stat(t), modifier.ModifierFilter.BASE, value, 0, None, t)
        else:
            mod = modifier.Modifier(self.stat_name, self.stat_name, None, None, 0, value, None, t)
        return mod

RelicSubStatType.SPD = RelicSubStatType("spd", 4, (2, 2.3, 2.6))
RelicSubStatType.HP = RelicSubStatType("hp", 10, (33.87004, 38.103795, 42.33751))
RelicSubStatType.ATK = RelicSubStatType("atk", 10, (16.935, 19.051877, 21.168754))
RelicSubStatType.DEF = RelicSubStatType("def", 10, (16.935, 19.051877, 21.168754))
RelicSubStatType.HP_PERCENT = RelicSubStatType("hp", 10, (0.0346, 0.0389, 0.0432), True)
RelicSubStatType.ATK_PERCENT = RelicSubStatType("atk", 10, (0.0346, 0.0389, 0.0432), True)
RelicSubStatType.DEF_PERCENT = RelicSubStatType("def", 10, (0.0432, 0.0486, 0.054), True)
RelicSubStatType.BREAK_EFFECT = RelicSubStatType("break_effect", 8, (0.05184, 0.05832, 0.0648))
RelicSubStatType.EFF_HR = RelicSubStatType("eff_hr", 8, (0.03456, 0.03888, 0.0432))
RelicSubStatType.EFF_RES = RelicSubStatType("eff_res", 8, (0.03456, 0.03888, 0.0432))
RelicSubStatType.CRT_RATE = RelicSubStatType("crt_rate", 6, (0.02592, 0.02916, 0.0324))
RelicSubStatType.CRT_DMG = RelicSubStatType("crt_dmg", 6, (0.05184, 0.05832, 0.0648))
RelicSubStatType.ALL = (RelicSubStatType.SPD,
    RelicSubStatType.HP, RelicSubStatType.ATK, RelicSubStatType.DEF,
    RelicSubStatType.HP_PERCENT, RelicSubStatType.ATK_PERCENT, RelicSubStatType.DEF_PERCENT,
    RelicSubStatType.BREAK_EFFECT, RelicSubStatType.EFF_HR, RelicSubStatType.EFF_RES,
    RelicSubStatType.CRT_RATE, RelicSubStatType.CRT_DMG)
RelicSubStatType.init()

class RelicSet(item.Item):
    class PiecesEffect:
        def __init__(self, t, relic_set, pieces):
            self.target = t
            self.relic_set = relic_set
            self.pieces = pieces
    
    def get_pieces_effect(self, t, pieces):
        return self.PiecesEffect(t, self, pieces)

relic_sets = []

def register_relic_set(relic_set_class):
    id = len(relic_sets)
    relic_set_class.id = id
    relic_sets.append(relic_set_class())

class Relic(item.Item):
    def __init__(self, relic_set, type):
        super().__init__(relic_set.nameid, relic_set.name)
        self.target = None
        self.relic_set = relic_set
        self.type = type
        self.level = None
        self.main_stat_type = None
        self.sub_stat_types = []
        self.enhancements = []
    
    def get_record(self):
        return {
            "name": self.nameid,
            "level": self.level,
            "main_stat_type": self.main_stat_type.name(),
            "sub_stat_types": [s.name() for s in self.sub_stat_types],
            "enhancements": self.enhancements,
        }
    
    def set_record(self, record):
        # `name`在target中被处理
        self.level = record["level"]
        self.main_stat_type = RelicMainStatType.dict[record["main_stat_type"]]
        self.sub_stat_types = [RelicSubStatType.dict[s] for s in record["sub_stat_types"]]
        self.enhancements = record["enhancements"]
    
    def apply(self, t):
        self.target = t
        modifiers = []
        modifiers.append((self.main_stat_type.get_stat(t), self.main_stat_type.get_modifier(t, self.level)))
        for i, sub_stat_type in enumerate(self.sub_stat_types):
            modifiers.append((sub_stat_type.get_stat(t), sub_stat_type.get_modifier(t, self.enhancements[i])))
        for stat, mod in modifiers:
            stat.modifiers.append(mod)

####################
# .\core\relics\hunter_of_glacial_forest.py
####################

import modifier
import battle
import event
import effect

from relics import base

class HunterOfGlacialForest(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def __init__(self, t, relic_set, pieces):
            super().__init__(t, relic_set, pieces)
            if self.pieces >= 2:
                mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name, None, None, 0, 0.1, None, t)
                t.stats["ice_dmg_boost"].modifiers.append(mod)
            if self.pieces >= 4:
                battle.current.event_bus.add_member_listener(self.skill_group_trigger, t)
                self.effect_id = effect.Effect.next_id()
        
        @event.member_listener(event.ListenerPriority.EXECUTE + 1)
        async def skill_group_trigger(self, skill_group):
            if self.target.skills["ultimate"] is not skill_group:
                return
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name, None, None, 0, 0.25, None, self.target)
            eff = effect.ModifierEffect(self.relic_set.nameid, self.relic_set.name,
                self.effect_id, effect.Effect.Type.BUFF, 2, effect.CommonEffect.DurationType.TURN_END, 1, mod, self.target.stats["crt_dmg"])
            await battle.current.event_bus.dispatch("add_effect", self.target, eff)

    def __init__(self):
        super().__init__("hunter_of_glacial_forest", "Hunter of Glacial Forest")

base.register_relic_set(HunterOfGlacialForest)

####################
# .\core\relics\inert_salsotto.py
####################

import modifier
import damage

from relics import base

class InertSalsotto(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def __init__(self, t, relic_set, pieces):
            super().__init__(t, relic_set, pieces)
            if self.pieces >= 2:
                mod1 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name, None, None, 0, 0.08, None, t)
                t.stats["crt_rate"].modifiers.append(mod1)
                mod2 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name, None, None, 0, 0.15, None, t)
                t.stats["dmg_boost"].modifiers.append(mod2)
        
        def validator_mod2(self, stat, **kwargs):
            dmg = kwargs.get("damage", None)
            if dmg is None:
                return False
            return stat.target.stats["crt_rate"] >= 0.5 and dmg.source in (damage.DamageSource.ULTIMATE, damage.DmgSource.FOLLOW_UP)

    def __init__(self):
        super().__init__("inert_salsotto", "Inert Salsotto")

base.register_relic_set(InertSalsotto)

####################
# .\core\server.py
####################

import websockets
import logging
import json
import os

import battle
import target

port = 55716
websocket = None

async def handle_message(message):
    type = message["type"]
    if type == "init_battle":
        battle.current = battle.Battle()
    elif type == "start_battle":
        await battle.current.start()
    elif type == "add_character":
        character = target.load_class("characters", message["name"])(message["record"])
        battle.current.characters.append(character)
    elif type == "add_monster":
        monster = target.load_class("monsters", message["name"])(message["level"], message["moc"])
        battle.current.monsters.append(monster)

async def handle(w):
    global websocket
    websocket = w
    while True:
        try:
            message = await websocket.recv()
            await handle_message(json.loads(message))
        except websockets.ConnectionClosedOK:
            logging.info("connection closed")
            break
        except Exception as e:
            logging.exception(e)
            msg = "Event stack (most recent dispatch last):"
            for event_name, listener in battle.current.event_bus.stack:
                msg += f"\n  {event_name} -> {listener.name} ({listener.nameid})"
            logging.error(msg)
            logging.info("server closing")
            os._exit(1)

async def handle_command(message):
    type = message["type"]
    if type == "query_characters":
        subtype = message["subtype"]
        if subtype == "base":
            message["characters"] = [c.get_info() | {
                "cur_hp": c.cur_hp, "hp": c.stats["hp"].calculate(),
                "cur_energy": c.cur_energy, "energy": c.stats["energy"].calculate()
            } for c in battle.current.characters]
        elif subtype == "stats":
            c = battle.current.characters[message["character"]]
            message["character"] = c.get_info() | {"stats": c.get_stats_info()}
        await websocket.send(json.dumps(message))
    elif type == "query_monsters":
        subtype = message["subtype"]
        if subtype == "base":
            message["monsters"] = [m.get_info() | {"cur_hp": m.cur_hp, "hp": m.stats["hp"].calculate()} for m in battle.current.monsters]
        elif subtype == "stats":
            m = battle.current.monsters[message["monster"]]
            message["monster"] = m.get_info() | {"stats": m.get_stats_info()}
        await websocket.send(json.dumps(message))
    else:
        return False
    return True

async def send_and_recv(message):
    await websocket.send(json.dumps(message))
    while True:
        response = json.loads(await websocket.recv())
        if not await handle_command(response):
            break
    return response

####################
# .\core\skill.py
####################

import item
import event
import battle
import enums

class SkillType(enums.Enum):
    SINGLE = item.Item("single", "Single Target")
    BLAST = item.Item("blast", "Blast")
    BOUNCE = item.Item("bounce", "Bounce")
    AOE = item.Item("aoe", "AoE")
    RESTORE = item.Item("restore", "Restore")
    SUPPORT = item.Item("support", "Support")
    OTHERS = item.Item("others", "Others")
    ALL = (SINGLE, BLAST, BOUNCE, AOE, RESTORE, SUPPORT, OTHERS)
SkillType.init()

class Skill(item.Item):
    def __init__(self, nameid, name, type, t, level=None):
        super().__init__(nameid, name)
        self.type = type
        self.target = t
        self.level = level
    
    def available(self):
        return "ok"

class SkillGroup:
    def __init__(self, t):
        self.target = t
        self.skills = item.ItemList()
        self.current = 0
        battle.current.event_bus.add_member_listener(self.skill_group_trigger, t)
    
    def available(self):
        return self.skills[self.current].available()
    
    def add(self, skill):
        self.skills.append(skill)
    
    def set_level(self, level):
        for skill in self.skills:
            skill.level = level
    
    def set_bonus_level(self, level):
        for skill in self.skills:
            skill.bonus_level += level
    
    @event.member_listener(priority=event.ListenerPriority.EXECUTE)
    async def skill_group_trigger(self, skill_group):
        if self is not skill_group:
            return
        await battle.current.event_bus.dispatch("skill_trigger", self.skills[self.current])

####################
# .\core\target.py
####################

import json
import importlib
import collections

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
        
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def die(self, dmg):
        if self is not dmg.target:
            return
        # TODO
        #message = {"type": "die"} | self.get_info()
        #await server.send_and_recv(message)
        self.dying_stage = DyingStage.DEAD
        battle.current.refresh()
    
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
        def __init__(self, nameid, name, type, t, delta_skillpoints):
            super().__init__(nameid, name, type, t)
            self.delta_skillpoints = delta_skillpoints
            self.bonus_level = 0
            battle.current.event_bus.add_member_listener(self.skill_trigger_pre, t)
        
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

    def __init__(self, nameid, name, element, path):
        super().__init__(nameid, name, None)
        self.element = element
        self.path = path
        self.stats.new_stats(
            ["crt_rate", "crt_dmg", "taunt", "energy", "max_energy", "energy_regen_rate", "break_eff", "base_break_dmg", "healing_boost"], self)
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
    
    def set_record(self, record):
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
        # 光锥和遗器的apply在各子类的set_record中调用（位于基础属性设置完成之后）
    
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
        dmg = damage.Damage(self, tr.target, self.stats["base_break_dmg"], self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
        await battle.current.event_bus.dispatch("deal_damage", dmg)
        Target.NormalTurn.delay_target(tr.target, 0.25)
        if self.element is enums.Element.ICE:
            dmg = damage.Damage(self, tr.target, self.stats["base_break_dmg"], self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
            dmg.factors[damage.DamageFactorType.MULTIPLIER] = 1
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

