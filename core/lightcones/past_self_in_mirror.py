from .. import item
from .. import modifier
from .. import effect
from .. import event
from .. import event_types
from .. import battle

from . import base

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
            event.bus.add_member_listener(self.ultimate, self.target, self.target)
            event.bus.add_member_listener(self.new_wave_start, None, self.target, unique=True)
    
    @event.member_listener(event_types.Ultimate.AFTER_TRIGGER)  # 经确认该效果确实在AFTER_TRIGGER阶段执行
    def ultimate(self, e):
        for c in battle.current.characters:
            eff_add = effect.EffectAddition(self.target, c, self.effect_types.get(self.nameid, "eff"), self.get_value("duration"))
            event.bus.dispatch(event_types.AddEffect(eff_add))
        if self.target.stats["break_eff"].calculate() >= self.get_value("break_eff_threshold"):
            battle.current.skillpoints.modify(1)
    
    @event.member_listener(event_types.NewWave.START)
    def new_wave_start(self, e):
        for c in battle.current.characters:
            event.bus.dispatch(event_types.RegenEnergy(c, self.get_value("energy_regen"), True))
