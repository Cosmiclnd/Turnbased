from ._event import Period, Event, EventStage

NO_MAIN_ARG = 0

def define_event(*stage_names):
    def wrapper(cls):
        for i, name in enumerate(stage_names):
            setattr(cls, name, EventStage(cls, i))
        return cls
    return wrapper

@define_event("INIT", "INIT_WAVE", "PASSIVES", "BEFORE_START", "START")
class BattleStart(Event):
    __slots__ = ()

    def __init__(self):
        super().__init__(None, NO_MAIN_ARG)

@define_event("BEFORE_RESET", "RESET", "START")
class NewWave(Event):
    __slots__ = ()

    def __init__(self):
        super().__init__(None, NO_MAIN_ARG)

@define_event("EXECUTE")
class AddMonster(Event):
    __slots__ = ("target",)

    def __init__(self, t):
        super().__init__(None, t)
        self.target = t

@define_event("EXECUTE")
class CurHpModify(Event):
    __slots__ = ("target", "amount")

    def __init__(self, t, amount):
        super().__init__(None, t)
        self.target = t
        self.amount = amount

@define_event("CREATE", "BEFORE_CALCULATE", "CALCULATE", "AFTER_CALCULATE", "BEFORE_TAKE", "TAKE", "AFTER_TAKE")
class Damage(Event):
    __slots__ = ("dmg",)

    def __init__(self, dmg):
        super().__init__(None, dmg.dealer)
        self.dmg = dmg

@define_event("BEFORE_HIT", "HIT", "AFTER_HIT")
class Hit(Event):
    __slots__ = ("dmg",)

    def __init__(self, dmg):
        super().__init__(None, dmg.dealer)
        self.dmg = dmg

@define_event("BEFORE_HIT", "HIT", "AFTER_HIT")
class AdditionalDamage(Event):
    __slots__ = ("dmg",)

    def __init__(self, dmg):
        super().__init__(None, dmg.dealer)
        self.dmg = dmg

@define_event("BEFORE_EXECUTE", "EXECUTE")
class Heal(Event):
    __slots__ = ("heal",)

    def __init__(self, heal):
        super().__init__(None, heal.healer)
        self.heal = heal

@define_event("BEFORE_EXECUTE", "EXECUTE", "AFTER_EXECUTE")
class AddEffect(Event):
    __slots__ = ("eff_add",)

    def __init__(self, eff_add):
        super().__init__(None, eff_add.target)
        self.eff_add = eff_add

@define_event("BEFORE_EXECUTE", "EXECUTE", "AFTER_EXECUTE")
class RegenEnergy(Event):
    __slots__ = ("target", "amount", "fixed")

    def __init__(self, target, amount, fixed=False):
        super().__init__(None, target)
        self.target = target
        self.amount = amount
        self.fixed = fixed

@define_event("BEFORE_TRIGGER", "TRIGGER", "AFTER_TRIGGER")
class SkillGroupTrigger(Event):
    __slots__ = ("skill_group",)

    def __init__(self, skill_group):
        super().__init__(None, skill_group)
        self.skill_group = skill_group

@define_event("BEFORE_TRIGGER", "MESSAGE", "TRIGGER", "AFTER_TRIGGER")
class SkillTrigger(Event):
    __slots__ = ("skill",)

    def __init__(self, skill):
        super().__init__(None, skill)
        self.skill = skill

@define_event("COMMON_DOT", "AFTER_COMMON_DOT")
class TickDot(Event):
    __slots__ = ("dot_tick",)

    def __init__(self, dot_tick):
        super().__init__(None, dot_tick.target)
        self.dot_tick = dot_tick

@define_event("EXECUTE")
class ExtraTurn(Event):
    __slots__ = ("turn",)

    def __init__(self, turn):
        super().__init__(None, turn)
        self.turn = turn

@define_event("BEFORE_TRIGGER", "TRIGGER", "AFTER_TRIGGER")
class Ultimate(Event):
    __slots__ = ("target",)

    def __init__(self, t):
        super().__init__(None, t)
        self.target = t

@define_event("EXECUTE")
class TargetAction(Event):
    __slots__ = ("target",)

    def __init__(self, t):
        super().__init__(None, t)
        self.target = t

@define_event("EXECUTE", "AFTER_EXECUTE", "CHECK")
class ReduceToughness(Event):
    __slots__ = ("tr",)

    def __init__(self, tr):
        super().__init__(None, tr.dealer)
        self.tr = tr

@define_event("EFFECT", "BEFORE_BREAK", "BREAK", "AFTER_BREAK")
class BreakWeakness(Event):
    __slots__ = ("tr",)

    def __init__(self, tr):
        super().__init__(None, tr.dealer)
        self.tr = tr

@define_event("BEFORE_EXECUTE", "EXECUTE", "AFTER_EXECUTE")
class RecoverToughness(Event):
    __slots__ = ("target",)

    def __init__(self, t):
        super().__init__(None, t)
        self.target = t

@define_event("REVIVE", "EXECUTE", "AFTER_EXECUTE")
class Die(Event):
    __slots__ = ("target",)

    def __init__(self, t):
        super().__init__(None, t)
        self.target = t

@define_event("ENERGY", "EXECUTE", "AFTER_EXECUTE")
class Clean(Event):
    __slots__ = ("target",)

    def __init__(self, t):
        super().__init__(None, t)
        self.target = t

@define_event("EXECUTE")
class ActionAdvance(Event):
    __slots__ = ("turn", "scale")

    def __init__(self, turn, scale):
        super().__init__(None, turn)
        self.turn = turn
        self.scale = scale

@define_event("EXECUTE")
class ActionDelay(Event):
    __slots__ = ("turn", "scale")

    def __init__(self, turn, scale):
        super().__init__(None, turn)
        self.turn = turn
        self.scale = scale

class NormalTurn(Period):
    @define_event("MESSAGE", "EFFECT", "EXECUTE")
    class Start(Event):
        __slots__ = ("turn",)

        def __init__(self, turn):
            super().__init__(NormalTurn, turn)
            self.turn = turn
    
    @define_event("EXECUTE", "EFFECT")
    class End(Event):
        __slots__ = ("turn",)

        def __init__(self, turn):
            super().__init__(NormalTurn, turn)
            self.turn = turn
    
    @define_event("EXECUTE")
    class Act(Event):
        __slots__ = ("turn",)

        def __init__(self, turn):
            super().__init__(NormalTurn, turn)
            self.turn = turn

class Attack(Period):
    @define_event("EXECUTE")
    class Start(Event):
        __slots__ = ("target",)

        def __init__(self, t):
            super().__init__(Attack, t)
            self.target = t
    
    @define_event("EXECUTE")
    class End(Event):
        __slots__ = ("target",)

        def __init__(self, t):
            super().__init__(Attack, t)
            self.target = t

@define_event("LOCK_ON", "DEFAULT")
class GetMonsterSkillTarget(Event):
    __slots__ = ("target",)

    def __init__(self, t):
        super().__init__(None, t)
        self.target = t
