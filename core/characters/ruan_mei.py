from .. import item
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

class RuanMei(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            t = self.get_main_target()
            event.bus.dispatch(event_types.Attack.Start(self.target))
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.set_toughness_reduction(damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element))
            dmg.energy_regen = self.get_value("energy_regen")
            event.bus.dispatch(event_types.Hit(dmg))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "overtone"),
                self.get_value("duration"))
            event.bus.dispatch(event_types.AddEffect(eff_add))
            event.bus.dispatch(event_types.RegenEnergy(self.target, self.get_value("energy_regen")))
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            duration = self.get_value("duration")
            if self.target.eidolons >= 6:
                duration += self.target.config.get_skill_value("eidolon6", "duration")
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "zone"), duration)
            event.bus.dispatch(event_types.AddEffect(eff_add))
            event.bus.dispatch(event_types.RegenEnergy(self.target, self.get_value("energy_regen")))
    
    class Talent(base.Character.CharacterSkill):
        pass
    
    class Technique(base.Character.CharacterSkill):
        class ExtraTurn(target.Target.ExtraTurn):
            def __init__(self, t, skill):
                super().__init__(f"{t.nameid}_technique_turn", f"{t.name}'s Technique Turn", action.ExtraTurn.Priority.NORMAL, t)
                self.skill = skill

                event.bus.add_member_listener(self.extra_turn, self, self)
            
            @event.member_listener(event_types.ExtraTurn.EXECUTE)
            def extra_turn(self, e):
                decision.provider.notify({"name": f"{self.target.nameid}.technique_turn", "target": str(self.target.uuid)})
                delta_skillpoints = self.skill.delta_skillpoints
                self.skill.delta_skillpoints = 0
                battle.current.cur_main_target = self.target
                event.bus.dispatch(event_types.SkillTrigger(self.skill))
                self.skill.delta_skillpoints = delta_skillpoints
                self.master.dead_toggle = True

        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            battle.current.action_list.extras.append(self.ExtraTurn(self.target, self.target.get_current_skill("skill")))
    
    class OvertoneEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.mod_dead = item.DeadToggle(self.target)
                    skill = self.target.get_current_skill("skill")
                    mod_dmg_boost = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc((None, None, skill.get_value("dmg_boost"))), None, self.mod_dead)
                    for c in battle.current.characters:
                        c.stats["dmg_boost"].modifiers.append(mod_dmg_boost)
                    mod_wb_eff = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc((None, None, skill.get_value("wb_eff_boost"))), None, self.mod_dead)
                    for c in battle.current.characters:
                        c.stats["wb_eff"].modifiers.append(mod_wb_eff)
                elif self.old_stacks != 0 and stacks == 0:
                    self.mod_dead.dead_toggle = True
                self.old_stacks = stacks

        def __init__(self):
            super().__init__("overtone", "Overtone", effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_START, 1)
    
    class ZoneEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    mod_res_pen = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc((None, None, self.target.get_current_skill("ultimate").get_value("res_pen_boost"))),
                        None, self.eff_dead)
                    for c in battle.current.characters:
                        c.stats["res_pen"].modifiers.append(mod_res_pen)
                    event.bus.add_member_listener(self.hit, None, self.eff_dead)
                    if self.target.eidolons >= 1:
                        event.bus.add_member_listener(self.deal_damage, None, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
        
            @event.member_listener(event_types.Hit.BEFORE_HIT)
            def hit(self, e):
                dmg = e.dmg
                if not isinstance(dmg.target, monster.Monster):
                    return
                if not dmg.target.effects.has_effect(self.target.effect_types.get(self.target.nameid, "thanatoplum_rebloom")):
                    eff_add = effect.EffectAddition(self.target, dmg.target,
                        self.target.effect_types.get(self.target.nameid, "thanatoplum_rebloom"), -1)
                    event.bus.dispatch(event_types.AddEffect(eff_add))
            
            @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
            def deal_damage(self, e):
                dmg = e.dmg
                if not isinstance(dmg.dealer, base.Character):
                    return
                dmg.factors[damage.DamageFactorType.DEF_BOOST] -= self.target.config.get_skill_value("eidolon1", "def_ignore")

        def __init__(self):
            super().__init__("zone", "Zone", effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_START, 1)
    
    class ThanatoplumRebloomEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    event.bus.add_member_listener(self.toughness_recover, self.target, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event_types.RecoverToughness.BEFORE_EXECUTE)
            def toughness_recover(self, e):
                if not self.target.weakness_broken:
                    return
                self.target.effects.delete(self.effect)
                self.effect.immune_targets.append(self.target)
                ultimate = self.effect.target.get_current_skill("ultimate")
                stat_desc = modifier.StatDesc((
                    (self.effect.target.stats["break_eff"], modifier.ModifierFilter.CALCULATED, ultimate.get_value("delay_percentage")),
                    (None, None, ultimate.get_value("delay_flat"))
                ))
                event.bus.dispatch(event_types.ActionDelay(self.target.cur_normal_turn, stat_desc.calculate()))  # TODO: need more tests
                dmg = damage.Damage.create(self.effect.target, self.target,
                    modifier.StatDesc((self.effect.target.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED,
                        ultimate.get_value("percentage"))),
                    self.effect.target.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
                event.bus.dispatch(event_types.AdditionalDamage(dmg))
                event.bus.interrupt(event_types.NormalTurn.Act)

        def __init__(self, t):
            super().__init__("thanatoplum_rebloom", "Thanatoplum Rebloom", effect.Effect.Type.DEBUFF, effect.Effect.DurationType.PERMANENT, 1)
            self.immune_targets = []
            self.target = t
            event.bus.add_member_listener(self.toughness_recover, t, t)
            
        @event.member_listener(event_types.RecoverToughness.EXECUTE)
        def toughness_recover(self, e):
            if self.target in self.immune_targets:
                self.immune_targets.remove(self.target)
    
    class NormalTurn(target.Target.NormalTurn):
        def __init__(self, t):
            super().__init__(t)

            if self.target.traces_unlocked[1]:
                event.bus.add_member_listener(self.normal_turn_start, self, self)
        
        @event.member_listener(event_types.NormalTurn.Start.EXECUTE)
        def normal_turn_start(self, e):
            event.bus.dispatch(event_types.RegenEnergy(self.target,
                self.target.config.get_skill_value("bonus_trace2", "energy")))

    def __init__(self, record):
        self.set_auto_battle(AutoBattlePolicy(self))
        super().__init__("ruan_mei", record)

        event.bus.add_member_listener(self.weakness_break, None, self)
        if self.eidolons >= 4:
            event.bus.add_member_listener(self.before_weakness_break, None, self)
    
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
        self.effect_types.add_unique(self.OvertoneEffect())
        self.effect_types.add_unique(self.ZoneEffect())
        self.effect_types.add_unique(self.ThanatoplumRebloomEffect(self))

        names = self.config.get_skill_name("talent")
        mod = modifier.Modifier(*names,
            modifier.StatDesc(("spd", modifier.ModifierFilter.BASE, self.get_current_skill("talent").get_value("spd_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.PERMANENT, 1, "spd", mod),
            "talent")

        names = self.config.get_skill_name("eidolon4")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((None, None, self.config.get_skill_value("eidolon4", "break_eff_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END, 1,
            "break_eff", mod), "eidolon4")
    
    @event.member_listener(override=base.Character.set_passives)
    def set_passives(self, e):
        super().set_passives(e)

        for c in battle.current.characters:
            if self is not c:
                eff_add = effect.EffectAddition(self, c, self.effect_types.get(self.nameid, "talent"), -1)
                event.bus.dispatch(event_types.AddEffect(eff_add))

        if self.traces_unlocked[0]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace1"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace1", "break_eff_boost"))), None, self)
            for c in battle.current.characters:
                c.stats["break_eff"].modifiers.append(mod)
        
        if self.traces_unlocked[2]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace3"),
                modifier.StatDesc((self.stats["break_eff"], modifier.ModifierFilter.CALCULATED,  # 经测试可以二次转化
                    modifier.StatConverter(
                        self.config.get_skill_value("bonus_trace3", "break_eff_threshold"),
                        self.config.get_skill_value("bonus_trace3", "break_eff_step"),
                        self.config.get_skill_value("bonus_trace3", "dmg_boost"),
                        self.config.get_skill_value("bonus_trace3", "dmg_boost_cap")
                    ))), None, self)
            for c in battle.current.characters:
                c.stats["dmg_boost"].modifiers.append(mod)
        
        if self.eidolons >= 2:
            mod = modifier.Modifier(*self.config.get_skill_name("eidolon2"),
                modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.config.get_skill_value("eidolon2", "atk_boost"))), self.validator_e2, self)
            for c in battle.current.characters:
                c.stats["atk"].modifiers.append(mod)
    
    def validator_e2(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.target.weakness_broken
    
    @event.member_listener(event_types.BreakWeakness.AFTER_BREAK)
    def weakness_break(self, e):
        if not e.tr.target.death_state.alive:
            return
        mult = self.get_current_skill("talent").get_value("percentage")
        if self.eidolons >= 6:
            mult += self.config.get_skill_value("eidolon6", "percentage")
        dmg = damage.Damage.create(self, e.tr.target,
            modifier.StatDesc((self.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, mult)),
            self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
        event.bus.dispatch(event_types.AdditionalDamage(dmg))
    
    @event.member_listener(event_types.BreakWeakness.BEFORE_BREAK)
    def before_weakness_break(self, e):
        eff_add = effect.EffectAddition(self, self, self.effect_types.get(self.nameid, "eidolon4"),
            self.config.get_skill_value("eidolon4", "duration"))
        event.bus.dispatch(event_types.AddEffect(eff_add))

import random

class AutoBattlePolicy(auto_battle.AutoBattlePolicy):
    def skill_option(self, skill_groups):
        if battle.current.skillpoints.current == 0:
            return skill_groups["basic_atk"]
        if not self.target.effects.has_effect(self.target.effect_types.get(self.target.nameid, "overtone")):
            return skill_groups["skill"]
        return skill_groups["basic_atk"]

    def skill_target(self, skill_group):
        if skill_group is self.target.skills["basic_atk"]:
            return random.choice(battle.current.monsters)
        elif skill_group is self.target.skills["skill"]:
            return self.target
