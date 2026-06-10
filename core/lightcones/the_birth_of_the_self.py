import target
import enums
import modifier
import event
import battle
import damage

from lightcones import base

class TheBirthOfTheSelf(base.LightCone):
    def __init__(self):
        super().__init__("the_birth_of_the_self", "The Birth of the Self", enums.Path.ERUDITION)
    
    def apply(self, tar):
        super().apply(tar)
        t = (self.level - 1) / 79
        self.target.stats["hp"].base_value += target.lerp(43, 953, t)
        self.target.stats["atk"].base_value += target.lerp(21.6, 476.28, t)
        self.target.stats["def"].base_value += target.lerp(15, 330.75, t)
        if self.path is self.target.path:
            dmg_boost = 0.18 + 0.06 * self.stacks
            mod1 = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, dmg_boost)), self.validator_mod1, self.target)
            mod2 = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, dmg_boost)), self.validator_mod2, self.target)
            self.target.stats["dmg_boost"].modifiers.extend((mod1, mod2))
    
    def validator_mod1(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.source is damage.DmgSource.FOLLOW_UP
    
    def validator_mod2(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.source is damage.DmgSource.FOLLOW_UP and dmg.target.cur_hp <= dmg.target.stats["hp"].calculate() * 0.5
