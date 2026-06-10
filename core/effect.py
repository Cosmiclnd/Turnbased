import item
import event
import battle
import target
import enums

class Debuff(enums.Enum):
    # 在需要时指定
    BLEED = item.Item("bleed", "Bleed")
    BURN = item.Item("burn", "Burn")
    FROZEN = item.Item("frozen", "Frozen")
    SHOCK = item.Item("shock", "Shock")
    WIND_SHEER = item.Item("wind_sheer", "Wind Sheer")
    ENTANGLEMENT = item.Item("entanglement", "Entanglement")
    IMPRISONMENT = item.Item("imprisonment", "Imprisonment")
    CONTROL = item.Item("control", "Control")
    ALL = (BLEED, BURN, FROZEN, SHOCK, WIND_SHEER, ENTANGLEMENT, IMPRISONMENT, CONTROL)
Debuff.init()

class Effect(item.Item):
    id = 0

    class Type:
        BUFF = 0
        DEBUFF = 1
        OTHER = 2

    def __init__(self, nameid, name, id, type):
        super().__init__(nameid, name)
        self.id = id
        self.type = type
        self.target = None
    
    def dead(self):
        return self.target is None or self.target.dead()
    
    def apply(self, target):
        target.effects[self.id] = self
        self.target = target
    
    def remove(self, target):
        if self.id in target.effects:
            del target.effects[self.id]
        self.target = None
    
    def get_debuff_res(self, target):
        # 仅对Debuff有效
        return 0

    @classmethod
    def next_id(cls):
        cls.id += 1
        return cls.id

class CommonEffect(Effect):
    class DurationType:
        PERMANENT = 0
        TURN_START = 1
        TURN_END = 2

    def __init__(self, nameid, name, id, type, duration, duration_type, max_stacks):
        # duration=-1表示永久持续
        super().__init__(nameid, name, id, type)
        self.durations = {duration: 1}
        self.duration_type = duration_type
        self.max_stacks = max_stacks
    
    def refresh(self, target):
        pass
    
    def apply(self, target):
        if self.id in target.effects:
            target.effects[self.id].add_stacks(self.durations)
            target.effects[self.id].refresh(target)
        else:
            super().apply(target)
            self.refresh(target)
            if self.duration_type == self.DurationType.TURN_START:
                battle.current.event_bus.add_member_listener(self.turn_start, self)
            elif self.duration_type == self.DurationType.TURN_END:
                battle.current.event_bus.add_member_listener(self.turn_end, self)
    
    def remove(self, target):
        duration = min(filter(lambda x: x >= 0, self.durations.keys()))
        self.durations[duration] -= 1
        if self.durations[duration] == 0:
            del self.durations[duration]
        if self.get_stacks() == 0 and self.id in target.effects:
            del target.effects[self.id]
            self.target = None
            self.refresh(target)
    
    def get_stacks(self):
        return sum(self.durations.values())
    
    def add_stacks(self, durations):
        for duration, stacks in durations.items():
            if duration in self.durations:
                self.durations[duration] += stacks
            else:
                self.durations[duration] = stacks
        excess = self.get_stacks() - self.max_stacks
        if excess > 0:
            for duration in sorted(self.durations.keys()):
                if excess <= 0:
                    break
                if duration < 0:
                    continue
                stacks = self.durations[duration]
                remove = min(excess, stacks)
                self.durations[duration] -= remove
                excess -= remove
                if self.durations[duration] == 0:
                    del self.durations[duration]
    
    def advance_turn(self):
        target = self.target
        self.durations = {k - 1 if k > 0 else -1: v for k, v in self.durations.items() if k != 1}
        if self.get_stacks() == 0 and self.id in self.target.effects:
            del self.target.effects[self.id]
            self.target = None
            self.refresh(target)
    
    @event.member_listener(event.ListenerPriority.START, "normal_turn")
    async def turn_start(self, t):
        if self.target is not t:
            return
        self.advance_turn()
    
    @event.member_listener(event.ListenerPriority.END, "normal_turn")
    async def turn_end(self, t):
        if self.target is not t:
            return
        self.advance_turn()

class ModifierEffect(CommonEffect):
    def __init__(self, nameid, name, id, type, duration, duration_type, max_stacks, modifier, stat):
        super().__init__(nameid, name, id, type, duration, duration_type, max_stacks)
        self.modifier = modifier
        self.stat_desc = modifier.stat_desc.scale(1)
        self.stat = stat
    
    def refresh(self, target):
        stacks = self.get_stacks()
        self.modifier.stat_desc = self.stat_desc.scale(stacks)
        if self.target is not None and  self.modifier not in self.stat.modifiers:
            self.stat.modifiers.append(self.modifier)
        if self.target is None and self.modifier in self.stat.modifiers:
            self.stat.modifiers.remove(self.modifier)

class FrozenEffect(CommonEffect):
    eff_id = Effect.next_id()

    def __init__(self, duration, additional_dmg=None):
        super().__init__("frozen", "Frozen", self.eff_id, Effect.Type.DEBUFF, duration, CommonEffect.DurationType.TURN_END, 1)
        self.additional_dmg = additional_dmg
    
    def refresh(self, target):
        target.frozen = self.get_stacks() > 0
    
    def get_debuff_res(self, target):
        return target.stats["control_res"].calculate(effect=self)
    
    @event.member_listener(event.ListenerPriority.END, "normal_turn")
    async def turn_end(self, t):
        if self.target is not t:
            return
        if self.additional_dmg is not None:
            await battle.current.event_bus.dispatch("deal_damage", self.additional_dmg)
        target.Target.NormalTurn.advance_target(t, 0.5)
        self.advance_turn()
