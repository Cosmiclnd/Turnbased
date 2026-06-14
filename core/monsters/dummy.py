import target
import event
import skill
import battle
import damage
import enums
import modifier

class Dummy(target.Monster):
    class Skill(target.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_target()
            dmg = damage.Damage(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                None, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.energy_regen = self.get_value("energy_regen")
            await battle.current.event_bus.dispatch("attack", dmg)

    def __init__(self, level, moc):
        super().__init__("dummy", level, moc)
        self.init_skills((self.Skill,))
