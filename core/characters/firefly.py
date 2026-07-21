from .. import item
from .. import enums
from .. import target
from .. import event
from .. import event_types
from .. import battle
from .. import modifier
from .. import damage
from .. import effect
from .. import healing
from .. import action
from .. import auto_battle
from ..decision import base as decision

from . import base

class Firefly(base.Character):
    class FireflyEnhancedSkill(base.Character.CharacterSkill):
        def before_skill_trigger(self):
            super().before_skill_trigger()
            names = self.target.config.get_skill_name("ultimate")
            ultimate = self.target.get_current_skill("ultimate")
            wb_eff_mod = modifier.Modifier(*names,
                modifier.StatDesc((None, None, ultimate.get_value("wb_eff_boost"))), None, self.skill_dead)
            self.target.stats["wb_eff"].modifiers.append(wb_eff_mod)
            break_dmg_boost_mod = modifier.Modifier(*names,
                modifier.StatDesc((None, None, ultimate.get_value("break_dmg_boost"))), None, self.skill_dead)
            self.target.stats["break_dmg_boost"].modifiers.append(break_dmg_boost_mod)
            if self.target.eidolons >= 2:
                battle.current.event_bus.add_member_listener_legacy(self.weakness_break, self.skill_dead)
                battle.current.event_bus.add_member_listener_legacy(self.clean, self.skill_dead)
            if self.target.eidolons >= 6:
                wb_eff_mod = modifier.Modifier(*self.target.config.get_skill_name("eidolon6"),
                    modifier.StatDesc((None, None, self.target.config.get_skill_value("eidolon6", "wb_eff_boost"))), None, self.skill_dead)
                self.target.stats["wb_eff"].modifiers.append(wb_eff_mod)
        
        @event.member_listener_legacy(event.ListenerPriority.POST_PROCESS)
        def weakness_break(self, tr):
            if self.target.extra_normal_turn_triggered or self.target is not tr.dealer:
                return
            battle.current.action_list.extras.append(target.Target.ExtraNormalTurn(self.target))
            self.target.extra_normal_turn_triggered = True
        
        @event.member_listener_legacy(event.ListenerPriority.POST_PROCESS)
        def clean(self, t):
            if self.target.extra_normal_turn_triggered or self.target is not t.death_state.killing_dmg.dealer:
                return
            battle.current.action_list.extras.append(target.Target.ExtraNormalTurn(self.target))
            self.target.extra_normal_turn_triggered = True

    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            t = self.get_main_target()
            battle.current.event_bus.dispatch_legacy("attack_start", self.target)
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            battle.current.event_bus.dispatch_legacy("hit", dmg)
            battle.current.event_bus.dispatch_legacy("attack_end", self.target)
    
    class EnhancedBasicAtk(FireflyEnhancedSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            heal = healing.Healing(self.target, self.target,
                modifier.StatDesc((self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("heal_percentage"))))
            battle.current.event_bus.dispatch_legacy("heal", heal)
            t = self.get_main_target()
            battle.current.event_bus.dispatch_legacy("attack_start", self.target)
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ENHANCED_BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            for ratio in (0.15, 0.15, 0.15, 0.15, 0.4):
                dmg.hit_split_ratio = ratio
                battle.current.event_bus.dispatch_legacy("hit", dmg)
            battle.current.event_bus.dispatch_legacy("attack_end", self.target)
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            self.target.consume_hp(self.target.stats["hp"].calculate() * self.get_value("hp_cost"))
            battle.current.event_bus.dispatch_legacy("regen_energy", self.target,
                self.target.stats["max_energy"].calculate() * self.get_value("energy_regen_rate"), True)
            t = self.get_main_target()
            battle.current.event_bus.dispatch_legacy("attack_start", self.target)
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            for ratio in (0.4, 0.6):
                dmg.hit_split_ratio = ratio
                battle.current.event_bus.dispatch_legacy("hit", dmg)
            battle.current.event_bus.dispatch_legacy("attack_end", self.target)
            self.target.cur_normal_turn.advance_next_turn(self.get_value("advance_scale"))
    
    class EnhancedSkill(FireflyEnhancedSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            if self.target.eidolons >= 1:
                event.bus.add_member_listener(self.deal_damage, self.target, self.skill_dead)
            heal = healing.Healing(self.target, self.target,
                modifier.StatDesc((self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("heal_percentage"))))
            battle.current.event_bus.dispatch_legacy("heal", heal)
            for t in [self.get_main_target()] + self.get_adjacent_targets():
                eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "fire_weakness"),
                    self.get_value("duration"))
                battle.current.event_bus.dispatch_legacy("add_effect", eff_add)
            battle.current.event_bus.dispatch_legacy("attack_start", self.target)
            main_mult = self.get_value("main_break_eff_percentage") * min(self.target.stats["break_eff"].calculate(),
                self.get_value("break_eff_cap")) + self.get_value("main_percentage")
            sub_mult = self.get_value("sub_break_eff_percentage") * min(self.target.stats["break_eff"].calculate(),
                self.get_value("break_eff_cap")) + self.get_value("sub_percentage")
            for ratio in (0.15, 0.15, 0.15, 0.15, 0.4):
                t = self.get_main_target()
                main_dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, main_mult)),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ENHANCED_SKILL)
                main_dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("main_toughness_reduction"),
                    self.target.element)
                main_dmg.hit_split_ratio = ratio
                battle.current.event_bus.dispatch_legacy("hit", main_dmg)
                for t in self.get_adjacent_targets():
                    sub_dmg = damage.Damage.create(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, sub_mult)),
                        self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ENHANCED_SKILL)
                    sub_dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("sub_toughness_reduction"),
                        self.target.element)
                    sub_dmg.hit_split_ratio = ratio
                    battle.current.event_bus.dispatch_legacy("hit", sub_dmg)
            battle.current.event_bus.dispatch_legacy("attack_end", self.target)
        
        @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
        def deal_damage(self, e):
            dmg.factors[damage.DamageFactorType.DEF_BOOST] -= self.target.config.get_skill_value("eidolon1", "def_ignore")
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            self.target.energy_maxed = False
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "complete_combustion"), -1)
            battle.current.event_bus.dispatch_legacy("add_effect", eff_add)
            battle.current.event_bus.dispatch_legacy("action_advance", self.target.cur_normal_turn, self.get_value("advance_scale"))
            battle.current.event_bus.dispatch_legacy("regen_energy", self.target, self.get_value("energy_regen"))
    
    class Talent(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.reduce_damage, None, t)
    
        @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
        def reduce_damage(self, e):
            dmg = e.dmg
            if self.target is not dmg.target:
                return
            max_reduction = self.target.get_current_skill("talent").get_value("max_dmg_reduction")
            if self.target.effects.has_effect(self.target.effect_types.get(self.target.nameid, "complete_combustion")):
                dmg.factors[damage.DamageFactorType.MITIGATION] *= 1 - max_reduction
                return
            threshold = self.target.get_current_skill("talent").get_value("hp_threshold")
            hp_rate = max(self.target.cur_hp / self.target.stats["hp"].calculate(), threshold)
            dmg.factors[damage.DamageFactorType.MITIGATION] *= 1 - max_reduction / (threshold - 1) * (hp_rate - 1)
    
        @event.member_listener_legacy(event.ListenerPriority.POST_PROCESS)
        def regen_energy(self, t, amount, fixed=False):
            if self.target is not t:
                return
            if self.target.check_ultimate_energy() and not self.target.energy_maxed:
                self.target.effects.dispel(0, lambda eff: eff.type is effect.Effect.Type.DEBUFF)
                self.target.energy_maxed = True
    
    class Technique(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener_legacy(self.new_wave_start, t)

        @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
        def new_wave_start(self):
            for t in battle.current.monsters:
                eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "fire_weakness"),
                    self.get_value("duration"))
                battle.current.event_bus.dispatch_legacy("add_effect", eff_add)
            battle.current.event_bus.dispatch_legacy("attack_start", self.target)
            for t in battle.current.monsters:
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
                dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                battle.current.event_bus.dispatch_legacy("hit", dmg)
            battle.current.event_bus.dispatch_legacy("attack_end", self.target)
    
    class CompleteCombustionCountdown(action.NormalTurn):
        def __init__(self, t):
            self.spd = modifier.Stat("spd", self)
            self.spd.base_value = t.get_current_skill("ultimate").get_value("countdown_spd")
            super().__init__("complete_combustion_countdown", "Complete Combustion Countdown", self.spd, item.DeadToggle(t))
            self.target = t
            self.target.complete_combustion_countdown = self

            battle.current.event_bus.add_member_listener_legacy(self.normal_turn, self)
        
        @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
        def normal_turn(self, turn):
            if self is not turn:
                return
            decision.provider.notify({"name": f"{self.target.nameid}.complete_combustion_countdown", "target": str(self.target.uuid)})
            self.target.effects.delete(self.target.effect_types.get(self.target.nameid, "complete_combustion"))
            self.master.dead_toggle = True
            self.target.complete_combustion_countdown = None
    
    class CompleteCombustionEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    mod = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc((None, None, self.target.get_current_skill("ultimate").get_value("spd_boost"))), None, self.eff_dead)
                    self.target.stats["spd"].modifiers.append(mod)
                    if self.target.traces_unlocked[0]:
                        mod = modifier.Modifier(*self.target.config.get_skill_name("bonus_trace1"),
                            modifier.StatDesc((None, None, self.target.config.get_skill_value("bonus_trace1", "break_eff_boost"))), None,
                            self.eff_dead)
                        self.target.stats["break_eff"].modifiers.append(mod)
                        self.delay_triggers = self.target.config.get_skill_value("bonus_trace1", "trigger_count")
                        battle.current.event_bus.add_member_listener_legacy(self.weakness_break, self.eff_dead)
                    if self.target.traces_unlocked[1]:
                        battle.current.event_bus.add_member_listener_legacy(self.reduce_toughness, self.eff_dead)
                    if self.target.eidolons >= 4:
                        mod = modifier.Modifier(*self.target.config.get_skill_name("eidolon4"),
                            modifier.StatDesc((None, None, self.target.config.get_skill_value("eidolon4", "eff_res_boost"))), None,
                            self.eff_dead)
                        self.target.stats["eff_res"].modifiers.append(mod)
                    if self.target.eidolons >= 6:
                        mod = modifier.Modifier(*self.target.config.get_skill_name("eidolon6"),
                            modifier.StatDesc((None, None, self.target.config.get_skill_value("eidolon6", "fire_res_pen_boost"))), None,
                            self.eff_dead)
                        self.target.stats["fire_res_pen"].modifiers.append(mod)
                    battle.current.action_list.normals.append(Firefly.CompleteCombustionCountdown(self.target))
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener_legacy(event.ListenerPriority.EXECUTE - 1)
            def weakness_break(self, tr):
                if self.target is not tr.dealer or tr.damage is None or tr.damage.context.source not in (damage.DmgSource.ENHANCED_BASIC_ATK,
                    damage.DmgSource.ENHANCED_SKILL):
                    return
                if self.delay_triggers > 0:
                    self.delay_triggers -= 1
                    battle.current.event_bus.dispatch_legacy("action_delay", self.target.complete_combustion_countdown,
                        self.target.config.get_skill_value("bonus_trace1", "delay_scale"))
            
            @event.member_listener_legacy(event.ListenerPriority.EXECUTE - 1)
            def reduce_toughness(self, tr):
                if self.target is not tr.dealer or not tr.target.weakness_broken:
                    return
                break_eff = self.target.stats["break_eff"].calculate()
                if break_eff >= self.target.config.get_skill_value("bonus_trace2", "break_eff_threshold2"):
                    battle.current.event_bus.dispatch_legacy("additional_damage",
                        tr.to_super_break_dmg(self.target.config.get_skill_value("bonus_trace2", "percentage2")))
                elif break_eff >= self.target.config.get_skill_value("bonus_trace2", "break_eff_threshold1"):
                    battle.current.event_bus.dispatch_legacy("additional_damage",
                        tr.to_super_break_dmg(self.target.config.get_skill_value("bonus_trace2", "percentage1")))

        def __init__(self):
            super().__init__("complete_combustion", "Complete Combustion", effect.Effect.Type.BUFF,
                effect.Effect.DurationType.PERMANENT, 1, False)
    
    def __init__(self, record):
        self.set_auto_battle(AutoBattlePolicy(self))
        super().__init__("firefly", record)

        battle.current.event_bus.add_member_listener_legacy(self.battle_start, self)
        if self.eidolons >= 2:
            battle.current.event_bus.add_member_listener_legacy(self.normal_turn_start, self)
    
    def init_skills(self):
        super().init_skills()
        self.skills["basic_atk"].add(self.EnhancedBasicAtk(self, "enhanced_basic_atk"))
        self.skills["skill"].add(self.EnhancedSkill(self, "enhanced_skill"))
        self.skills["basic_atk"].selector = self.basic_atk_selector
        self.skills["skill"].selector = self.skill_selector
    
    def set_record(self, record):
        super().set_record(record)
        
        if self.eidolons >= 3:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)
        if self.eidolons >= 5:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)

        self.set_effect_types()
    
    def set_effect_types(self):
        self.effect_types.add_unique(self.CompleteCombustionEffect())
        self.effect_types.add_unique(effect.AdditionalWeaknessEffect("fire_weakness", "Fire Weakness", 
            effect.Effect.DurationType.TURN_END, enums.Element.FIRE, False))
    
    def basic_atk_selector(self, group):
        if self.effects.has_effect(self.effect_types.get(self.nameid, "complete_combustion")):
            return group.skills[1]
        else:
            return group.skills[0]
    
    def skill_selector(self, group):
        if self.effects.has_effect(self.effect_types.get(self.nameid, "complete_combustion")):
            return group.skills[1]
        else:
            return group.skills[0]
    
    def ultimate_available(self):
        if not super().ultimate_available():
            return False
        return not self.effects.has_effect(self.effect_types.get(self.nameid, "complete_combustion"))

    @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
    def battle_start(self):
        self.complete_combustion_countdown = None
        self.energy_maxed = False

        if self.traces_unlocked[2]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace3"),
                modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.SELF_CONVERSION,
                    modifier.StatConverter(
                        self.config.get_skill_value("bonus_trace3", "atk_threshold"),
                        self.config.get_skill_value("bonus_trace3", "atk_step"),
                        self.config.get_skill_value("bonus_trace3", "break_eff_boost"),
                        None
                    ))), None, self)
            self.stats["break_eff"].modifiers.append(mod)
        
        half_energy = self.stats["max_energy"].calculate() * 0.5
        if self.cur_energy < half_energy:
            battle.current.event_bus.dispatch_legacy("regen_energy", self, half_energy - self.cur_energy, True)
        
        if self.eidolons >= 1:
            self.skills["skill"].skills[1].delta_skillpoints = 0
        
        if self.eidolons >= 2:
            self.extra_normal_turn_triggered = True
        
    @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
    def normal_turn_start(self, turn):
        if self is not turn.target:
            return
        self.extra_normal_turn_triggered = False

import random

class AutoBattlePolicy(auto_battle.AutoBattlePolicy):
    def skill_target(self, skill_group):
        if skill_group in (self.target.skills["basic_atk"], self.target.skills["skill"]):
            return random.choice(battle.current.monsters)
