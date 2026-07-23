from .. import modifier
from .. import effect
from .. import event
from .. import event_types
from .. import battle
from .. import healing

from . import base

class NightOfFright(base.LightCone):
    def __init__(self, record):
        super().__init__("night_of_fright", record)
    
    def apply(self, t):
        super().apply(t)
        if self.valid:
            mod = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, self.get_value("energy_regen_boost"))), None, t)
            t.stats["energy_regen_rate"].modifiers.append(mod)
            mod2 = modifier.Modifier(self.nameid, self.name,
                modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.get_value("atk_boost"))))
            self.effect_types.add_unique(effect.ModifierEffect("effect", self.name, effect.Effect.Type.BUFF,
                effect.Effect.DurationType.TURN_END, self.get_value("max_stacks"), "atk", mod2), "eff")
            event.bus.add_member_listener(self.ultimate, None, t)
            event.bus.add_member_listener(self.heal, t, t)
    
    @event.member_listener(event_types.Ultimate.BEFORE_TRIGGER)
    def ultimate(self, e):
        heal = healing.Healing(self.target, e.target, modifier.StatDesc((e.target.stats["hp"], modifier.ModifierFilter.CALCULATED,
            self.get_value("percentage"))))
        event.bus.dispatch(event_types.Heal(heal))
    
    @event.member_listener(event_types.Heal.BEFORE_EXECUTE)
    def heal(self, e):
        eff_add = effect.EffectAddition(self.target, e.heal.target, self.effect_types.get(self.nameid, "eff"),
            self.get_value("duration"))
        event.bus.dispatch(event_types.AddEffect(eff_add))
