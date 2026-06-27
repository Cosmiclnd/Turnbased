import random

import event
import action
import item
import target
import modifier
import server
from monsters import base as monster

class Skillpoints:
    def __init__(self):
        self.current = 3
        self.max = modifier.Stat("skillpoints")
        self.max.base_value = 5
    
    def refresh(self):
        m = int(self.max.calculate())
        if self.current > m:
            self.current = m
    
    def available(self, delta_skillpoints):
        self.refresh()
        return self.current + delta_skillpoints >= 0
    
    def modify(self, delta_skillpoints):
        self.current += delta_skillpoints
        self.refresh()

class Battle:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.event_bus = event.EventBus()
        self.action_list = action.ActionList()
        self.skillpoints = Skillpoints()
        self.characters = item.ItemList()
        self.monsters = item.ItemList()
        self.monster_setup = monster.Setup()
        self.target_index = 0
        self.suspended = False

        self.event_bus.add_member_listener(self.battle_start, nameid="battle", name="Battle")
        self.event_bus.add_member_listener(self.add_monster, nameid="battle", name="Battle")
    
    def refresh(self):
        self.characters.refresh()
        self.monsters.refresh()
    
    def count_monsters(self):
        return sum(1 for m in self.monsters if m.countable())
    
    def all_targets(self):
        return self.characters + self.monsters
    
    async def check_targets(self):
        if await self.monster_setup.check():
            await server.send_and_recv({"type": "battle_win"})
            return True
        if not self.characters:
            await server.send_and_recv({"type": "battle_lose"})
            return True
        return False
    
    async def start(self):
        await self.event_bus.dispatch("battle_start")
        await self.monster_setup.check()
        while True:
            await self.action_list.next_normal_turn()
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS)
    async def battle_start(self):
        for t in self.characters[::-1]:
            self.action_list.normals.append(t.new_normal_turn())
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS)
    async def add_monster(self, m):
        self.monsters.append(m)
        turn = m.new_normal_turn()
        self.action_list.normals.append(turn)
        turn.advance(1 - m.first_turn_delay)

current = None
