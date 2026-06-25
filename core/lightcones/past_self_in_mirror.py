import item
import modifier
import effect
import event
import battle

from lightcones import base

class PastSelfInMirror(base.LightCone):
    inited = False

    def __init__(self, record):
        super().__init__("past_self_in_mirror", record)

    def apply(self, t):
        super().apply(t)
        if self.valid:
            mod1 = modifier.Modifier(self.nameid, self.name,
                modifier.StatDesc((None, None, self.get_value("break_eff_boost"))), None, t)
            t.stats["break_eff"].modifiers.append(mod1)
            mod2 = modifier.Modifier(self.nameid, self.name, modifier.StatDesc((None, None, self.get_value("dmg_boost"))))
            self.effect = effect.ModifierEffect(self.nameid, self.name, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END,
                1, "dmg_boost", mod2)
            battle.current.event_bus.add_member_listener(self.ultimate_turn, self.target)
            self.init_class()
    
    def init_class(self):
        cls = self.__class__
        if cls.inited:
            return
        cls.inited = True
        battle.current.event_bus.add_member_listener(self.new_wave_start, self.target)
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS)
    async def ultimate_turn(self, t):
        if self.target is not t:
            return
        for c in battle.current.characters:
            eff_add = effect.EffectAddition(self.target, c, self.effect, self.get_value("duration"))
            await battle.current.event_bus.dispatch("add_effect", eff_add)
        if self.target.stats["break_eff"].calculate() >= self.get_value("break_eff_threshold"):
            battle.current.skillpoints.modify(1)
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS)
    async def new_wave_start(self):
        for c in battle.current.characters:
            await battle.current.event_bus.dispatch("regen_energy", c, self.get_value("energy_regen"))
