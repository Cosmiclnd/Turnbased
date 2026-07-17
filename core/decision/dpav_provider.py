import uuid
import sys

import config
import battle
import event
import target
import action

from decision import base

class DpavProvider(base.DecisionProvider):
    def __init__(self):
        self.dmg_record = {}

    def set_args(self, args):
        self.battle_config = args["battle"]

    def start(self):
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
        battle.current.start()
    
    def stop(self):
        action_value = battle.current.action_list.cur_action_value
        print(f"Action Value Elapsed: {action_value}")
        print("Damage Record:")
        for t, dmg in self.dmg_record.items():
            print(f"{t.name}: {dmg}  (DPAV = {dmg / action_value})")
        sys.exit()
    
    def on_battle_start(self):
        battle.current.event_bus.add_member_listener(self.deal_damage, nameid="dpav_provider", name="DPAV Provider")

    def check_ultimate(self, character):
        if character.ultimate_activated:
            return False
        if not character.check_ultimate_energy():
            return False
        if not character.ultimate_available():
            return False
        return True
    
    def provide_ultimate(self):
        for c in battle.current.characters:
            if self.check_ultimate(c):
                return c
    
    @event.member_listener(event.ListenerPriority.EXECUTE - 1)
    def deal_damage(self, dmg):
        if dmg.dealer not in self.dmg_record:
            self.dmg_record[dmg.dealer] = 0
        self.dmg_record[dmg.dealer] += dmg.get_damage() or 0
    
    # TODO: more complex logic

    def provide_character_skill_option(self, character):
        battle.current.cur_main_target = battle.current.monsters[0]
        return character.skills["basic_atk"]
