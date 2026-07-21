from .. import modifier
from .. import event
from .. import event_types
from .. import battle
from .. import damage

from . import base

class PrisonerInDeepConfinement(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def effect_2pc(self):
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.BASE, self.get_value_2pc("atk_boost"))),
                None, self.target)
            self.target.stats["atk"].modifiers.append(mod)
        
        def effect_4pc(self):
            event.bus.add_member_listener(self.deal_damage, self.target, self.target)
        
        @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
        def deal_damage(self, e):
            dmg = e.dmg
            count = min(dmg.target.effects.count_effect(lambda eff: eff.is_dot(dmg.target)), self.get_value_4pc("max_dots"))
            dmg.factors[damage.DamageFactorType.DEF_BOOST] -= self.get_value_4pc("def_ignore") * count

    def __init__(self):
        super().__init__("prisoner_in_deep_confinement")

base.register_relic_set(PrisonerInDeepConfinement)
