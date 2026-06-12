import target

class Healing:
    def __init__(self, healer, t, stat_desc):
        self.healer = healer
        self.target = t
        self.stat_desc = stat_desc
    
    def calculate(self):
        mult = 1
        if isinstance(self.healer, target.Character):
            mult += self.healer.stats["outgoing_healing_boost"].calculate(healing=self) + self.target.stats["incoming_healing_boost"].calculate(healing=self)
        return self.stat_desc.calculate(healing=self) * mult
