import copy
from collections.abc import Iterable

import item
import event
import battle
import target
import enums
import damage

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
    class Type(enums.Enum):
        BUFF = item.Item("buff", "Buff")
        DEBUFF = item.Item("debuff", "Debuff")
        OTHERS = item.Item("others", "Others")
        ALL = (BUFF, DEBUFF, OTHERS)
    Type.init()
    
    class DurationType(enums.Enum):
        PERMANENT = item.Item("permanent", "Permanent")
        TURN_START = item.Item("turn_start", "Turn Start")
        TURN_END = item.Item("turn_end", "Turn End")
        TURN_END_CHECK_START = item.Item("turn_end_check_start", "Turn End (Check Start)")
        ALL = (PERMANENT, TURN_START, TURN_END, TURN_END_CHECK_START)
    DurationType.init()
    
    # 表示已经应用到某个target的状态效果
    class Instance:
        def __init__(self, eff, t):
            self.effect = eff
            self.target = t
            self.old_stacks = 0
        
        # 有关状态效果的信息改变后调用
        # 要求多次调用无副作用
        # 不要通过super()调用父类的refresh
        # 初始状态的设置也应该在refresh中进行
        async def refresh(self):
            self.old_stacks = self.target.effects.get_stacks(self.effect)

    def __init__(self, nameid, name, type, duration_type, max_stacks, dispellable=True):
        super().__init__(nameid, name)
        self.type = type
        self.duration_type = duration_type
        # max_stacks=0表示无限制
        self.max_stacks = max_stacks
        self.dispellable = dispellable
        self.group_name = None
    
    def print(self, indent=0):
        print(" " * indent + f"{self.name} ({self.nameid}) "
            f"<type={self.type.name}, duration_type={self.duration_type.name}, max_stacks={self.max_stacks}, dispellable={self.dispellable}>")
    
    def full_name(self):
        return f"{self.group_name}.{self.nameid}" if self.group_name is not None else self.nameid
    
    def new_instance(self, t):
        return self.Instance(self, t)
    
    def is_debuff_type(self, type):
        return False
    
    def is_dot(self, t):
        return False
    
    def is_immune(self, t):
        return False
    
    def can_act(self, t):
        return True

class ModifierEffect(Effect):
    class Instance(Effect.Instance):
        async def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            stat = self.target.stats[self.effect.stat_name]
            if self.old_stacks == 0 and stacks != 0:
                self.modifiers = [copy.copy(m) for m in self.effect.modifiers]
                stat.modifiers.extend(self.modifiers)
                self.mod_dead = item.DeadToggle(self.target)
                for mod in self.modifiers:
                    mod.master = self.mod_dead
            elif self.old_stacks != 0 and stacks == 0:
                self.mod_dead.dead_toggle = True
            for i in range(len(self.modifiers)):
                self.modifiers[i].stat_desc = self.effect.modifiers[i].stat_desc.scale(stacks)
            self.old_stacks = stacks

    def __init__(self, nameid, name, type_, duration_type, max_stacks, stat_name, modifiers, dispellable=True):
        super().__init__(nameid, name, type_, duration_type, max_stacks, dispellable)
        self.stat_name = stat_name
        self.modifiers = list(modifiers) if isinstance(modifiers, Iterable) else [modifiers]

class FrozenEffect(Effect):
    class Instance(Effect.Instance):
        async def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            if self.old_stacks == 0 and stacks != 0:
                self.listener_dead = item.DeadToggle(self.target)
                if self.effect.dmg_desc is not None:
                    self.dmg = await self.effect.dmg_desc.summon(self.target)
                battle.current.event_bus.add_member_listener(self.normal_turn_start, self.listener_dead)
            elif self.old_stacks != 0 and stacks == 0:
                self.listener_dead.dead_toggle = True
            self.old_stacks = stacks
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def normal_turn_start(self, turn):
            if self.target is not turn.target:
                return
            if self.effect.dmg_desc is not None:
                await battle.current.event_bus.dispatch("additional_damage", self.dmg)

    def __init__(self, dmg_desc=None, dispellable=True):
        super().__init__("frozen", "Frozen", Effect.Type.DEBUFF, Effect.DurationType.TURN_END, 1, dispellable)
        self.dmg_desc = dmg_desc

    def is_debuff_type(self, type):
        return type in (Debuff.FROZEN, Debuff.CONTROL)
    
    def can_act(self, t):
        return False

class DotEffect(Effect):
    class Instance(Effect.Instance):
        async def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            if self.old_stacks == 0 and stacks != 0:
                self.listener_dead = item.DeadToggle(self.target)
                battle.current.event_bus.add_member_listener(self.tick_dot, self.listener_dead)
                self.dmg = await self.effect.dmg_desc.summon(self.target)
            elif self.old_stacks != 0 and stacks == 0:
                self.listener_dead.dead_toggle = True
            self.old_stacks = stacks
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def tick_dot(self, dot):
            if self.target is not dot.target or not dot.filter(self.effect):
                return
            await battle.current.event_bus.dispatch("additional_damage", self.dmg.scale(dot.percentage * self.old_stacks))

    def __init__(self, nameid, name, dmg_desc, debuff_type, max_stacks, dispellable=True):
        super().__init__(nameid, name, Effect.Type.DEBUFF, Effect.DurationType.TURN_END, max_stacks, dispellable)
        self.dmg_desc = dmg_desc
        self.debuff_type = debuff_type
    
    def is_dot(self, t):
        return True
    
    def is_debuff_type(self, type):
        return type is self.debuff_type

class EffectTypes:
    def __init__(self, t=None):
        self.target = t
        self.groups = {}
    
    def add(self, group_name, eff, alias=None):
        if group_name not in self.groups:
            self.groups[group_name] = {}
        if alias is not None:
            self.groups[group_name][alias] = eff
        else:
            self.groups[group_name][eff.nameid] = eff
        eff.group_name = group_name
    
    def add_unique(self, eff, alias=None):
        self.add(self.target.nameid, eff, alias)
    
    def get(self, group_name, nameid):
        master = self.target.__class__
        if hasattr(master, "effect_types"):
            try:
                return master.effect_types.groups[group_name][nameid]
            except KeyError:
                pass
        return self.groups[group_name][nameid]

class EffectList:
    def __init__(self, t):
        self.target = t
        # effects格式为{effect: {duration: stacks}}
        # duration=-1表示永久持续
        self.effects = {}
        # instance一旦被添加就不会被删除
        # effect.Instance的实现保证没有副作用
        self.instances = {}
        self.start_effects = []

        battle.current.event_bus.add_member_listener(self.normal_turn_start, t)
        battle.current.event_bus.add_member_listener(self.normal_turn_end, t)
    
    def print(self, indent=0):
        print(" " * indent + f"{self.target.nameid}.effects:")
        for eff in self.effects.keys():
            eff.print(indent + 2)
            for duration, stacks in self.effects[eff].items():
                if duration == -1:
                    print(" " * (indent + 4) + f"Permanent: {stacks}")
                else:
                    print(" " * (indent + 4) + f"{duration} turn(s): {stacks}")
    
    async def add(self, eff, duration, stacks=1):
        if eff.is_immune(self.target):
            return False
        if eff not in self.instances:
            self.instances[eff] = eff.new_instance(self.target)
        if eff not in self.effects:
            self.effects[eff] = {}
        if duration not in self.effects[eff]:
            self.effects[eff][duration] = 0
        self.effects[eff][duration] += stacks
        current_stacks = self.get_stacks(eff)
        if eff.max_stacks != 0 and current_stacks > eff.max_stacks:
            await self.remove(eff, current_stacks - eff.max_stacks)
        await self.instances[eff].refresh()
        return True
    
    async def remove(self, eff, stacks):
        durations = self.effects[eff]
        for duration in sorted(durations.keys()):
            if duration == -1:
                continue
            if durations[duration] >= stacks:
                durations[duration] -= stacks
                if durations[duration] == 0:
                    del durations[duration]
                break
            else:
                stacks -= durations[duration]
                del durations[duration]
        if not durations:
            del self.effects[eff]
        await self.instances[eff].refresh()
    
    async def delete(self, eff):
        if eff in self.effects:
            del self.effects[eff]
        await self.instances[eff].refresh()
    
    async def advance_turn(self, eff):
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
        await self.instances[eff].refresh()
    
    def has_effect(self, eff):
        return eff in self.effects
    
    def get_stacks(self, eff):
        if not self.has_effect(eff):
            return 0
        return sum(self.effects[eff].values())
    
    def has_debuff(self, debuff):
        for eff in self.effects.keys():
            if eff.is_debuff_type(debuff):
                return True
        return False
    
    def can_act(self):
        for eff in self.effects.keys():
            if not eff.can_act(self.target):
                return False
        return True
    
    async def dispel(self, count, f=None):
        for i in range(count):
            effects = list(filter(lambda eff: eff.dispellable and (f is None or f(eff)), self.effects.keys()))
            if not effects:
                return i
            import random  # TODO: battle.current.random
            eff = random.choice(effects)
            await self.remove(eff, 1)
        return count
    
    async def die(self):
        for eff in list(self.effects.keys()):
            await self.delete(eff)
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS)
    async def normal_turn_start(self, turn):
        if self.target is not turn.target:
            return
        for eff in list(self.effects.keys()):
            if eff.duration_type == Effect.DurationType.TURN_START:
                await self.advance_turn(eff)
        self.start_effects = list(self.effects.keys())
        await battle.current.event_bus.dispatch("tick_dot", damage.DotTick(self.target, lambda x: True, 1))
    
    @event.member_listener(event.ListenerPriority.POST_PROCESS)
    async def normal_turn_end(self, turn):
        if self.target is not turn.target:
            return
        for eff in list(self.effects.keys()):
            if eff.duration_type == Effect.DurationType.TURN_END:
                await self.advance_turn(eff)
            elif eff.duration_type == Effect.DurationType.TURN_END_CHECK_START and eff in self.start_effects:
                await self.advance_turn(eff)

class EffectAddition:
    __slots__ = ("adder", "target", "effect", "duration", "stacks")

    def __init__(self, adder, t, eff, duration, stacks=1):
        self.adder = adder
        self.target = t
        self.effect = eff
        self.duration = duration
        self.stacks = stacks
