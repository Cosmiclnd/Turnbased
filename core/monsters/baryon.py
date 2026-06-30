import target
import event
import skill
import battle
import damage
import enums
import modifier

from monsters import base

class Baryon(base.Monster):
    class Skill(base.Monster.MonsterSkill):
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

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "baryon", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill,))
