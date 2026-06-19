import modifier
import battle
import event
import effect

from relics import base

class PasserbyOfWanderingCloud(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def __init__(self, t, relic_set, pieces):
            super().__init__(t, relic_set, pieces)
            if self.pieces >= 2:
                mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc((None, None, relic_set.config.get_skill_value("2pc", "healing_boost"))),
                    None, t)
                t.stats["outgoing_healing_boost"].modifiers.append(mod)
            if self.pieces >= 4:
                battle.current.event_bus.add_member_listener(self.battle_start, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def battle_start(self):
            battle.current.skillpoints.modify(1)

    def __init__(self):
        super().__init__("passerby_of_wandering_cloud")

base.register_relic_set(PasserbyOfWanderingCloud)
