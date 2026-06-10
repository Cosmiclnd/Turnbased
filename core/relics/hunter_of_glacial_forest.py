import modifier
import battle
import event
import effect

from relics import base

class HunterOfGlacialForest(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def __init__(self, t, relic_set, pieces):
            super().__init__(t, relic_set, pieces)
            if self.pieces >= 2:
                mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name, modifier.StatDesc((None, None, 0.1)), None, t)
                t.stats["ice_dmg_boost"].modifiers.append(mod)
            if self.pieces >= 4:
                battle.current.event_bus.add_member_listener(self.skill_group_trigger, t)
                self.effect_id = effect.Effect.next_id()
        
        @event.member_listener(event.ListenerPriority.EXECUTE + 1)
        async def skill_group_trigger(self, skill_group):
            if self.target.skills["ultimate"] is not skill_group:
                return
            mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name, modifier.StatDesc((None, None, 0.25)), None, self.target)
            eff = effect.ModifierEffect(self.relic_set.nameid, self.relic_set.name,
                self.effect_id, effect.Effect.Type.BUFF, 2, effect.CommonEffect.DurationType.TURN_END, 1, mod, self.target.stats["crt_dmg"])
            await battle.current.event_bus.dispatch("add_effect", self.target, eff)

    def __init__(self):
        super().__init__("hunter_of_glacial_forest", "Hunter of Glacial Forest")

base.register_relic_set(HunterOfGlacialForest)
