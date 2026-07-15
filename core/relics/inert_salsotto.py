import modifier
import damage

from relics import base

class InertSalsotto(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        async def effect_2pc(self):
            mod1 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((None, None, self.get_value_2pc("crt_rate_boost"))),
                None, self.target)
            self.target.stats["crt_rate"].modifiers.append(mod1)
            mod2 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((None, None, self.get_value_2pc("dmg_boost"))),
                self.validator_mod2, self.target)
            self.target.stats["dmg_boost"].modifiers.append(mod2)
        
        def validator_mod2(self, stat, **kwargs):
            dmg = kwargs.get("damage", None)
            if dmg is None:
                return False
            return (stat.target.stats["crt_rate"].calculate() >= self.get_value_2pc("crt_rate_threshold") and
                dmg.context.source in (damage.DmgSource.ULTIMATE, damage.DmgSource.FOLLOW_UP))

    def __init__(self):
        super().__init__("inert_salsotto")

base.register_relic_set(InertSalsotto)
