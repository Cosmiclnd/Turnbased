from .. import target
from .. import event
from .. import event_types
from .. import skill
from .. import battle
from .. import damage
from .. import enums
from .. import modifier
from .. import effect
from .. import action

from . import base

class BlazeOutOfSpace(base.Monster):
    class Skill1(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            t = event.bus.query(event_types.GetMonsterSkillTarget(self.target))
            event.bus.dispatch(event_types.Attack.Start(self.target))
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                enums.Element.FIRE, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            event.bus.dispatch(event_types.Hit(dmg))
            eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "enkindle"),
                self.target.config.get_skill_value("talent", "duration"))
            self.target.try_apply_debuff(eff_add, self.target.config.get_skill_value("talent", "base_chance"))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class Skill2(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "spontaneous_combustion"),
                -1)
            event.bus.dispatch(event_types.AddEffect(eff_add))
    
    class Skill3(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            event.bus.dispatch(event_types.Attack.Start(self.target))
            for i in range(self.get_value("times")):
                t = event.bus.query(event_types.GetMonsterSkillTarget(self.target))
                if t is None:
                    break
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    enums.Element.FIRE, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
                event.bus.dispatch(event_types.Hit(dmg))
                eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "enkindle"),
                    self.target.config.get_skill_value("talent", "duration"))
                self.target.try_apply_debuff(eff_add, self.target.config.get_skill_value("talent", "base_chance"))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class Skill4(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "atk_boost"),
                self.get_value("duration"))
            event.bus.dispatch(event_types.AddEffect(eff_add))
    
    class NormalTurn(target.Target.NormalTurn):
        def __init__(self, t):
            super().__init__(t)

            event.bus.add_member_listener(self.reset_next_skill, self, self)

        def get_num_actions(self):
            return 2
    
        @event.member_listener(event_types.NormalTurn.Start.EXECUTE)
        def reset_next_skill(self, turn):
            self.target.next_skill = None

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "blaze_out_of_space", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill1, self.Skill2, self.Skill3, self.Skill4))
        self.skills.selector = self.skill_selector
        self.next_skill = None

        event.bus.add_member_listener(self.discharge, None, self)

        self.set_effect_types()
    
    def set_effect_types(self):
        dmg_desc = damage.DamageDesc(self,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.CALCULATED, self.config.get_skill_value("talent", "percentage"))),
            enums.Element.FIRE, damage.DmgType.DOT, damage.DmgSource.MONSTER)
        self.effect_types.add_unique(effect.DotEffect("enkindle", "Enkindle", dmg_desc, effect.Debuff.BURN, 0))

        self.effect_types.add_unique(effect.Effect("spontaneous_combustion", "Spontaneous Combustion",
            effect.Effect.Type.OTHERS, effect.Effect.DurationType.PERMANENT, 1, False))

        names = self.config.get_skill_name("skill4")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.BASE, self.config.get_skill_value("skill4", "atk_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF,
            effect.Effect.DurationType.TURN_END_CHECK_START, self.config.get_skill_value("skill4", "max_stacks"), "atk", mod), "atk_boost")
    
    def skill_selector(self, group):
        if self.next_skill is not None:
            return self.next_skill
        if self.effects.has_effect(self.effect_types.get(self.nameid, "spontaneous_combustion")):
            self.next_skill = group.skills[3]
            return group.skills[2]
        else:
            self.next_skill = group.skills[1]
            return group.skills[0]
    
    @event.member_listener(event_types.BreakWeakness.AFTER_BREAK)
    def discharge(self, e):
        if self is not e.tr.target:
            return
        self.effects.delete(self.effect_types.get(self.nameid, "spontaneous_combustion"))
        self.effects.delete(self.effect_types.get(self.nameid, "atk_boost"))
