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
            level = self.level + self.bonus_level
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
            level = self.level + self.bonus_level
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
