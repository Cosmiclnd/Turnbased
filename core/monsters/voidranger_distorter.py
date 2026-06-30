import target
import event
import skill
import battle
import damage
import enums
import action
import modifier
import effect
import item

from monsters import base

class VoidrangerDistorter(base.Monster):
    has_lock_on = None

    class Skill1(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = await battle.current.event_bus.query("get_monster_target", self.target)
            eff_add = effect.EffectAddition(self.target, t, self.target.effect_types["lock_on"], -1)
            await battle.current.event_bus.dispatch("add_effect", eff_add)
    
    class Skill2(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = await battle.current.event_bus.query("get_monster_target", self.target)
            await battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = await damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                enums.Element.QUANTUM, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.energy_regen = self.get_value("energy_regen")
            await battle.current.event_bus.dispatch("hit", dmg)
            await battle.current.event_bus.dispatch("attack_end", self.target)
    
    class LockOnEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            async def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    VoidrangerDistorter.has_lock_on = (self.effect.target, self.target)
                    self.eff_dead = item.DeadToggle(self.target)
                    battle.current.event_bus.add_member_listener(self.deal_damage, self.eff_dead)
                    battle.current.event_bus.add_member_resolver(self.get_monster_target, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    VoidrangerDistorter.has_lock_on = None
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event.ListenerPriority.PRE_PROCESS)
            async def deal_damage(self, dmg):
                if self.target is not dmg.target:
                    return
                dmg.factors[damage.DamageFactorType.VULNERABILITY] += self.effect.target.config.get_skill_value("skill1", "vulnerability")
            
            @event.member_resolver(event.ListenerPriority.EXECUTE + 1)
            async def get_monster_target(self, t):
                if t.tier is not base.Monster.Tier.NORMAL:
                    return
                return event.QueryResult(self.target)

        def __init__(self, t):
            super().__init__("lock_on", "Lock On", effect.Effect.Type.OTHERS, effect.Effect.DurationType.PERMANENT, 1)
            self.target = t

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "voidranger_distorter", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill1, self.Skill2))
        self.skills.selector = self.skill_selector
        battle.current.event_bus.add_member_listener(self.reset_lock_on, self)
        battle.current.event_bus.add_member_listener(self.check_lock_on, self)

        self.set_effect_types()
    
    def set_effect_types(self):
        self.effect_types["lock_on"] = self.LockOnEffect(self)
    
    def skill_selector(self, group):
        if len(battle.current.characters) == 0:
            return group.skills[1]
        if self.has_lock_on is None:
            return group.skills[0]
        return group.skills[1]
    
    @event.member_listener(event.ListenerPriority.POST_PROCESS, "attack_end")
    async def reset_lock_on(self, t):
        if self is not t or self.has_lock_on is None or self is not self.has_lock_on[0]:
            return
        await self.has_lock_on[1].effects.delete(self.effect_types["lock_on"])
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "die")
    async def check_lock_on(self, t):
        if self is not t or self.has_lock_on is None or self is not self.has_lock_on[0]:
            return
        await self.has_lock_on[1].effects.delete(self.effect_types["lock_on"])
