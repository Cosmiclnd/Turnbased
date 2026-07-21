import uuid
import sys
import time
from tqdm import tqdm

from .. import config
from .. import battle
from .. import event
from .. import event_types
from .. import target
from .. import action
from ..characters import base as character

from . import base

class BattleFinished(Exception):
    pass

class DpavProvider(base.DecisionProvider):
    def __init__(self):
        self.total_dmg = {}
        self.dpavs = {}
        self.wins = 0

    def set_args(self, args):
        self.battle_config = args["battle"]

    def start(self):
        n = self.battle_config["repeats"]
        start_time = time.time()
        for _ in tqdm(range(n), desc="Simulating"):
            battle.current = battle.Battle()
            battle.current.action_list = action.ActionList()
            for record in self.battle_config["characters"]:
                character = config.load_class("characters", record["name"])(record)
                battle.current.characters.append(character)
            battle.current.monster_setup.set_record(self.battle_config["monsters"])
            for id, state in self.battle_config["initial_state"].items():
                t = target.from_uuid(uuid.UUID(id))
                t.initial_state = state
            for id in self.battle_config["techniques"]:
                t = target.from_uuid(uuid.UUID(id))
                t.use_technique = True
            battle.current.random = battle.Random({"use_random": True})
            battle.current.config = battle.BattleConfig(battle.BattleType.dict_nameid[self.battle_config["battle_config"]["type"]])
            for feature in self.battle_config["features"]:
                battle.current.features.use(feature)
            try:
                battle.current.start()
            except BattleFinished:
                pass
        end_time = time.time()
        print(f"Finished in {end_time - start_time}s")
        print("*" * 50)
        print(f"Win Rate: {round(100 * self.wins / n, 4)}%")
        print(f"Average Total DMG:")
        for t, dmg in self.total_dmg.items():
            print(f"  {t}:")
            self.print_array(dmg, indent=4)
        print(f"Average DPAV:")
        for t, dpav in self.dpavs.items():
            print(f"  {t}:")
            self.print_array(dpav, indent=4)
    
    def print_array(self, array, indent=0):
        avg = sum(array) / len(array)
        min_x = min(array)
        max_x = max(array)
        print(" " * indent + f"Min: {min_x}")
        print(" " * indent + f"Max: {max_x}")
        print(" " * indent + f"Avg: {avg}")
    
    def stop(self, win):
        self.wins += win
        action_value = battle.current.action_list.cur_action_value
        for t, dmg in self.dmg_record.items():
            if t.nameid not in self.total_dmg:
                self.total_dmg[t.nameid] = []
            self.total_dmg[t.nameid].append(dmg)
            if t.nameid not in self.dpavs:
                self.dpavs[t.nameid] = []
            self.dpavs[t.nameid].append(dmg / action_value)
        raise BattleFinished
    
    def on_battle_start(self):
        self.dmg_record = {}

        event.bus.add_member_listener(self.deal_damage, None, nameid="dpav_provider", name="DPAV Provider")

    def check_ultimate(self, character):
        if character.ultimate_activated:
            return False
        if not character.check_ultimate_energy():
            return False
        if not character.ultimate_available():
            return False
        return True
    
    def provide_ultimate(self):
        characters = []
        for c in battle.current.characters:
            if self.check_ultimate(c) and c.auto_battle.ultimate():
                characters.append(c)
        if characters:
            return max(characters, key=lambda c: c.auto_battle.ultimate_priority)
    
    def provide_ultimate_target(self, character):
        battle.current.cur_main_target = character.auto_battle.skill_target(character.skills["ultimate"])

    def provide_character_skill_option(self, character):
        skill_group = character.auto_battle.skill_option(character.skills)
        battle.current.cur_main_target = character.auto_battle.skill_target(skill_group)
        return skill_group
    
    @event.member_listener(event_types.Damage.AFTER_CALCULATE)
    def deal_damage(self, e):
        dmg = e.dmg
        if not isinstance(dmg.dealer, character.Character):
            return
        if dmg.dealer not in self.dmg_record:
            self.dmg_record[dmg.dealer] = 0
        self.dmg_record[dmg.dealer] += dmg.get_damage() or 0
