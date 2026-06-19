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
                mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc((None, None, relic_set.config.get_skill_value("2pc", "dmg_boost"))),
                    None, t)
                t.stats["ice_dmg_boost"].modifiers.append(mod)
            if self.pieces >= 4:
                battle.current.event_bus.add_member_listener(self.skill_group_trigger, t)
                mod = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc((None, None, relic_set.config.get_skill_value("4pc", "crt_dmg_boost"))),
                    None, t)
                self.effect = effect.ModifierEffect(self.relic_set.nameid, self.relic_set.name, effect.Effect.Type.BUFF,
                    effect.Effect.DurationType.TURN_END, 1, "crt_dmg", mod)
        
        @event.member_listener(event.ListenerPriority.EXECUTE + 1)
        async def skill_group_trigger(self, skill_group):
            if self.target.skills["ultimate"] is not skill_group:
                return
            eff_add = effect.EffectAddition(self.target, self.target, self.effect, self.relic_set.config.get_skill_value("4pc", "duration"))
            await battle.current.event_bus.dispatch("add_effect", eff_add)

    def __init__(self):
        super().__init__("hunter_of_glacial_forest")

base.register_relic_set(HunterOfGlacialForest)
