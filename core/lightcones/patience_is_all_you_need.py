from .. import item
from .. import modifier
from .. import effect
from .. import event
from .. import event_types
from .. import battle
from .. import damage
from .. import enums

from . import base

class PatienceIsAllYouNeed(base.LightCone):
    def __init__(self, record):
        super().__init__("patience_is_all_you_need", record)
    
    def apply(self, t):
        super().apply(t)
        if self.valid:
            mod1 = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, self.get_value("dmg_boost"))), None, t)
            t.stats["dmg_boost"].modifiers.append(mod1)
            mod2 = modifier.Modifier(self.nameid, self.name,
                modifier.StatDesc((t.stats["spd"], modifier.ModifierFilter.BASE, self.get_value("spd_boost"))))
            self.effect_types.add_unique(effect.ModifierEffect("effect", self.name, effect.Effect.Type.BUFF,
                effect.Effect.DurationType.PERMANENT, self.get_value("max_stacks"), "spd", mod2), "eff")
            dmg_desc = damage.DamageDesc(t,
                modifier.StatDesc((t.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("dot_percentage"))),
                enums.Element.LIGHTNING, damage.DmgType.DOT, damage.DmgSource.DOT)
            self.effect_types.add_unique(effect.DotEffect("erode", "Erode", dmg_desc, effect.Debuff.SHOCK, 1))
            event.bus.add_member_listener(self.attack_end, t, t)
            event.bus.add_member_listener(self.hit, t, t)
    
    @event.member_listener(event_types.Attack.End.EXECUTE)
    def attack_end(self, e):
        eff_add = effect.EffectAddition(self.target, self.target, self.effect_types.get(self.nameid, "eff"), -1)
        event.bus.dispatch(event_types.AddEffect(eff_add))
    
    @event.member_listener(event_types.Hit.BEFORE_HIT)
    def hit(self, e):
        if e.dmg.target.effects.has_effect(self.effect_types.get(self.nameid, "erode")):
            return
        eff_add = effect.EffectAddition(self.target, e.dmg.target, self.effect_types.get(self.nameid, "erode"), self.get_value("duration"))
        self.target.try_apply_debuff(eff_add, self.get_value("base_chance"))
