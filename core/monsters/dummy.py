from .. import target
from .. import event
from .. import event_types
from .. import skill
from .. import battle
from .. import damage
from .. import enums
from .. import modifier

from . import base

class Dummy(base.Monster):
    class Skill(base.Monster.MonsterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            event.bus.add_member_listener(self.skill_trigger, self, t)
        
        @event.member_listener(event_types.SkillTrigger.TRIGGER)
        def skill_trigger(self, e):
            t = battle.current.event_bus.query_legacy("get_monster_target", self.target)
            battle.current.event_bus.dispatch_legacy("attack_start", self.target)
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                None, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.energy_regen = self.get_value("energy_regen")
            battle.current.event_bus.dispatch_legacy("hit", dmg)
            battle.current.event_bus.dispatch_legacy("attack_end", self.target)

    def __init__(self, uuid, level, moc, stat_scales, stat_flats):
        super().__init__(uuid, "dummy", level, moc, stat_scales, stat_flats)
        self.init_skills((self.Skill,))
