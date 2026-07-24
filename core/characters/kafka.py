from .. import item
from .. import enums
from .. import target
from .. import event
from .. import event_types
from .. import battle
from .. import modifier
from .. import damage
from .. import effect
from .. import action
from .. import auto_battle
from ..decision import base as decision
from ..monsters import base as monster

from . import base

class Kafka(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            t = self.get_main_target()
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1((t,))
            event.bus.dispatch(event_types.Attack.Start(self.target))
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.set_toughness_reduction(damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element))
            dmg.energy_regen = self.get_value("energy_regen")
            for ratio in (0.5, 0.5):
                dmg.hit_split_ratio = ratio
                event.bus.dispatch(event_types.Hit(dmg))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1([self.get_main_target()] + self.get_adjacent_targets())
            event.bus.dispatch(event_types.Attack.Start(self.target))
            t = self.get_main_target()
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("main_percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
            dmg.set_toughness_reduction(damage.ToughnessReduction(self.get_value("main_toughness_reduction"), self.target.element))
            dmg.energy_regen = self.get_value("energy_regen")
            for ratio in (0.2, 0.3, 0.5):
                dmg.hit_split_ratio = ratio
                event.bus.dispatch(event_types.Hit(dmg))
            for t in self.get_adjacent_targets():
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("sub_percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
                dmg.set_toughness_reduction(damage.ToughnessReduction(self.get_value("sub_toughness_reduction"), self.target.element))
                event.bus.dispatch(event_types.Hit(dmg))
            event.bus.dispatch(event_types.Attack.End(self.target))
            event.bus.dispatch(event_types.TickDot(
                damage.DotTick(self.get_main_target(), lambda x: True, self.get_value("main_dot_tick_percentage"))))
            for t in self.get_adjacent_targets():
                event.bus.dispatch(event_types.TickDot(damage.DotTick(t, lambda x: True, self.get_value("sub_dot_tick_percentage"))))
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1(battle.current.monsters.copy())
            event.bus.dispatch(event_types.Attack.Start(self.target))
            for t in battle.current.monsters.copy():
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ULTIMATE)
                dmg.set_toughness_reduction(damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element))
                event.bus.dispatch(event_types.Hit(dmg))
                self.target.inflict_shock(t, self.get_value("duration"), self.get_value("base_chance"))
            event.bus.dispatch(event_types.Attack.End(self.target))
            for t in battle.current.monsters.copy():
                event.bus.dispatch(event_types.TickDot(damage.DotTick(t, lambda x: True, self.get_value("dot_tick_percentage"))))
            event.bus.dispatch(event_types.RegenEnergy(self.target, self.get_value("energy_regen")))
            if self.target.traces_unlocked[2]:
                self.target.regain_follow_up_count()
    
    class Talent(base.Character.CharacterSkill):
        class FollowUp(target.Target.ExtraTurn):
            def __init__(self, t, skill):
                super().__init__(f"{t.nameid}_follow_up_turn", f"{t.name}'s Follow Up Turn", action.ExtraTurn.Priority.FOLLOW_UP, t)
                self.skill = skill

                event.bus.add_member_listener(self.extra_turn, self, self)
                if not battle.current.features.get("kafka_follow_up_not_reset_at_new_wave"):
                    event.bus.add_member_listener(self.reset, None, self)
            
            def on_removed(self, list):
                super().on_removed(list)
                if list is battle.current.action_list.extras:
                    self.skill.follow_up_launched = False
            
            def is_follow_up(self):
                return True
            
            @event.member_listener(event_types.ExtraTurn.EXECUTE)
            def extra_turn(self, e):
                decision.provider.notify({"name": f"{self.target.nameid}.follow_up_turn", "target": str(self.target.uuid)})
                self.skill.follow_up_launched = False
                event.bus.dispatch(event_types.SkillTrigger(self.skill))
                self.master.dead_toggle = True
        
            @event.member_listener(event_types.NewWave.BEFORE_RESET)
            def reset(self, e):
                self.master.dead_toggle = True

        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            self.follow_up_launched = False
            self.skill_target = None

            event.bus.add_member_listener(self.skill_trigger, self, t)
            event.bus.add_member_listener(self.attack_end, None, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            self.target.follow_up_count -= 1
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1((self.skill_target,))
            event.bus.dispatch(event_types.Attack.Start(self.target))
            dmg = damage.Damage.create(self.target, self.skill_target,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.FOLLOW_UP)
            dmg.set_toughness_reduction(damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element))
            dmg.energy_regen = self.get_value("energy_regen")
            for ratio in (0.15, 0.15, 0.15, 0.15, 0.15, 0.25):
                dmg.hit_split_ratio = ratio
                event.bus.dispatch(event_types.Hit(dmg))
                self.target.inflict_shock(self.skill_target, self.get_value("duration"), self.get_value("base_chance"))
            event.bus.dispatch(event_types.Attack.End(self.target))
            if self.target.traces_unlocked[2]:
                event.bus.dispatch(event_types.TickDot(damage.DotTick(self.skill_target, lambda x: True,
                    self.target.config.get_skill_value("bonus_trace3", "dot_tick_percentage"))))
        
        @event.member_listener(event_types.Attack.End.EXECUTE)
        def attack_end(self, e):
            if (self.target is e.target or not isinstance(e.target, base.Character) or
                self.target.follow_up_count == 0 or self.follow_up_launched):
                return
            self.follow_up_launched = True
            battle.current.action_list.extras.append(self.FollowUp(self.target, self))
            self.skill_target = self.get_main_target() or battle.current.random.character_target()
    
    class Technique(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            event.bus.dispatch(event_types.Attack.Start(self.target))
            for t in battle.current.monsters.copy():
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
                dmg.set_toughness_reduction(damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element))
                event.bus.dispatch(event_types.Hit(dmg))
                self.target.inflict_shock(t, self.get_value("duration"), self.get_value("base_chance"))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class DotDmgVulnerabilityEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    event.bus.add_member_listener(self.deal_damage, None, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
            def deal_damage(self, e):
                dmg = e.dmg
                if self.target is not e.dmg.target or not e.dmg.is_dot_dmg():
                    return
                dmg.factors[damage.DamageFactorType.VULNERABILITY] += self.effect.amount

        def __init__(self, nameid, name, amount):
            super().__init__(nameid, name, effect.Effect.Type.DEBUFF, effect.Effect.DurationType.TURN_END, 1)
            self.amount = amount
    
    class NormalTurn(target.Target.NormalTurn):
        def __init__(self, t):
            super().__init__(t)

            event.bus.add_member_listener(self.normal_turn_end, self, self)
        
        @event.member_listener(event_types.NormalTurn.End.EXECUTE)
        def normal_turn_end(self, e):
            self.target.regain_follow_up_count()
    
    def __init__(self, record):
        self.set_auto_battle(AutoBattlePolicy(self))
        super().__init__("kafka", record)

        if self.traces_unlocked[1]:
            event.bus.add_member_listener(self.monster_cleaned, None, self)
        if self.eidolons >= 2:
            event.bus.add_member_listener(self.deal_damage_eidolon2, None, self)
        if self.eidolons >= 4:
            event.bus.add_member_listener(self.deal_damage_eidolon4, None, self)
    
    def set_record(self, record):
        super().set_record(record)

        if self.eidolons >= 3:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
        if self.eidolons >= 5:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)

        self.set_effect_types()
    
    def set_effect_types(self):
        percentage = self.get_current_skill("ultimate").get_value("dot_percentage")
        if self.eidolons >= 6:
            percentage += self.config.get_skill_value("eidolon6", "percentage")
        dmg_desc = damage.DamageDesc(self,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.CALCULATED, percentage)),
            enums.Element.LIGHTNING, damage.DmgType.DOT, damage.DmgSource.DOT)
        self.effect_types.add_unique(effect.DotEffect("shock", "Shock", dmg_desc, effect.Debuff.SHOCK, 1))

        self.effect_types.add_unique(self.DotDmgVulnerabilityEffect(*self.config.get_skill_name("eidolon1"),
            self.config.get_skill_value("eidolon1", "dot_dmg_vulnerability")), "eidolon1")
    
    def regain_follow_up_count(self):
        self.follow_up_count = min(self.follow_up_count + 1, self.get_current_skill("talent").get_value("trigger_count"))
    
    def validator_trace1(self, stat, **kwargs):
        return stat.target.stats["eff_hr"].calculate() >= self.config.get_skill_value("bonus_trace1", "eff_hr_threshold")

    @event.member_listener(override=base.Character.set_passives)
    def set_passives(self, e):
        super().set_passives(e)

        self.follow_up_count = self.get_current_skill("talent").get_value("trigger_count")

        if self.traces_unlocked[0]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace1"),
                modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.config.get_skill_value("bonus_trace1", "atk_boost"))),
                self.validator_trace1, self)
            for c in battle.current.characters:
                c.stats["atk"].modifiers.append(mod)
    
    @event.member_listener(event_types.Clean.AFTER_EXECUTE)
    def monster_cleaned(self, e):
        if not isinstance(e.target, monster.Monster):
            return
        context = e.target.death_state.killing_dmg.context
        if context.effect is not None and context.effect.is_debuff_type(effect.Debuff.SHOCK):
            event.bus.dispatch(event_types.RegenEnergy(self, self.config.get_skill_value("bonus_trace2", "energy_regen")))
    
    @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
    def deal_damage_eidolon2(self, e):
        dmg = e.dmg
        if not isinstance(dmg.target, monster.Monster) or not dmg.is_dot_dmg():
            return
        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.config.get_skill_value("eidolon2", "dot_dmg_boost")
    
    @event.member_listener(event_types.Damage.AFTER_TAKE)
    def deal_damage_eidolon4(self, e):
        dmg = e.dmg
        if not isinstance(dmg.target, monster.Monster) or not dmg.is_dot_dmg():
            return
        context = dmg.context
        if context.effect is not None and context.effect.is_debuff_type(effect.Debuff.SHOCK) and context.effect_instance.caster is self:
            event.bus.dispatch(event_types.RegenEnergy(self, self.config.get_skill_value("eidolon4", "energy_regen")))
    
    def inflict_shock(self, t, duration, base_chance):
        if self.eidolons >= 6:
            duration += self.config.get_skill_value("eidolon6", "duration")
        eff_add = effect.EffectAddition(self, t, self.effect_types.get(self.nameid, "shock"), duration)
        self.try_apply_debuff(eff_add, base_chance)
    
    def dot_dmg_vulnerability_eidolon1(self, targets):
        for t in targets:
            eff_add = effect.EffectAddition(self, t, self.effect_types.get(self.nameid, "eidolon1"),
                self.config.get_skill_value("eidolon1", "duration"))
            self.try_apply_debuff(eff_add, self.config.get_skill_value("eidolon1", "base_chance"))

import random

class AutoBattlePolicy(auto_battle.AutoBattlePolicy):
    def skill_target(self, skill_group):
        if skill_group in (self.target.skills["basic_atk"], self.target.skills["skill"]):
            return random.choice(battle.current.monsters)
