import copy

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

# 表示一种状态效果类型
# 不同的Effect实例是不同的状态效果类型
class Effect(item.Item):
    class Type:
        BUFF = 0
        DEBUFF = 1
        OTHER = 2
    
    class DurationType:
        PERMANENT = 0
        TURN_START = 1
        TURN_END = 2
    
    # 表示已经应用到某个target的状态效果
    class Instance:
        def __init__(self, eff, t):
            self.effect = eff
            self.target = t
            self.old_stacks = 0
        
        # 有关状态效果的信息改变后调用
        # 要求多次调用无副作用
        # 不要通过super()调用父类的refresh
        def refresh(self):
            self.old_stacks = self.target.effects.get_stacks(self.effect)

    def __init__(self, nameid, name, type, duration_type, max_stacks, dispellable=True):
        super().__init__(nameid, name)
        self.type = type
        self.duration_type = duration_type
        self.max_stacks = max_stacks
        self.dispellable = dispellable
    
    def new_instance(self, t):
        return self.Instance(self, t)
    
    def is_debuff_type(self, type):
        return False

class ModifierEffect(Effect):
    class Instance(Effect.Instance):
        def __init__(self, eff, t):
            super().__init__(eff, t)
            self.mod = copy.copy(eff.mod)

        def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            stat = self.target.stats[self.effect.stat_name]
            if stacks != 0 and self.mod not in stat.modifiers:
                stat.modifiers.append(self.mod)
            elif stacks == 0 and self.mod in stat.modifiers:
                stat.modifiers.remove(self.mod)
            self.mod.stat_desc = self.effect.mod.stat_desc.scale(stacks)
            self.old_stacks = stacks

    def __init__(self, nameid, name, type, duration_type, max_stacks, stat_name, mod, dispellable=True):
        super().__init__(nameid, name, type, duration_type, max_stacks, dispellable)
        self.stat_name = stat_name
        self.mod = mod

class FrozenEffect(Effect):
    class Instance(Effect.Instance):
        def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            if self.old_stacks == 0 and stacks != 0:
                self.listener = battle.current.event_bus.add_member_listener(self.turn_end, item.DeadToggle(self.target))
            elif self.old_stacks != 0 and stacks == 0:
                self.listener.master.dead_toggle = True
            self.old_stacks = stacks
        
        @event.member_listener(event.ListenerPriority.POST_PROCESS, "normal_turn")
        async def turn_end(self, t):
            if self.target is not t:
                return
            if self.effect.additional_dmg is not None:
                await battle.current.event_bus.dispatch("deal_damage", self.effect.additional_dmg)

    def __init__(self, additional_dmg=None, dispellable=True):
        super().__init__("frozen", "Frozen", Effect.Type.DEBUFF, Effect.DurationType.TURN_END, 1, dispellable)
        self.additional_dmg = additional_dmg

    def is_debuff_type(self, type):
        return type in (Debuff.FROZEN, Debuff.CONTROL)

class EffectList:
    def __init__(self, t):
        self.target = t
        self.effects = {}
        # effects格式为{effect: {duration: stacks}}
        # duration=-1表示永久持续
        self.instances = {}

        battle.current.event_bus.add_member_listener(self.turn_start, t)
        battle.current.event_bus.add_member_listener(self.turn_end, t)
    
    def add(self, eff, duration, stacks=1):
        if eff not in self.instances:
            self.instances[eff] = eff.new_instance(self.target)
        if eff not in self.effects:
            self.effects[eff] = {}
        if duration not in self.effects[eff]:
            self.effects[eff][duration] = 0
        self.effects[eff][duration] += stacks
        current_stacks = self.get_stacks(eff)
        if current_stacks > eff.max_stacks:
            self.remove(eff, current_stacks - eff.max_stacks)
        self.instances[eff].refresh()
    
    def remove(self, eff, stacks):
        durations = self.effects[eff]
        for duration in sorted(durations.keys()):
            if duration == -1:
                continue
            if durations[duration] >= stacks:
                durations[duration] -= stacks
                break
            else:
                stacks -= durations[duration]
                del durations[duration]
                if not durations:
                    del self.effects[eff]
        self.instances[eff].refresh()
    
    def advance_turn(self, eff):
        durations = self.effects[eff]
        self.effects[eff] = {}
        for duration in sorted(durations.keys()):
            if duration == -1:
                self.effects[eff][-1] = durations[-1]
                continue
            if duration > 1:
                self.effects[eff][duration - 1] = durations[duration]
        if not self.effects[eff]:
            del self.effects[eff]
        self.instances[eff].refresh()
    
    def get_stacks(self, eff):
        if eff not in self.effects:
            return 0
        return sum(self.effects[eff].values())
    
    def has_debuff(self, debuff):
        for eff in self.effects.keys():
            if eff.is_debuff_type(debuff):
                return True
        return False
    
    @event.member_listener(event.ListenerPriority.START, "normal_turn")
    async def turn_start(self, t):
        if self.target is not t:
            return
        for eff in list(self.effects.keys()):
            if eff.duration_type == Effect.DurationType.TURN_START:
                self.advance_turn(eff)
    
    @event.member_listener(event.ListenerPriority.END, "normal_turn")
    async def turn_end(self, t):
        if self.target is not t:
            return
        for eff in list(self.effects.keys()):
            if eff.duration_type == Effect.DurationType.TURN_END:
                self.advance_turn(eff)

class EffectAddition:
    def __init__(self, adder, t, eff, duration, stacks=1):
        self.adder = adder
        self.target = t
        self.effect = eff
        self.duration = duration
        self.stacks = stacks
