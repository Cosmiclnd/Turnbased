from .. import modifier
from .. import damage
from .. import battle
from .. import event
from .. import event_types

from . import base

class RevelryBySea(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def effect_2pc(self):
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.BASE, self.get_value_2pc("atk_boost"))),
                None, self.target)
            self.target.stats["atk"].modifiers.append(mod)
            event.bus.add_member_listener(self.deal_damage, self.target, self.target)
        
        @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
        def deal_damage(self, e):
            dmg = e.dmg
            if not dmg.is_dot_dmg():
                return
            atk = self.target.stats["atk"].calculate()
            if atk >= self.get_value_2pc("atk_threshold1"):
                dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.get_value_2pc("dot_dmg_boost1")
            elif atk >= self.get_value_2pc("atk_threshold2"):
                dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.get_value_2pc("dot_dmg_boost2")

    def __init__(self):
        super().__init__("revelry_by_sea")

base.register_relic_set(RevelryBySea)
