from . import battle

class AutoBattlePolicy:
    def __init__(self, t):
        self.target = t
        self.ultimate_priority = 0
    
    def ultimate(self):
        return True
    
    def skill_option(self, skill_groups):
        max_skillpoints = battle.current.skillpoints.max.calculate()
        skillpoints = battle.current.skillpoints.current
        if skillpoints > max_skillpoints * 0.2:
            return skill_groups["skill"]
        return skill_groups["basic_atk"]
    
    def skill_target(self, skill_group):
        raise NotImplementedError
