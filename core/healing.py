from dataclasses import dataclass

from . import modifier
from .characters import base as character

@dataclass(slots=True, eq=False)
class Healing:
    healer: object
    target: object
    stat_desc: modifier.StatDesc
    multiplier: float = 1
    
    def calculate(self):
        mult = self.multiplier
        if isinstance(self.healer, character.Character):
            mult += self.healer.stats["outgoing_healing_boost"].calculate(healing=self) + self.target.stats["incoming_healing_boost"].calculate(healing=self)
        return self.stat_desc.calculate(healing=self) * mult
