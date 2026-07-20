from .. import target
from .. import skill
from .. import battle
from .. import event
from .. import damage
from .. import modifier
from .. import enums
from .. import effect
from .. import action
from .. import auto_battle

from . import base

class March7ThPreservation(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            battle.current.event_bus.dispatch("hit", dmg)
            battle.current.event_bus.dispatch("attack_end", self.target)
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
    
    class Talent(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
    
    class Technique(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
    
    def __init__(self, record):
        self.set_auto_battle(AutoBattlePolicy(self))
        super().__init__("march_7th_preservation", record)
    
    def set_record(self, record):
        super().set_record(record)
        
        if self.eidolons >= 3:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
        if self.eidolons >= 5:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)

class AutoBattlePolicy(auto_battle.AutoBattlePolicy):
    pass
