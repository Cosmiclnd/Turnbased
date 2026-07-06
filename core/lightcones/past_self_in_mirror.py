import item
import modifier
import effect
import event
import battle

from lightcones import base

class PastSelfInMirror(base.LightCone):
    def __init__(self, record):
        super().__init__("past_self_in_mirror", record)

    def apply(self, t):
        super().apply(t)
        if self.valid:
            mod1 = modifier.Modifier(self.nameid, self.name,
                modifier.StatDesc((None, None, self.get_value("break_eff_boost"))), None, t)
            t.stats["break_eff"].modifiers.append(mod1)
            mod2 = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, self.get_value("dmg_boost"))))
            self.effect_types.add_unique(effect.ModifierEffect("effect", self.name, effect.Effect.Type.BUFF,
                effect.Effect.DurationType.TURN_END_CHECK_START, 1, "dmg_boost", mod2), "eff")
            battle.current.event_bus.add_member_listener(self.ultimate_turn, self.target)
            battle.current.event_bus.add_member_listener(self.new_wave_start, self.target, unique=True)
    
    @event.member_listener(event.ListenerPriority.POST_PROCESS)
    async def ultimate_turn(self, turn):
        if self.target is not turn.target:
            return
        for c in battle.current.characters:
            eff_add = effect.EffectAddition(self.target, c, self.effect_types.get(self.nameid, "eff"), self.get_value("duration"))
            await battle.current.event_bus.dispatch("add_effect", eff_add)
        if self.target.stats["break_eff"].calculate() >= self.get_value("break_eff_threshold"):
            battle.current.skillpoints.modify(1)
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS)
    async def new_wave_start(self):
        for c in battle.current.characters:
            await battle.current.event_bus.dispatch("regen_energy", c, self.get_value("energy_regen"), True)
