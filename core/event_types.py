from ._event import Event, EventStage

def define_event(*stage_names):
    def wrapper(cls):
        for i, name in enumerate(stage_names):
            setattr(cls, name, EventStage(cls, i))
        return cls
    return wrapper

@define_event("CREATE", "BEFORE_CALCULATE", "CALCULATE", "AFTER_CALCULATE", "BEFORE_TAKE", "TAKE", "AFTER_TAKE")
class Damage(Event):
    def __init__(self, dmg):
        super().__init__(dmg.dealer)
        self.dmg = dmg

@define_event("BEFORE_TRIGGER", "TRIGGER", "AFTER_TRIGGER")
class SkillGroupTrigger(Event):
    def __init__(self, skill_group):
        super().__init__(skill_group)
        self.skill_group = skill_group

@define_event("BEFORE_TRIGGER", "MESSAGE", "TRIGGER", "AFTER_TRIGGER")
class SkillTrigger(Event):
    def __init__(self, skill):
        super().__init__(skill)
        self.skill = skill
