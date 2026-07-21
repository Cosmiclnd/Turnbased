from .. import modifier
from .. import event
from .. import event_types
from .. import enums
from .. import effect
from .. import battle

from . import base

class ForgeOfTheKalpagniLantern(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def effect_2pc(self):
            mod1 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((self.target.stats["spd"], modifier.ModifierFilter.BASE, self.get_value_2pc("spd_boost"))),
                None, self.target)
            self.target.stats["spd"].modifiers.append(mod1)
            mod2 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((None, None, self.get_value_2pc("break_eff_boost"))))
            self.effect_types.add_unique(effect.ModifierEffect("2pc_effect", self.relic_set.name, effect.Effect.Type.BUFF,
                effect.Effect.DurationType.TURN_END_CHECK_START, 1, "break_eff", mod2), "2pc")
            battle.current.event_bus.add_member_listener_legacy(self.hit, self.target)
        
        @event.member_listener_legacy(event.ListenerPriority.EXECUTE + 1)
        def hit(self, dmg):
            if self.target is not dmg.dealer:
                return
            if dmg.target.weaknesses.has_weakness(enums.Element.FIRE):
                eff_add = effect.EffectAddition(self.target, self.target, self.effect_types.get(self.relic_set.nameid, "2pc"),
                    self.get_value_2pc("duration"))
                battle.current.event_bus.dispatch_legacy("add_effect", eff_add)

    def __init__(self):
        super().__init__("forge_of_the_kalpagni_lantern")

base.register_relic_set(ForgeOfTheKalpagniLantern)
