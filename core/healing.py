from characters import base as character

class Healing:
    def __init__(self, healer, t, stat_desc):
        self.healer = healer
        self.target = t
        self.stat_desc = stat_desc
        self.multiplier = 1
    
    def calculate(self):
        mult = self.multiplier
        if isinstance(self.healer, character.Character):
            mult += self.healer.stats["outgoing_healing_boost"].calculate(healing=self) + self.target.stats["incoming_healing_boost"].calculate(healing=self)
        return self.stat_desc.calculate(healing=self) * mult
