import item
import event
import battle
import enums

class SkillType(enums.Enum):
    SINGLE = item.Item("single", "Single Target")
    BLAST = item.Item("blast", "Blast")
    BOUNCE = item.Item("bounce", "Bounce")
    AOE = item.Item("aoe", "AoE")
    RESTORE = item.Item("restore", "Restore")
    SUPPORT = item.Item("support", "Support")
    OTHERS = item.Item("others", "Others")
    ALL = (SINGLE, BLAST, BOUNCE, AOE, RESTORE, SUPPORT, OTHERS)
SkillType.init()

class Skill(item.Item):
    def __init__(self, nameid, name, type, t, level=None):
        super().__init__(nameid, name)
        self.type = type
        self.target = t
        self.level = level
    
    def available(self):
        return "ok"

class SkillGroup:
    def __init__(self, t):
        self.target = t
        self.skills = item.ItemList()
        self.current = 0
        battle.current.event_bus.add_member_listener(self.skill_group_trigger, t)
    
    def available(self):
        return self.skills[self.current].available()
    
    def add(self, skill):
        self.skills.append(skill)
    
    def set_level(self, level):
        for skill in self.skills:
            skill.level = level
    
    def set_bonus_level(self, level):
        for skill in self.skills:
            skill.bonus_level += level
    
    @event.member_listener(priority=event.ListenerPriority.EXECUTE)
    async def skill_group_trigger(self, skill_group):
        if self is not skill_group:
            return
        await battle.current.event_bus.dispatch("skill_trigger", self.skills[self.current])
