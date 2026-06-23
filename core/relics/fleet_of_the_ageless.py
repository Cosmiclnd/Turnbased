import modifier
import damage
import battle

from relics import base

class FleetOfTheAgeless(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def __init__(self, t, relic_set, pieces):
            super().__init__(t, relic_set, pieces)
            if self.pieces >= 2:
                mod1 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc((t.stats["hp"], modifier.ModifierFilter.BASE, relic_set.config.get_skill_value("2pc", "hp_boost"))),
                    None, t)
                t.stats["hp"].modifiers.append(mod1)
                mod2 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, relic_set.config.get_skill_value("2pc", "atk_boost"))),
                    self.validator_mod2, t)
                for c in battle.current.characters:
                    c.stats["atk"].modifiers.append(mod2)
        
        def validator_mod2(self, stat, **kwargs):
            return self.target.stats["spd"].calculate() >= self.relic_set.config.get_skill_value("2pc", "spd_threshold")

    def __init__(self):
        super().__init__("fleet_of_the_ageless")

base.register_relic_set(FleetOfTheAgeless)
