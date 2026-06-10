import random

import event
import action
import item
import target
import modifier
import server

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
        self.action_list = item.ItemList()
        self.current_action_value = 0
        self.skillpoints = Skillpoints()
        self.characters = item.ItemList()
        self.monsters = item.ItemList()
        self.target_index = 0

        self.event_bus.add_member_listener(self.battle_start, nameid="battle", name="Battle")
    
    def refresh(self):
        self.characters.refresh()
        self.monsters.refresh()
    
    async def prepare_next_action_unit(self):
        verbose = True
        while True:
            message = await server.send_and_recv({"type": "prepare_next_action_unit", "verbose": verbose})
            if message["type"] == "empty":
                break
            if message["type"] == "prepare_ultimate":
                await self.event_bus.dispatch("prepare_ultimate", self.characters[message["index"]])
            verbose = False
    
    async def start(self):
        await self.event_bus.dispatch("battle_start")
        while True:
            await self.prepare_next_action_unit()
            self.action_list.refresh()
            self.action_list.sort(key=lambda x: x.sort_key())
            await self.event_bus.dispatch("action_unit_trigger", self.action_list[0])
            if not self.monsters:
                await server.send_and_recv({"type": "battle_win"})
                break
            if not self.characters:
                await server.send_and_recv({"type": "battle_lose"})
                break
    
    @event.member_listener(event.ListenerPriority.END)
    async def battle_start(self):
        for t in self.characters + self.monsters:
            self.action_list.append(target.Target.NormalTurn(t))

current = None
