from .. import target
from .. import enums
from .. import modifier
from .. import event
from .. import event_types
from .. import battle
from .. import damage
from .. import effect
from .. import item

from . import base

class WhereaboutsShouldDreamRest(base.LightCone):
    inited = False
    effect_types = effect.EffectTypes()

    class RoutedEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    mod = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc(("spd", modifier.ModifierFilter.BASE, -self.effect.lightcone.get_value("spd_reduction"))),
                        None, self.eff_dead)
                    self.target.stats["spd"].modifiers.append(mod)
                    event.bus.add_member_listener(self.deal_damage, self.effect.lightcone.target, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event_types.Damage.BEFORE_CALCULATE)
            def deal_damage(self, e):
                dmg = e.dmg
                if self.target is not dmg.target or dmg.is_break_dmg():
                    return
                dmg.factors[damage.DamageFactorType.VULNERABILITY] += self.effect.lightcone.get_value("break_dmg_vulnerability")

        def __init__(self, lightcone):
            super().__init__("routed", "Routed", effect.Effect.Type.DEBUFF, effect.Effect.DurationType.TURN_END, 1)
            self.lightcone = lightcone

    def __init__(self, record):
        super().__init__("whereabouts_should_dream_rest", record)
    
    def apply(self, t):
        super().apply(t)
        if self.valid:
            mod = modifier.Modifier(self.nameid, self.name,
                modifier.StatDesc((None, None, self.get_value("break_eff_boost"))), None, t)
            t.stats["break_eff"].modifiers.append(mod)
            self.init_class()
            event.bus.add_member_listener(self.deal_damage, t, t)
    
    def init_class(self):
        cls = self.__class__
        if not cls.inited:
            cls.inited = True
            cls.effect_types.add(self.nameid, self.RoutedEffect(self))
        self.effect_types.add_unique(cls.effect_types.get(self.nameid, "routed"))
    
    @event.member_listener(event_types.Damage)
    def deal_damage(self, e):
        dmg = e.dmg
        if not dmg.is_break_dmg():
            return
        eff_add = effect.EffectAddition(self.target, dmg.target, self.effect_types.get(self.nameid, "routed"), self.get_value("duration"))
        event.bus.dispatch(event_types.AddEffect(eff_add))
