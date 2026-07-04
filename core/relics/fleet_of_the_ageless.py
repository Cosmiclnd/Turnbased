import modifier
import damage
import battle

from relics import base

class FleetOfTheAgeless(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        async def effect_2pc(self):
            mod1 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((self.target.stats["hp"], modifier.ModifierFilter.BASE, self.get_value_2pc("hp_boost"))),
                None, self.target)
            self.target.add_modifier_hp(mod1)
            mod2 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.get_value_2pc("atk_boost"))),
                self.validator_mod2, self.target)
            for c in battle.current.characters:
                c.stats["atk"].modifiers.append(mod2)
        
        def validator_mod2(self, stat, **kwargs):
            return self.target.stats["spd"].calculate() >= self.get_value_2pc("spd_threshold")

    def __init__(self):
        super().__init__("fleet_of_the_ageless")

base.register_relic_set(FleetOfTheAgeless)
