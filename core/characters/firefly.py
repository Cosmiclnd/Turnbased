import item
import target
import event
import battle
import modifier
import damage
import effect
import action

from characters import base

class Firefly(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            await battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = await damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            await battle.current.event_bus.dispatch("hit", dmg)
            await battle.current.event_bus.dispatch("attack_end", self.target)
    
    class EnhancedBasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            await self.target.consume_hp(self.target.stats["hp"].calculate() * self.get_value("hp_cost"))
            await battle.current.event_bus.dispatch("regen_energy", self.target,
                self.target.stats["max_energy"].calculate() * self.get_value("energy_regen_rate"), True)
            t = self.get_main_target()
            await battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = await damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
            await battle.current.event_bus.dispatch("hit", dmg)
            await battle.current.event_bus.dispatch("attack_end", self.target)
            await battle.current.event_bus.dispatch("action_advance", self.target, self.get_value("advance_scale"))
    
    class EnhancedSkill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
    
    class Ultimate(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            self.target.cur_energy -= self.target.stats["energy"].calculate()
            self.target.ultimate_activated = False
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "complete_combustion"), -1)
            await battle.current.event_bus.dispatch("add_effect", eff_add)
            await battle.current.event_bus.dispatch("action_advance", self.target, self.get_value("advance_scale"))
    
    class Talent(base.Character.CharacterSkill):
        pass
    
    class Technique(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
    
    def __init__(self, record):
        super().__init__("firefly", record)
    
    def init_skills(self):
        super().init_skills()
        self.skills["basic_atk"].add(self.EnhancedBasicAtk(self, "enhanced_basic_atk"))
        self.skills["skill"].add(self.EnhancedSkill(self, "enhanced_skill"))
    
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
        self.effect_types.add_unique(effect.Effect("complete_combustion", "Complete Combustion", effect.Effect.Type.BUFF,
            effect.Effect.DurationType.Permanent, 1, False))
