from .. import modifier
from .. import battle
from .. import event
from .. import effect

from . import base

class PasserbyOfWanderingCloud(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def effect_2pc(self):
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                modifier.StatDesc((None, None, self.get_value_2pc("healing_boost"))),
                None, self.target)
            self.target.stats["outgoing_healing_boost"].modifiers.append(mod)

        def effect_4pc(self):
            battle.current.skillpoints.modify(1)

    def __init__(self):
        super().__init__("passerby_of_wandering_cloud")

base.register_relic_set(PasserbyOfWanderingCloud)
