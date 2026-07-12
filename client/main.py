import websockets.sync.client as websockets
from websockets import ConnectionClosedOK
import asyncio
import json
import msgpack

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
import keyboard

import config

console = Console()
live = Live(console, auto_refresh=False)
layout = Layout()
action_order = Text()
battle_log = Text()
input_text = ""
inputing = False

def refresh_screen():
    layout.split_row(
        Layout(Panel(action_order, title="Action Order"), size=50),
        Layout(Panel(battle_log + input_text, title="Battle Log"), ratio=1),
    )
    live.update(layout, refresh=True)

def print_battle_log(str, style=None, end="\n"):
    global battle_log
    battle_log.append(console.render_str(f"[{style}]{str}[/]" if style else str))
    if end is not None:
        battle_log.append(end)
    lines = battle_log.split(allow_blank=True)
    max_lines = 50
    if len(lines) > max_lines:
        battle_log = Text("\n").join(lines[-max_lines:])
    refresh_screen()

def on_key_press(event):
    global input_text
    if inputing:
        if event.name == "backspace":
            input_text = input_text[:-1]
            refresh_screen()
            return
        text = None
        if len(event.name) == 1:
            text = event.name
        elif event.name == "space":
            text = " "
        if text is not None:
            input_text += text
            refresh_screen()
keyboard.on_press(on_key_press)

def input(prompt=""):
    global inputing, input_text
    print_battle_log(prompt, end=None)
    inputing = True
    keyboard.wait("enter")
    inputing = False
    print_battle_log(input_text)
    result = input_text
    input_text = ""
    return result

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
        print_battle_log(f"*** Wave {message['wave']}/{message['total']} ***", style="bold yellow")
        return {"type": "empty"}
    
    def handle_normal_turn_start(self, message):
        self.on_new_turn(f"Normal Turn: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_extra_normal_turn(self, message):
        self.on_new_turn(f"Extra Normal Turn: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_ultimate_turn(self, message):
        self.on_new_turn(f"Ultimate Turn: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_skill_trigger(self, message):
        print_battle_log(f"{self.client.targets[message['target']].nameid} triggered skill", style="#6055f0", end=" ")
        print_battle_log(message['skill'], style="italic #6055f0")
        return {"type": "empty"}
    
    def handle_damage(self, message):
        info = (f"{self.client.targets[message['dealer']].nameid} deals {round(message['damage']['amount'], 2)} damage to " +
            f"{self.client.targets[message['target']].nameid}")
        if message["damage"]["crit"]:
            info += " CRIT!"
        if "break" in message["damage"]["types"]:
            info += " Break!"
        if "super_break" in message["damage"]["types"]:
            info += " Super Break!"
        print_battle_log(info, style="#f0806f")
        return {"type": "empty"}
    
    def handle_heal(self, message):
        info = (f"{self.client.targets[message['healer']].nameid} heals {round(message['amount'], 2)} HP to " +
            f"{self.client.targets[message['target']].nameid}")
        print_battle_log(info, style="#6ff076")
        return {"type": "empty"}
    
    def handle_reduce_toughness(self, message):
        return {"type": "empty"}
    
    def handle_action_advance(self, message):
        if "target" in message["turn"]:
            name = f"{self.client.targets[message['turn']['target']].nameid}'s action"
        else:
            name = message['turn']['name']
        print_battle_log(f"{name} is advanced by {round(100 * message['scale'], 2)}%", style="yellow")
        return {"type": "empty"}
    
    def handle_action_delay(self, message):
        if "target" in message["turn"]:
            name = f"{self.client.targets[message['turn']['target']].nameid}'s action"
        else:
            name = message['turn']['name']
        print_battle_log(f"{name} is delayed by {round(100 * message['scale'], 2)}%", style="yellow")
        return {"type": "empty"}
    
    def handle_add_effect(self, message):
        print_battle_log(f"{self.client.targets[message['target']].nameid} is affected by", style="#90d050", end=" ")
        print_battle_log(f"{message['effect']}", style="italic #90d050")
        return {"type": "empty"}
    
    def handle_weakness_break(self, message):
        print_battle_log(f"{self.client.targets[message['target']].nameid}'s weakness is broken", style="#f08080")
        return {"type": "empty"}
    
    def handle_die(self, message):
        print_battle_log(f"{self.client.targets[message['target']].nameid} dies", style="bold red")
        return {"type": "empty"}
    
    def handle_battle_lose(self, message):
        print_battle_log("Battle Lose!", style="bold red")
        return {"type": "empty"}
    
    def handle_battle_win(self, message):
        print_battle_log("Battle Win!", style="bold green")
        return {"type": "empty"}
    
    def handle_firefly(self, message, *args):
        if args[0] == "complete_combustion_countdown":
            self.on_new_turn(f"Complete Combustion Countdown: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_herta(self, message, *args):
        if args[0] == "follow_up_turn":
            self.on_new_turn(f"Follow-Up Attack: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_ruan_mei(self, message, *args):
        if args[0] == "technique_turn":
            self.on_new_turn(f"Technique Turn: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def on_new_turn(self, info):
        print_battle_log(f"> {info} <", style="bold blue")
    
    def update_action_order(self):
        global action_order
        action_order = Text()
        ao = self.client.query({"name": "action_order"})
        for extra in ao["extras"]:
            action_order.append(f"{extra['name']} <extra>\n")
        for normal in ao["normals"]:
            action_order.append(f"{normal['name']} | {round(normal['action_value'], 2)}\n")
        refresh_screen()

class AskHandler:
    def __init__(self, client):
        self.client = client
    
    def handle(self, message):
        method = getattr(self, "handle_" + message["name"])
        return method(message)
    
    def handle_ultimate(self, message):
        if message["info"] is not None:
            print_battle_log(f"Error: {message['info']}", style="bold red")
        characters = self.print_current_characters(lambda c: c["cur_energy"] >= c["energy"])
        if not characters:
            return {"type": "empty"}
        while True:
            raw = input("ultimate> ").strip()
            if not raw:
                return {"type": "empty"}
            try:
                return {"type": "ask", "name": "ultimate", "character": characters[int(raw)]["uuid"]}
            except (ValueError, IndexError):
                print_battle_log(f"Invalid index: {raw}", style="bold red")
    
    def handle_ultimate_target(self, message):
        if message["info"] is not None:
            print_battle_log(f"Error: {message['info']}", style="bold red")
        if message["target_info"]["type"] == "character":
            target_list = self.print_current_characters()
        elif message["target_info"]["type"] == "monster":
            target_list = self.print_current_monsters()
        response = {"type": "ask", "name": "ultimate_target"}
        while True:
            raw = input("target> ").strip()
            if raw:
                try:
                    response["target"] = target_list[int(raw)]["uuid"]
                except (ValueError, IndexError):
                    print_battle_log(f"Invalid index: {raw}", style="bold red")
                    continue
            break
        return response
    
    def handle_character_skill_option(self, message):
        if message["info"] is not None:
            print_battle_log(f"Error: {message['info']}", style="bold red")
        options = self.client.query({"name": "character_skill_options", "target": message["target"]})["options"]
        target_lists = {}
        for option, skill in options.items():
            print_battle_log(f"\\[{option}] {skill['name']}", style="#d037f4")
            if skill["target_info"]["type"] == "character":
                target_lists[option] = self.print_current_characters()
            elif skill["target_info"]["type"] == "monster":
                target_lists[option] = self.print_current_monsters()
        option = ""
        target = None
        while True:
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
                print_battle_log(f"Invalid option: {option}", style="bold red")
                continue
            if len(words) == 2:
                try:
                    idx = int(words[1])
                    target = target_lists[option][idx]["uuid"]
                except (ValueError, IndexError):
                    print_battle_log(f"Invalid index: {words[1]}", style="bold red")
                    continue
            break
        response = {"type": "ask", "name": "character_skill_option", "option": option}
        if target is not None:
            response["target"] = target
        return response
    
    def print_current_characters(self, filter=None):
        result = self.client.query({"name": "current_characters"})
        characters = [c for c in result["characters"] if filter is None or filter(c)]
        for i, character in enumerate(characters):
            print_battle_log(f"\\[{i}] {self.client.targets[character['uuid']].nameid} "
                f"HP: {round(character['cur_hp'], 2)}/{round(character['hp'], 2)} "
                f"Energy: {round(character['cur_energy'], 2)}/{round(character['max_energy'], 2)}", style="#a0a0a0")
        return characters
    
    def print_current_monsters(self, filter=None):
        result = self.client.query({"name": "current_monsters"})
        monsters = [m for m in result["monsters"] if filter is None or filter(m)]
        for i, monster in enumerate(monsters):
            print_battle_log(f"\\[{i}] {self.client.targets[monster['uuid']].nameid} "
                f"HP: {round(monster['cur_hp'], 2)}/{round(monster['hp'], 2)} "
                f"Toughness: {round(monster['cur_toughness'], 2)}/{round(monster['toughness'], 2)}", style="#a0a0a0")
        return monsters

class InbattleMessageHandler:
    def __init__(self, websocket):
        self.websocket = websocket
        self.updates = []
        self.response = None
    
    def recv_message(self, query=False):
        if not query and self.updates:
            return self.updates.pop(0)
        message = msgpack.unpackb(self.websocket.recv())
        if message["type"] == "updates":
            self.updates = message["updates"]
            return self.updates.pop(0)
        else:
            return message
    
    def respond(self, message, query=False):
        if query:
            self.websocket.send(msgpack.packb(message))
            return
        self.response = self.response or message
        if not self.updates:
            self.websocket.send(msgpack.packb(self.response or {"type": "empty"}))
            self.response = None

class Client:
    def __init__(self, url):
        self.url = url
        self.targets = {}
        self.update_handler = UpdateHandler(self)
        self.ask_handler = AskHandler(self)
        self.websocket = None
    
    def send_message(self, message):
        self.websocket.send(msgpack.packb(message))
    
    def query(self, message):
        message["type"] = "query"
        self.handler.respond(message, True)
        return self.handler.recv_message(True)
    
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
            for feature in config["features"]:
                self.send_message({"type": "use_feature", "feature": feature})
            self.send_message({"type": "start_battle"})
            self.handler = InbattleMessageHandler(websocket)
            while True:
                message = self.handler.recv_message()
                self.update_handler.update_action_order()
                response = None
                if message["type"] == "update":
                    self.handler.respond(self.update_handler.handle(message))
                elif message["type"] == "ask":
                    self.handler.respond(self.ask_handler.handle(message))

live.start()
client = Client("ws://localhost:55716")
with open("client/userdata/config.json", "r", encoding="utf-8") as f:
    try:
        client.start(json.load(f))
    except ConnectionClosedOK:
        pass
    finally:
        live.stop()
