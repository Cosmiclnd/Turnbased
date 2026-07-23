from dataclasses import dataclass

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
from .. import item

from . import base

class VoidrangerDistorter(base.Monster):
    lock_on_info = None
    
    @dataclass(slots=True, eq=False)
    class GlobalLockOnInfo:
        caster: object
        target: object

    class Skill1(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            t = event.bus.query(event_types.GetMonsterSkillTarget(self.target))
            eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "lock_on"), -1)
            event.bus.dispatch(event_types.AddEffect(eff_add))
    
    class Skill2(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            t = event.bus.query(event_types.GetMonsterSkillTarget(self.target))
            event.bus.dispatch(event_types.Attack.Start(self.target))
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                enums.Element.QUANTUM, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.energy_regen = self.get_value("energy_regen")
            event.bus.dispatch(event_types.Hit(dmg))
            event.bus.dispatch(event_types.Attack.End(self.target))
    
    class LockOnEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    VoidrangerDistorter.lock_on_info = VoidrangerDistorter.GlobalLockOnInfo(self.caster, self.target)
                    self.eff_dead = item.DeadToggle(self.target)
                    event.bus.add_member_listener(self.deal_damage, None, self.eff_dead)
                    event.bus.add_member_resolver(self.get_monster_skill_target, None, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    VoidrangerDistorter.lock_on_info = None
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
            def deal_damage(self, e):
                dmg = e.dmg
                if self.target is not dmg.target:
                    return
                dmg.factors[damage.DamageFactorType.VULNERABILITY] += self.caster.config.get_skill_value("skill1", "vulnerability")
            
            @event.member_resolver(event_types.GetMonsterSkillTarget.LOCK_ON)
            def get_monster_skill_target(self, e):
                if e.target.tier is not base.Monster.Tier.NORMAL:
                    return
                return event.QueryResult(self.target)

        def __init__(self):
            super().__init__("lock_on", "Lock On", effect.Effect.Type.OTHERS, effect.Effect.DurationType.PERMANENT, 1)

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "voidranger_distorter", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill1, self.Skill2))
        self.skills.selector = self.skill_selector

        event.bus.add_member_listener(self.reset_lock_on, self, self)
        event.bus.add_member_listener(self.check_lock_on, self, self)

        self.set_effect_types()
    
    def set_effect_types(self):
        self.effect_types.add_unique(self.LockOnEffect())
    
    def skill_selector(self, group):
        if len(battle.current.characters) == 0:
            return group.skills[1]
        if VoidrangerDistorter.lock_on_info is None:
            return group.skills[0]
        return group.skills[1]
    
    @event.member_listener(override=base.Monster.set_initial_state)
    def set_initial_state(self, e):
        super().set_initial_state(e)
        VoidrangerDistorter.lock_on_info = None
    
    @event.member_listener(event_types.Attack.End.EXECUTE)
    def reset_lock_on(self, e):
        if VoidrangerDistorter.lock_on_info is None or self is not VoidrangerDistorter.lock_on_info.caster:
            return
        VoidrangerDistorter.lock_on_info.target.effects.delete(self.effect_types.get(self.nameid, "lock_on"))
    
    @event.member_listener(event_types.Die.AFTER_EXECUTE)
    def check_lock_on(self, t):
        if VoidrangerDistorter.lock_on_info is None or self is not VoidrangerDistorter.lock_on_info.caster:
            return
        VoidrangerDistorter.lock_on_info.target.effects.delete(self.effect_types.get(self.nameid, "lock_on"))
