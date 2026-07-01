import target
import event
import skill
import battle
import damage
import enums
import modifier
import effect
import item

from monsters import base

class VoidrangerEliminator(base.Monster):
    class Skill1(base.Monster.MonsterSkill):
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
            for ratio in (0.33, 0.33, 0.34):
                dmg.hit_split_ratio = ratio
                await battle.current.event_bus.dispatch("hit", dmg)
            eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "detonated"), -1, 3)
            await battle.current.event_bus.dispatch("add_effect", eff_add)
            await battle.current.event_bus.dispatch("attack_end", self.target)
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "overloaded"), -1)
            await battle.current.event_bus.dispatch("add_effect", eff_add)
    
    class Skill2(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            await self.target.effects.delete(self.target.effect_types.get(self.target.nameid, "overloaded"))
    
    class DetonatedEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            async def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.listener_dead = item.DeadToggle(self.target)
                    self.dmg = await self.effect.dmg_desc.summon(self.target)
                    battle.current.event_bus.add_member_listener(self.hit, self.listener_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.listener_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event.ListenerPriority.EXECUTE)
            async def hit(self, dmg):
                if self.target is not dmg.target:
                    return
                await battle.current.event_bus.dispatch("additional_damage", self.dmg)
                await self.target.effects.remove(self.effect, 1)

        def __init__(self, dmg_desc):
            super().__init__("detonated", "Detonated", effect.Effect.Type.DEBUFF, effect.Effect.DurationType.PERMANENT, -1)
            self.dmg_desc = dmg_desc

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "voidranger_eliminator", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill1, self.Skill2))
        self.skills.selector = self.skill_selector

        self.set_effect_types()
    
    def set_effect_types(self):
        dmg_desc = damage.DamageDesc(self,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.CALCULATED,
                self.config.get_skill_value("skill1", "additional_percentage"))),
            enums.Element.IMAGINARY, damage.DmgType.ADDITIONAL, damage.DmgSource.MONSTER)
        self.effect_types.add_unique(self.DetonatedEffect(dmg_desc))

        self.effect_types.add_unique(effect.Effect("overloaded", "Overloaded", effect.Effect.Type.OTHERS,
            effect.Effect.DurationType.PERMANENT, 1), "overloaded")
    
    def skill_selector(self, group):
        if self.effects.has_effect(self.effect_types.get(self.nameid, "overloaded")):
            return group.skills[1]
        return group.skills[0]
