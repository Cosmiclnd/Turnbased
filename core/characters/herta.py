from .. import target
from .. import skill
from .. import battle
from .. import event
from .. import event_types
from .. import damage
from .. import modifier
from .. import enums
from .. import effect
from .. import action
from .. import auto_battle
from ..decision import base as decision
from ..monsters import base as monster

from . import base

class Herta(base.Character):
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
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            event.bus.dispatch(event_types.Hit(dmg))
            if self.target.eidolons >= 1:
                hp = t.stats["hp"].calculate()
                if t.cur_hp <= hp * self.target.config.get_skill_value("eidolon1", "hp_threshold"):
                    dmg = damage.Damage.create(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.target.config.get_skill_value("eidolon1", "percentage"))),
                        self.target.element, damage.DmgType.ADDITIONAL, damage.DmgSource.BASIC_ATK)
                    event.bus.dispatch(event_types.AdditionalDamage(dmg))
            event.bus.dispatch(event_types.Attack.End(self.target))

    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            event.bus.dispatch(event_types.Attack.Start(self.target))
            for ratio in (0.3, 0.7):
                for t in battle.current.monsters.copy():
                    dmg = damage.Damage.create(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                        self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
                    dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                    dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                    if t.cur_hp >= t.stats["hp"].calculate() * self.get_value("hp_threshold"):
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.get_value("dmg_boost")
                        if self.target.traces_unlocked[0]:
                            dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("bonus_trace1", "dmg_boost")
                    dmg.hit_split_ratio = ratio
                    event.bus.dispatch(event_types.Hit(dmg))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            event.bus.dispatch(event_types.Attack.Start(self.target))
            for t in battle.current.monsters.copy():
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ULTIMATE)
                dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                if self.target.traces_unlocked[2] and t.effects.has_debuff(effect.Debuff.FROZEN):
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("bonus_trace3", "dmg_boost")
                event.bus.dispatch(event_types.Hit(dmg))
            if self.target.eidolons >= 6:
                eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "eidolon6"),
                    self.target.config.get_skill_value("eidolon6", "duration"))
                event.bus.dispatch(event_types.AddEffect(eff_add))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class Talent(base.Character.CharacterSkill):
        class FollowUp(target.Target.ExtraTurn):
            def __init__(self, t, skill):
                super().__init__(f"{t.nameid}_follow_up_turn", f"{t.name}'s Follow Up Turn", action.ExtraTurn.Priority.FOLLOW_UP, t)
                self.skill = skill
                
                event.bus.add_member_listener(self.extra_turn, self, self)

            def dead(self):
                if super().dead():
                    return True
                return self.skill.attacks == 0
            
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

        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            self.attacks = 0
            self.follow_up_launched = False
            self.immune_targets = []

            event.bus.add_member_listener(self.skill_trigger, self, t)
            event.bus.add_member_listener(self.hit, None, t)
            if not battle.current.features.get("herta_follow_up_not_reset_at_new_wave"):
                event.bus.add_member_listener(self.reset, None, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            event.bus.dispatch(event_types.Attack.Start(self.target))
            i = 0
            while i < self.attacks and battle.current.monsters:
                for t in battle.current.monsters.copy():
                    dmg = damage.Damage.create(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                        self.target.element, damage.DmgType.NORMAL, damage.DmgSource.FOLLOW_UP)
                    dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                    dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                    if self.target.eidolons >= 4:
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("eidolon4", "dmg_boost")
                    event.bus.dispatch(event_types.Hit(dmg))
                if self.target.eidolons >= 2:
                    eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "eidolon2"), -1)
                    event.bus.dispatch(event_types.AddEffect(eff_add))
                i += 1
            event.bus.dispatch(event_types.Attack.End(self.target))
            self.attacks = 0
        
        @event.member_listener(event_types.Hit.AFTER_HIT)
        def hit(self, e):
            dmg = e.dmg
            if dmg.target in self.immune_targets or not isinstance(dmg.target, monster.Monster):
                return
            hp_threshold = dmg.target.stats["hp"].calculate() * self.get_value("hp_threshold")
            if dmg.target.cur_hp <= hp_threshold:
                self.attacks += 1
                self.immune_targets.append(dmg.target)
                if not self.follow_up_launched:
                    self.follow_up_launched = True
                    battle.current.action_list.extras.append(Herta.Talent.FollowUp(self.target, self))
        
        @event.member_listener(event_types.NewWave.BEFORE_RESET)
        def reset(self, e):
            self.attacks = 0
    
    class Technique(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "technique"),
                self.get_value("duration"))
            event.bus.dispatch(event_types.AddEffect(eff_add))
        
    def __init__(self, record):
        self.set_auto_battle(AutoBattlePolicy(self))
        super().__init__("herta", record)
    
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
        names = self.config.get_skill_name("technique")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.BASE, self.config.get_skill_value("technique", "atk_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END,
            1, "atk", mod), "technique")

        names = self.config.get_skill_name("eidolon2")
        mod = modifier.Modifier(*names, modifier.StatDesc((None, None, self.config.get_skill_value("eidolon2", "crt_rate_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.PERMANENT,
            self.config.get_skill_value("eidolon2", "max_stacks"), "crt_rate", mod), "eidolon2")
        
        names = self.config.get_skill_name("eidolon6")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.BASE, self.config.get_skill_value("eidolon6", "atk_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END_CHECK_START,
            1, "atk", mod), "eidolon6")
    
    @event.member_listener(override=base.Character.set_passives)
    def set_passives(self, e):
        super().set_passives(e)

        if self.traces_unlocked[1]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace2"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace2", "control_res"))),
                None, self)
            self.stats["control_res"].modifiers.append(mod)

import random

class AutoBattlePolicy(auto_battle.AutoBattlePolicy):
    def skill_target(self, skill_group):
        if skill_group is self.target.skills["basic_atk"]:
            return random.choice(battle.current.monsters)
