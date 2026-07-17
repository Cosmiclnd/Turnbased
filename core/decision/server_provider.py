import logging
import uuid
from websockets.sync.server import serve

import battle
import server
import target
from characters import base as character

from decision import base

class ServerProvider(base.DecisionProvider):
    def start(self):
        with serve(server.handle, "127.0.0.1", server.port) as s:
            logging.info("Listening on 127.0.0.1:%d", server.port)
            s.serve_forever()
    
    def stop(self):
        server.handler.flush_updates()
        server.handler.close()

    def on_battle_start(self):
        server.handler.add_answer_handler("action_order", self.respond_action_order)
        server.handler.add_answer_handler("current_characters", self.respond_current_characters)
        server.handler.add_answer_handler("current_monsters", self.respond_current_monsters)
        server.handler.add_answer_handler("character_skill_options", self.respond_character_skill_options)
    
    def notify(self, message):
        server.handler.update_client(message)
        
    @server.server_handler
    def skill_target_validator(self, skill, target):
        if skill.target_info is None:
            return "internal_error"
        type = skill.target_info["type"]
        selection = skill.target_info["selection"]
        if type == "monster":
            if target is not None and isinstance(target, character.Character):
                return "bad_target"
            if selection == "all" and target is not None:
                return "bad_target"
            if selection != "all" and target is None:
                return "bad_target"
            return "ok"
        elif type == "character":
            if target is not None and not isinstance(target, character.Character):
                return "bad_target"
            if selection == "self" and target is not skill.target:
                return "bad_target"
            if selection == "all" and target is not None:
                return "bad_target"
            if selection != "all" and target is None:
                return "bad_target"
            return "ok"
        return "internal_error"

    @server.server_handler
    def check_ultimate(self, character, message):
        if character.ultimate_activated:
            return "ultimate_activated"
        if not character.check_ultimate_energy():
            return "not_enough_energy"
        if not character.ultimate_available():
            return "ultimate_not_available"
        return "ok"
    
    @server.server_handler
    def ultimate_handler(self, message):
        self.ultimate_character = None
        if message.get("type") == "empty":
            return "ok"
        if message.get("type") != "ask" or message.get("name") != "ultimate":
            return "invalid_message_type"
        try:
            id = uuid.UUID(message["character"])
            import target  # TODO: Python 3.15 lazy import
            c = target.from_uuid(id)
            if c is None:
                return "target_not_found"
            from characters import base as character  # TODO: Python 3.15 lazy import
            if not isinstance(c, character.Character):
                return "target_not_character"
            info = self.check_ultimate(c, message)
            if info == "ok":
                self.ultimate_character = c
                return "ok"
            else:
                return info
        except KeyError:
            return "invalid_message"
        return "internal_error"
    
    def provide_ultimate(self):
        server.handler.ask_client({"name": "ultimate"}, self.ultimate_handler)
        return self.ultimate_character
    
    @server.server_handler
    def check_ultimate_target(self, message):
        battle.current.cur_main_target = None
        if "target" in message:
            battle.current.cur_main_target = target.from_uuid(uuid.UUID(message["target"]))
            if battle.current.cur_main_target is None:
                return "target_not_found"
        info = self.skill_target_validator(self.character.get_current_skill("ultimate"), battle.current.cur_main_target)
        return info
    
    def provide_ultimate_target(self, character):
        self.character = character
        ultimate = character.get_current_skill("ultimate")
        server.handler.ask_client({"name": "ultimate_target", "target_info": ultimate.target_info}, self.check_ultimate_target)
    
    @server.server_handler
    def character_skill_option_handler(self, message):
        if message.get("type") != "ask" or message.get("name") != "character_skill_option":
            return "invalid_message_type"
        try:
            option = message["option"]
            if option not in self.character.skill_options:
                return "bad_option"
            if "target" in message:
                battle.current.cur_main_target = target.from_uuid(uuid.UUID(message["target"]))
                if battle.current.cur_main_target is None:
                    return "target_not_found"
            else:
                battle.current.cur_main_target = None
            skill_group = self.character.skills[option]
            skill = skill_group.current_skill()
            info = self.skill_target_validator(skill, battle.current.cur_main_target)
            if info != "ok":
                return info
            if not battle.current.skillpoints.available(skill.delta_skillpoints):
                return "not_enough_skillpoints"
            self.selected_skill_group = skill_group
            return "ok"
        except KeyError:
            return "invalid_message"
    
    def provide_character_skill_option(self, character):
        self.character = character
        server.handler.ask_client({"name": "character_skill_option", "target": str(character.uuid)}, self.character_skill_option_handler)
        return self.selected_skill_group
    
    @server.server_handler
    def rate_handler(self, message):
        try:
            if type(message["result"]) is not bool:
                return "invalid_message"
            return "ok"
        except KeyError:
            return "invalid_message"
    
    def provide_random_rate(self):
        response = server.handler.ask_client({"name": "random_rate"}, self.rate_handler)
        return response["result"]
    
    @server.server_handler
    def target_handler(self, message):
        try:
            self.temp_target = target.from_uuid(uuid.UUID(message["result"]))
            if self.temp_target is None:
                return "target_not_found"
            return "ok"
        except KeyError:
            return "invalid_message"
    
    def provide_random_character_target(self):
        response = server.handler.ask_client({"name": "random_character_target"}, self.target_handler)
        return self.temp_target
    
    def provide_random_monster_target(self):
        response = server.handler.ask_client({"name": "random_monster_target"}, self.target_handler)
        return self.temp_target

    @server.server_responder
    @classmethod
    def respond_action_order(cls, message):
        self = battle.current.action_list
        self.refresh_turns()
        extras = [turn.get_info() for turn in self.extras]
        normals = [turn.get_info() | {"num_actions": turn.get_num_actions(), "cur_action": turn.cur_action, "action_value": turn.action_value}
            for turn in self.normals]
        return {"extras": extras, "normals": normals}
    
    @server.server_responder
    @classmethod
    def respond_current_characters(cls, message):
        result = []
        for c in battle.current.characters:
            result.append({"uuid": str(c.uuid), "cur_hp": c.cur_hp, "hp": c.stats["hp"].calculate(), "cur_energy": c.cur_energy,
                "energy": c.stats["energy"].calculate(), "max_energy": c.stats["max_energy"].calculate()})
        return {"characters": result}

    @server.server_responder
    @classmethod
    def respond_current_monsters(self, message):
        result = []
        for m in battle.current.monsters:
            result.append({"uuid": str(m.uuid), "cur_hp": m.cur_hp, "hp": m.stats["hp"].calculate(), "cur_toughness": m.cur_toughness,
                "toughness": m.stats["toughness"].calculate()})
        return {"monsters": result}
    
    @server.server_responder
    @classmethod
    def respond_character_skill_options(cls, message):
        t = target.from_uuid(uuid.UUID(message["target"]))
        result = {}
        for option in t.skill_options:
            skill = t.skills[option].current_skill()
            result[option] = {
                "name": skill.nameid,
                "target_info": skill.target_info
            }
        return {"options": result}
