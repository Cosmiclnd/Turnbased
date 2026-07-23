from .. import modifier
from .. import effect
from .. import event
from .. import event_types
from .. import battle

from . import base

class MessengerTraversingHakerspace(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        inited = False
        effect_types = effect.EffectTypes()
        
        def effect_2pc(self):
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((self.target.stats["spd"], modifier.ModifierFilter.BASE, self.get_value_2pc("spd_boost"))),
                None, self.target)
            self.target.stats["spd"].modifiers.append(mod)
        
        def effect_4pc(self):
            cls = self.__class__
            if not cls.inited:
                cls.inited = True
                mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc(("spd", modifier.ModifierFilter.BASE, self.get_value_4pc("spd_boost"))))
                cls.effect_types.add(self.relic_set.nameid, effect.ModifierEffect("4pc_effect", self.relic_set.name, effect.Effect.Type.BUFF,
                    effect.Effect.DurationType.TURN_END_CHECK_START, 1, "spd", mod), "4pc")
            self.effect_types.add_unique(cls.effect_types.get(self.relic_set.nameid, "4pc"), "4pc")
            event.bus.add_member_listener(self.ultimate, self.target, self.target)
        
        @event.member_listener(event_types.Ultimate.BEFORE_TRIGGER)
        def ultimate(self, e):
            if not self.target.get_current_skill("ultimate").is_character_target():
                return
            for c in battle.current.characters:
                eff_add = effect.EffectAddition(self.target, c, self.effect_types.get(self.relic_set.nameid, "4pc"),
                    self.get_value_4pc("duration"))
                event.bus.dispatch(event_types.AddEffect(eff_add))

    def __init__(self):
        super().__init__("messenger_traversing_hakerspace")

base.register_relic_set(MessengerTraversingHakerspace)
