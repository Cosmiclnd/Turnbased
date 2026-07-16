import target
import enums
import modifier
import event
import battle
import damage
import effect
import item

from lightcones import base

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
                    battle.current.event_bus.add_member_listener(self.deal_damage, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event.ListenerPriority.PRE_PROCESS)
            def deal_damage(self, dmg):
                if self.target is not dmg.target or self.effect.lightcone.target is not dmg.dealer:
                    return
                if dmg.is_break_dmg():
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
            battle.current.event_bus.add_member_listener(self.deal_damage, t)
    
    def init_class(self):
        cls = self.__class__
        if not cls.inited:
            cls.inited = True
            cls.effect_types.add(self.nameid, self.RoutedEffect(self))
        self.effect_types.add_unique(cls.effect_types.get(self.nameid, "routed"))
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS + 1)
    def deal_damage(self, dmg):
        if self.target is not dmg.dealer or not dmg.is_break_dmg():
            return
        eff_add = effect.EffectAddition(self.target, dmg.target, self.effect_types.get(self.nameid, "routed"), self.get_value("duration"))
        battle.current.event_bus.dispatch("add_effect", eff_add)
