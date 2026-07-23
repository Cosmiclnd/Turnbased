from .. import target
from .. import event
from .. import event_types
from .. import skill
from .. import battle
from .. import damage
from .. import enums
from .. import modifier

from . import base

class Baryon(base.Monster):
    class Skill(base.Monster.MonsterSkill):
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

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "baryon", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill,))
