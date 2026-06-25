import modifier
import effect
import event
import battle

from relics import base

class MessengerTraversingHakerspace(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        inited = False

        def __init__(self, t, relic_set, pieces):
            super().__init__(t, relic_set, pieces)
            if self.pieces >= 2:
                mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc((t.stats["spd"], modifier.ModifierFilter.BASE, relic_set.config.get_skill_value("2pc", "spd_boost"))),
                    None, t)
                t.stats["spd"].modifiers.append(mod)
            if self.pieces >= 4:
                self.init_class()
        
        def init_class(self):
            cls = self.__class__
            if cls.inited:
                return
            cls.inited = True
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc(("spd", modifier.ModifierFilter.BASE, self.relic_set.config.get_skill_value("4pc", "spd_boost"))))
            cls.effect = effect.ModifierEffect(self.relic_set.nameid, self.relic_set.name, effect.Effect.Type.BUFF,
                effect.Effect.DurationType.TURN_END_CHECK_START, 1, "spd", mod)
            battle.current.event_bus.add_member_listener(self.ultimate_turn, self.target)
        
        @event.member_listener(event.ListenerPriority.PRE_PROCESS)
        async def ultimate_turn(self, turn):
            if self.target is not turn.target:
                return
            for c in battle.current.characters:
                eff_add = effect.EffectAddition(self.target, c, self.effect, self.relic_set.config.get_skill_value("4pc", "duration"))
                await battle.current.event_bus.dispatch("add_effect", eff_add)

    def __init__(self):
        super().__init__("messenger_traversing_hakerspace")

base.register_relic_set(MessengerTraversingHakerspace)
