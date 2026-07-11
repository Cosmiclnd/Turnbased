import target
import event
import skill
import battle
import damage
import enums
import action
import modifier
import effect

from monsters import base

class BlazeOutOfSpace(base.Monster):
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
                enums.Element.FIRE, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            await battle.current.event_bus.dispatch("hit", dmg)
            eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "enkindle"),
                self.target.config.get_skill_value("talent", "duration"))
            await self.target.try_apply_debuff(eff_add, self.target.config.get_skill_value("talent", "base_chance"))
            await battle.current.event_bus.dispatch("attack_end", self.target)
    
    class Skill2(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "spontaneous_combustion"),
                -1)
            await battle.current.event_bus.dispatch("add_effect", eff_add)
    
    class Skill3(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            await battle.current.event_bus.dispatch("attack_start", self.target)
            for i in range(self.get_value("times")):
                t = await battle.current.event_bus.query("get_monster_target", self.target)
                if t is None:
                    break
                dmg = await damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    enums.Element.FIRE, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
                await battle.current.event_bus.dispatch("hit", dmg)
                eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "enkindle"),
                    self.target.config.get_skill_value("talent", "duration"))
                await self.target.try_apply_debuff(eff_add, self.target.config.get_skill_value("talent", "base_chance"))
            await battle.current.event_bus.dispatch("attack_end", self.target)
    
    class Skill4(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "atk_boost"),
                self.get_value("duration"))
            await battle.current.event_bus.dispatch("add_effect", eff_add)
    
    class NormalTurn(target.Target.NormalTurn):
        def get_num_actions(self):
            return 2

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "blaze_out_of_space", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill1, self.Skill2, self.Skill3, self.Skill4))
        self.skills.selector = self.skill_selector
        self.next_skill = None
        battle.current.event_bus.add_member_listener(self.reset_next_skill, self)
        battle.current.event_bus.add_member_listener(self.discharge, self)

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
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1, "normal_turn")
    async def reset_next_skill(self, turn):
        if not isinstance(turn, target.Target.NormalTurn) or self is not turn.target or turn.cur_action != 0:
            return
        self.next_skill = None
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "weakness_break")
    async def discharge(self, tr):
        if self is not tr.target:
            return
        await self.effects.delete(self.effect_types.get(self.nameid, "spontaneous_combustion"))
        await self.effects.delete(self.effect_types.get(self.nameid, "atk_boost"))
