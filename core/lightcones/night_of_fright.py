import modifier
import effect
import event
import battle
import healing

from lightcones import base

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
            battle.current.event_bus.add_member_listener(self.ultimate_turn, t)
            battle.current.event_bus.add_member_listener(self.heal, t)
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1)
    def ultimate_turn(self, turn):
        heal = healing.Healing(self.target, turn.target, modifier.StatDesc((turn.target.stats["hp"], modifier.ModifierFilter.CALCULATED,
            self.get_value("percentage"))))
        battle.current.event_bus.dispatch("heal", heal)
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1)
    def heal(self, heal):
        if self.target is not heal.healer:
            return
        eff_add = effect.EffectAddition(self.target, heal.target, self.effect_types.get(self.nameid, "eff"), self.get_value("duration"))
        battle.current.event_bus.dispatch("add_effect", eff_add)
