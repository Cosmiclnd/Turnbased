from .. import modifier
from .. import battle
from .. import event
from .. import event_types
from .. import effect

from . import base

class HunterOfGlacialForest(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def effect_2pc(self):
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((None, None, self.get_value_2pc("dmg_boost"))),
                None, self.target)
            self.target.stats["ice_dmg_boost"].modifiers.append(mod)

        def effect_4pc(self):
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((None, None, self.get_value_4pc("crt_dmg_boost"))))
            self.effect_types.add_unique(effect.ModifierEffect("4pc_effect", self.relic_set.name, effect.Effect.Type.BUFF,
                effect.Effect.DurationType.TURN_END_CHECK_START, 1, "crt_dmg", mod), "4pc")
            battle.current.event_bus.add_member_listener_legacy(self.ultimate_turn, self.target)
        
        @event.member_listener_legacy(event.ListenerPriority.EXECUTE + 1)
        def ultimate_turn(self, turn):
            if self.target is not turn.target:
                return
            eff_add = effect.EffectAddition(self.target, self.target, self.effect_types.get(self.relic_set.nameid, "4pc"),
                self.get_value_4pc("duration"))
            battle.current.event_bus.dispatch_legacy("add_effect", eff_add)

    def __init__(self):
        super().__init__("hunter_of_glacial_forest")

base.register_relic_set(HunterOfGlacialForest)
