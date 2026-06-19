import target
import skill
import battle
import event
import damage
import healing
import modifier
import enums
import effect

from characters import base

class Huohuo(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            dmg = damage.Damage(self.target, t,
                modifier.StatDesc((self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATTACK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            dmg.hit_split = (0.2, 0.2, 0.2, 0.4)
            await battle.current.event_bus.dispatch("attack", dmg)
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            main = healing.Healing(self.target, t,
                modifier.StatDesc((
                    (self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("main_percentage")),
                    (None, None, self.get_value("main_flat"))
                )))
            await battle.current.event_bus.dispatch("heal", main)
            for t in self.get_blast_targets():
                sub = healing.Healing(self.target, t,
                    modifier.StatDesc((
                        (self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("sub_percentage")),
                        (None, None, self.get_value("sub_flat"))
                    )))
                await battle.current.event_bus.dispatch("heal", sub)
            await battle.current.event_bus.dispatch("regen_energy", self.target, self.get_value("energy_regen"))
    
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
            for t in battle.current.characters[:]:
                if t is self.target:
                    continue
                await battle.current.event_bus.dispatch("regen_energy", t, t.stats["max_energy"].calculate() * self.get_value("energy_regen_rate"), True)
                eff_add = effect.EffectAddition(self.target, t, self.target.effect_types["ultimate"], self.get_value("duration"))
                await battle.current.event_bus.dispatch("add_effect", eff_add)
            await battle.current.event_bus.dispatch("regen_energy", self.target, self.get_value("energy_regen"))
    
    class Talent(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
    
    def __init__(self, record):
        super().__init__("huohuo", record)
    
    def set_record(self, record):
        super().set_record(record)
        
        if self.traces_unlocked[1]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace2"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace2", "control_res"))),
                None, self)
            self.stats["control_res"].modifiers.append(mod)
        
        if self.eidolons >= 3:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)
        if self.eidolons >= 5:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
        
        self.set_effect_types()
    
    def set_effect_types(self):
        self.effect_types = {}

        names = self.config.get_skill_name("ultimate")
        mod = modifier.Modifier(*names,
            modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.skills["ultimate"].skills[0].get_value("atk_boost"))), None, self)
        self.effect_types["ultimate"] = effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END, 1, "atk", mod)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        await super().battle_start()
        if self.traces_unlocked[0]:
            await battle.current.event_bus.dispatch("regen_energy", self, self.config.get_skill_value("bonus_trace1", "energy"))
