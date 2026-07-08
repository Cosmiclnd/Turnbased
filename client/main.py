import websockets.sync.client as websockets
from websockets import ConnectionClosedOK
import asyncio
import json
import rich

import config

console = rich.get_console()

class Target:
    def __init__(self, uuid, nameid, is_character):
        self.uuid = uuid
        self.nameid = nameid
        self.is_character = is_character
        self.config = config.load_config_data("characters" if is_character else "monsters", nameid)

class UpdateHandler:
    def __init__(self, client):        
        self.client = client
    
    def handle(self, message):
        words = message["name"].split(".")
        method = getattr(self, "handle_" + words[0])
        return method(message, *words[1:])
    
    def handle_new_wave(self, message):
        console.print(f"*** Wave {message['wave']}/{message['total']}", style="bold yellow")
        return {"type": "empty"}
    
    def handle_normal_turn_start(self, message):
        console.print(f"Normal Turn: {self.client.targets[message['target']].nameid}", style="bold blue")
        return {"type": "empty"}
    
    def handle_ultimate_turn(self, message):
        console.print(f"Ultimate Turn: {self.client.targets[message['target']].nameid}", style="bold blue")
        return {"type": "empty"}
    
    def handle_skill_trigger(self, message):
        console.print(f"{self.client.targets[message['target']].nameid} triggered skill", style="#6055f0", end=" ")
        console.print(message['skill'], style="italic #6055f0")
        return {"type": "empty"}
    
    def handle_damage(self, message):
        info = (f"{self.client.targets[message['dealer']].nameid} deals {round(message['damage']['amount'], 2)} damage to " +
            f"{self.client.targets[message['target']].nameid}")
        if message["damage"]["crit"]:
            info += " CRIT!"
        if "break" in message["damage"]["types"]:
            info += " Break!"
        console.print(info, style="#f0806f")
        return {"type": "empty"}
    
    def handle_heal(self, message):
        info = (f"{self.client.targets[message['healer']].nameid} heals {round(message['amount'], 2)} HP to " +
            f"{self.client.targets[message['target']].nameid}")
        console.print(info, style="#6ff076")
        return {"type": "empty"}
    
    def handle_reduce_toughness(self, message):
        return {"type": "empty"}
    
    def handle_action_advance(self, message):
        console.print(f"{self.client.targets[message['target']].nameid}'s action is advanced by {message['scale']}", style="yellow")
        return {"type": "empty"}
    
    def handle_action_delay(self, message):
        console.print(f"{self.client.targets[message['target']].nameid}'s action is delayed by {round(100 * message['scale'], 2)}%", style="yellow")
        return {"type": "empty"}
    
    def handle_add_effect(self, message):
        console.print(f"{self.client.targets[message['target']].nameid} is affected by", style="#90d050", end=" ")
        console.print(f"{message['effect']}", style="italic #90d050")
        return {"type": "empty"}
    
    def handle_weakness_break(self, message):
        console.print(f"{self.client.targets[message['target']].nameid}'s weakness is broken", style="#f08080")
        return {"type": "empty"}
    
    def handle_die(self, message):
        console.print(f"{self.client.targets[message['target']].nameid} dies", style="bold red")
        return {"type": "empty"}
    
    def handle_battle_lose(self, message):
        console.print("Battle Lose!", style="bold red")
        return {"type": "empty"}
    
    def handle_battle_win(self, message):
        console.print("Battle Win!", style="bold green")
        return {"type": "empty"}
    
    def handle_herta(self, message, *args):
        if args[0] == "follow_up_turn":
            console.print(f"Follow-Up Attack: {self.client.targets[message['target']].nameid}", style="bold blue")
        return {"type": "empty"}

class AskHandler:
    def __init__(self, client):
        self.client = client
    
    def handle(self, message):
        method = getattr(self, "handle_" + message["name"])
        return method(message)
    
    def handle_ultimate(self, message):
        if message["info"] is not None:
            console.print(f"Error: {message['info']}", style="bold red")
        characters = self.print_current_characters()
        raw = input("ultimate> ")
        if not raw:
            return {"type": "empty"}
        return {"type": "ask", "name": "ultimate", "character": characters[int(raw)]["uuid"]}
    
    def handle_character_skill_option(self, message):
        if message["info"] is not None:
            console.print(f"Error: {message['info']}", style="bold red")
        options = self.client.query({"name": "character_skill_options", "target": message["target"]})["options"]
        target_lists = {}
        for option, skill in options.items():
            console.print(f"\\[{option}] {skill['name']}", style="#d037f4")
            if skill["target_info"]["type"] == "character":
                target_lists[option] = self.print_current_characters()
            elif skill["target_info"]["type"] == "monster":
                target_lists[option] = self.print_current_monsters()
        option = ""
        target = None
        while not option:
            raw = input("option> ")
            words = raw.strip().lower().split()
            if not words:
                continue
            option = words[0]
            if option == "q":
                option = "basic_atk"
            elif option == "e":
                option = "skill"
            if option not in target_lists:
                console.print(f"Invalid option: {option}", style="bold red")
                continue
            if len(words) > 1:
                idx = int(words[1])
                target = target_lists[option][idx]["uuid"]
        response = {"type": "ask", "name": "character_skill_option", "option": option}
        if target is not None:
            response["target"] = target
        return response
    
    def print_current_characters(self):
        result = self.client.query({"name": "current_characters"})
        characters = result["characters"]
        for i, character in enumerate(characters):
            console.print(f"\\[{i}] {self.client.targets[character['uuid']].nameid}"
                f"HP: {round(character['cur_hp'], 2)}/{round(character['hp'], 2)} "
                f"Energy: {round(character['cur_energy'], 2)}/{round(character['max_energy'], 2)}", style="#a0a0a0")
        return characters
    
    def print_current_monsters(self):
        result = self.client.query({"name": "current_monsters"})
        monsters = result["monsters"]
        for i, monster in enumerate(monsters):
            console.print(f"\\[{i}] {self.client.targets[monster['uuid']].nameid}"
                f"HP: {round(monster['cur_hp'], 2)}/{round(monster['hp'], 2)} "
                f"Toughness: {round(monster['cur_toughness'], 2)}/{round(monster['toughness'], 2)}", style="#a0a0a0")
        return monsters

class Client:
    def __init__(self, url):
        self.url = url
        self.targets = {}
        self.update_handler = UpdateHandler(self)
        self.ask_handler = AskHandler(self)
        self.websocket = None
    
    def send_message(self, message):
        self.websocket.send(json.dumps(message))
    
    def query(self, message):
        message["type"] = "query"
        self.send_message(message)
        return json.loads(self.websocket.recv())
    
    def collect_targets(self, config):
        for record in config["characters"]:
            self.targets[record["uuid"]] = Target(record["uuid"], record["name"], True)
        for wave in config["monsters"]:
            for group_name, group in wave.items():
                for record in group["monsters"]:
                    self.targets[record["uuid"]] = Target(record["uuid"], record["name"], False)

    def start(self, config):
        with websockets.connect(self.url) as websocket:
            self.websocket = websocket
            self.send_message({"type": "init_battle"})
            self.collect_targets(config)
            self.send_message({"type": "setup_monsters", "record": config["monsters"]})
            for record in config["characters"]:
                self.send_message({"type": "add_character", "record": record})
            for name, state in config["initial_state"].items():
                self.send_message({"type": "set_initial_state", "target": name, "state": state})
            for name in config["techniques"]:
                self.send_message({"type": "use_technique", "target": name})
            self.send_message({"type": "setup_random", "config": {"use_random": True}})
            self.send_message({"type": "set_battle_config", "config": config["battle_config"]})
            self.send_message({"type": "start_battle"})
            while True:
                message = json.loads(self.websocket.recv())
                response = None
                if message["type"] == "update":
                    response = self.update_handler.handle(message)
                elif message["type"] == "ask":
                    response = self.ask_handler.handle(message)
                if response is not None:
                    self.send_message(response)
                else:
                    self.send_message({"type": "empty"})

client = Client("ws://localhost:55716")
with open("client/userdata/config.json", "r", encoding="utf-8") as f:
    try:
        client.start(json.load(f))
    except ConnectionClosedOK:
        pass
