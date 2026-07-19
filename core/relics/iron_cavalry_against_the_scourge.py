from .. import modifier
from .. import event
from .. import battle
from .. import damage

from . import base

class IronCavalryAgainstTheScourge(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def effect_2pc(self):
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((None, None, self.get_value_2pc("break_eff_boost"))), None, self.target)
            self.target.stats["break_eff"].modifiers.append(mod)
        
        def effect_4pc(self):
            battle.current.event_bus.add_member_listener(self.deal_damage, self.target)
        
        @event.member_listener(event.ListenerPriority.PRE_PROCESS)
        def deal_damage(self, dmg):
            if self.target is not dmg.dealer or not dmg.is_break_dmg():
                return
            break_eff = self.target.stats["break_eff"].calculate()
            if break_eff >= self.get_value_4pc("break_eff_threshold1"):
                dmg.factors[damage.DamageFactorType.DEF_BOOST] -= self.get_value_4pc("def_ignore1")
            if break_eff >= self.get_value_4pc("break_eff_threshold2") and dmg.is_super_break_dmg():
                dmg.factors[damage.DamageFactorType.DEF_BOOST] -= self.get_value_4pc("def_ignore2")

    def __init__(self):
        super().__init__("iron_cavalry_against_the_scourge")

base.register_relic_set(IronCavalryAgainstTheScourge)
