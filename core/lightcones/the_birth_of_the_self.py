from .. import target
from .. import enums
from .. import modifier
from .. import event
from .. import battle
from .. import damage

from . import base

class TheBirthOfTheSelf(base.LightCone):
    def __init__(self, record):
        super().__init__("the_birth_of_the_self", record)

    def apply(self, t):
        super().apply(t)
        if self.valid:
            dmg_boost = self.get_value("dmg_boost")
            mod1 = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, dmg_boost)), self.validator_mod1, self.target)
            mod2 = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, dmg_boost)), self.validator_mod2, self.target)
            self.target.stats["dmg_boost"].modifiers.extend((mod1, mod2))
    
    def validator_mod1(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.context.source is damage.DmgSource.FOLLOW_UP
    
    def validator_mod2(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.context.source is damage.DmgSource.FOLLOW_UP and dmg.target.cur_hp <= dmg.target.stats["hp"].calculate() * self.get_value("hp_threshold")
