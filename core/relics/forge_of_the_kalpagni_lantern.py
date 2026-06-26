import modifier
import event
import enums
import effect
import battle

from relics import base

class ForgeOfTheKalpagniLantern(base.RelicSet):
    class PiecesEffect(base.RelicSet.PiecesEffect):
        def __init__(self, t, relic_set, pieces):
            super().__init__(t, relic_set, pieces)
            if self.pieces >= 2:
                mod1 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc((t.stats["spd"], modifier.ModifierFilter.BASE, relic_set.config.get_skill_value("2pc", "spd_boost"))),
                    None, t)
                t.stats["spd"].modifiers.append(mod1)
                mod2 = modifier.Modifier(self.relic_set.nameid, self.relic_set.name,
                    modifier.StatDesc((None, None, relic_set.config.get_skill_value("2pc", "break_eff_boost"))))
                self.effect = effect.ModifierEffect(self.relic_set.nameid, self.relic_set.name, effect.Effect.Type.BUFF,
                    effect.Effect.DurationType.TURN_END_CHECK_START, 1, "break_eff", mod2)
                battle.current.event_bus.add_member_listener(self.hit, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE + 1)
        async def hit(self, dmg):
            if self.target is not dmg.dealer:
                return
            if dmg.target.has_weakness(enums.Element.FIRE):
                eff_add = effect.EffectAddition(self.target, self.target, self.effect, self.relic_set.config.get_skill_value("2pc", "duration"))
                await battle.current.event_bus.dispatch("add_effect", eff_add)

    def __init__(self):
        super().__init__("forge_of_the_kalpagni_lantern")

base.register_relic_set(ForgeOfTheKalpagniLantern)
