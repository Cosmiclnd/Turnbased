import websockets.sync.client as websockets
from websockets import ConnectionClosedOK
import json
import msgpack
import sys
import time

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal

import config

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
        self.client.print_battle_log(f"*** Wave {message['wave']}/{message['total']} ***", color="#f8f045", bold=True)
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
        self.client.print_battle_log(f"{self.client.targets[message['target']].nameid} triggered skill", color="#6055f0", end=" ")
        self.client.print_battle_log(message['skill'], color="#6055f0", italic=True)
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
        if "dot" in message["damage"]["types"]:
            info += " DoT"
        self.client.print_battle_log(info, color="#f0806f")
        return {"type": "empty"}
    
    def handle_heal(self, message):
        info = (f"{self.client.targets[message['healer']].nameid} heals {round(message['amount'], 2)} HP to " +
            f"{self.client.targets[message['target']].nameid}")
        self.client.print_battle_log(info, color="#6ff076")
        return {"type": "empty"}
    
    def handle_reduce_toughness(self, message):
        return {"type": "empty"}
    
    def handle_action_advance(self, message):
        if "target" in message["turn"]:
            name = f"{self.client.targets[message['turn']['target']].nameid}'s action"
        else:
            name = message['turn']['name']
        self.client.print_battle_log(f"{name} is advanced by {round(100 * message['scale'], 2)}%", color="yellow")
        return {"type": "empty"}
    
    def handle_action_delay(self, message):
        if "target" in message["turn"]:
            name = f"{self.client.targets[message['turn']['target']].nameid}'s action"
        else:
            name = message['turn']['name']
        self.client.print_battle_log(f"{name} is delayed by {round(100 * message['scale'], 2)}%", color="yellow")
        return {"type": "empty"}
    
    def handle_add_effect(self, message):
        self.client.print_battle_log(f"{self.client.targets[message['target']].nameid} is affected by", color="#90d050", end=" ")
        self.client.print_battle_log(f"{message['effect']}", color="#90d050", italic=True)
        return {"type": "empty"}
    
    def handle_weakness_break(self, message):
        self.client.print_battle_log(f"{self.client.targets[message['target']].nameid}'s weakness is broken", color="#f08080")
        return {"type": "empty"}
    
    def handle_die(self, message):
        self.client.print_battle_log(f"{self.client.targets[message['target']].nameid} dies", color="red", bold=True)
        return {"type": "empty"}
    
    def handle_battle_lose(self, message):
        self.client.print_battle_log("Battle Lose!", color="red", bold=True)
        return {"type": "empty"}
    
    def handle_battle_win(self, message):
        self.client.print_battle_log("Battle Win!", color="green", bold=True)
        return {"type": "empty"}
    
    def handle_firefly(self, message, *args):
        if args[0] == "complete_combustion_countdown":
            self.on_new_turn(f"Complete Combustion Countdown: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_herta(self, message, *args):
        if args[0] == "follow_up_turn":
            self.on_new_turn(f"Follow-Up Attack: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_kafka(self, message, *args):
        if args[0] == "follow_up_turn":
            self.on_new_turn(f"Follow-Up Attack: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def handle_ruan_mei(self, message, *args):
        if args[0] == "technique_turn":
            self.on_new_turn(f"Technique Turn: {self.client.targets[message['target']].nameid}")
        return {"type": "empty"}
    
    def on_new_turn(self, info):
        self.client.print_battle_log(f"&gt; {info} &lt;", color="#a0a4f5", bold=True)
    
    def update_action_order(self):
        ao = self.client.query({"name": "action_order"})
        lines = []
        for extra in ao["extras"]:
            lines.append(f"{extra['name']} <extra>")
        for normal in ao["normals"]:
            lines.append(f"{normal['name']} | {round(normal['action_value'], 2)}")
        self.client.update_action_order_text.emit("\n".join(lines))

class AskHandler:
    def __init__(self, client):
        self.client = client
        self.input_prompt = None
        self.input_func = None
    
    def setup_input(self, prompt, func):
        self.input_prompt = prompt
        self.input_func = func
        if prompt is not None:
            self.client.print_battle_log(prompt, color="white", end=None)
        self.client.set_input_state.emit(prompt is not None)
    
    def handle(self, message):
        method = getattr(self, "handle_" + message["name"])
        method(message)
    
    def handle_ultimate(self, message):
        if message["info"] is not None:
            self.client.print_battle_log(f"Error: {message['info']}", color="red", bold=True)
        characters = self.print_current_characters(lambda c: c["cur_energy"] >= c["energy"])
        if not characters:
            return
        def func(raw):
            raw = raw.strip()
            if not raw:
                self.setup_input(None, None)
                return
            try:
                response = {"type": "ask", "name": "ultimate", "character": characters[int(raw)]["uuid"]}
                self.setup_input(None, None)
                return response
            except (ValueError, IndexError):
                self.client.print_battle_log(f"Invalid index: {raw}", color="red", bold=True)
                self.setup_input("ultimate> ", func)
                return
        self.setup_input("ultimate> ", func)
    
    def handle_ultimate_target(self, message):
        if message["info"] is not None:
            self.client.print_battle_log(f"Error: {message['info']}", color="red", bold=True)
        if message["target_info"]["type"] == "character":
            target_list = self.print_current_characters()
        elif message["target_info"]["type"] == "monster":
            target_list = self.print_current_monsters()
        def func(raw):
            raw = raw.strip()
            response = {"type": "ask", "name": "ultimate_target"}
            if raw:
                try:
                    response["target"] = target_list[int(raw)]["uuid"]
                except (ValueError, IndexError):
                    self.client.print_battle_log(f"Invalid index: {raw}", color="red", bold=True)
                    self.setup_input("target> ", func)
                    return
            self.setup_input(None, None)
            return response
        self.setup_input("target> ", func)
    
    def handle_character_skill_option(self, message):
        if message["info"] is not None:
            self.client.print_battle_log(f"Error: {message['info']}", color="red", bold=True)
        options = self.client.query({"name": "character_skill_options", "target": message["target"]})["options"]
        target_lists = {}
        for option, skill in options.items():
            if option == "basic_atk":
                option_info = "basic_atk/q"
            elif option == "skill":
                option_info = "skill/e"
            else:
                option_info = option
            self.client.print_battle_log(f"[{option_info}] {skill['name']}", color="#d037f4")
            if skill["target_info"]["type"] == "character":
                target_lists[option] = self.print_current_characters()
            elif skill["target_info"]["type"] == "monster":
                target_lists[option] = self.print_current_monsters()
        def func(raw):
            words = raw.strip().lower().split()
            if not words:
                self.setup_input("option> ", func)
                return
            option = words[0]
            if option == "q":
                option = "basic_atk"
            elif option == "e":
                option = "skill"
            if option not in target_lists:
                self.client.print_battle_log(f"Invalid option: {option}", color="red", bold=True)
                self.setup_input("option> ", func)
                return
            target = None
            if len(words) == 2:
                try:
                    idx = int(words[1])
                    target = target_lists[option][idx]["uuid"]
                except (ValueError, IndexError):
                    self.client.print_battle_log(f"Invalid index: {words[1]}", color="red", bold=True)
                    self.setup_input("option> ", func)
                    return
            self.setup_input(None, None)
            response = {"type": "ask", "name": "character_skill_option", "option": option}
            if target is not None:
                response["target"] = target
            return response
        self.setup_input("option> ", func)
    
    def print_current_characters(self, filter=None):
        result = self.client.query({"name": "current_characters"})
        characters = [c for c in result["characters"] if filter is None or filter(c)]
        for i, character in enumerate(characters):
            self.client.print_battle_log(f"[{i}] {self.client.targets[character['uuid']].nameid} "
                f"HP: {round(character['cur_hp'], 2)}/{round(character['hp'], 2)} "
                f"Energy: {round(character['cur_energy'], 2)}/{round(character['max_energy'], 2)}", color="#a0a0a0")
        return characters
    
    def print_current_monsters(self, filter=None):
        result = self.client.query({"name": "current_monsters"})
        monsters = [m for m in result["monsters"] if filter is None or filter(m)]
        for i, monster in enumerate(monsters):
            self.client.print_battle_log(f"[{i}] {self.client.targets[monster['uuid']].nameid} "
                f"HP: {round(monster['cur_hp'], 2)}/{round(monster['hp'], 2)} "
                f"Toughness: {round(monster['cur_toughness'], 2)}/{round(monster['toughness'], 2)}", color="#a0a0a0")
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

class Client(QThread):
    update_action_order_text = pyqtSignal(str)
    append_battle_log = pyqtSignal(str)
    set_input_state = pyqtSignal(bool)

    def __init__(self, url):
        super().__init__()
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

    def run(self):
        with open("client/userdata/config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
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
                if self.ask_handler.input_prompt is None:
                    try:
                        message = self.handler.recv_message()
                    except ConnectionClosedOK:
                        break
                    self.update_handler.update_action_order()
                    response = None
                    if message["type"] == "update":
                        self.handler.respond(self.update_handler.handle(message))
                    elif message["type"] == "ask":
                        response = self.ask_handler.handle(message)
                        if self.ask_handler.input_prompt is None:
                            self.handler.respond(response)
                else:
                    time.sleep(0.0001)
    
    def print_battle_log(self, text, color, bold=False, italic=False, end="<br>"):
        text += end or ""
        if bold:
            text = f"<b style=\"color: {color};\">{text}</b>"
        elif italic:
            text = f"<i style=\"color: {color};\">{text}</i>"
        else:
            text = f"<span style=\"color: {color};\">{text}</span>"
        self.append_battle_log.emit(text)
    
    def submit_input(self, text):
        response = self.ask_handler.input_func(text)
        if self.ask_handler.input_prompt is None:
            self.handler.respond(response)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Turnbased Battle Client")
        self.setGeometry(100, 100, 1200, 900)
        self.showMaximized()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)

        self.action_order_text = QTextEdit()
        self.action_order_text.setReadOnly(True)
        self.action_order_text.setLineWrapMode(QTextEdit.NoWrap)
        self.action_order_text.setMaximumWidth(500)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)

        self.log = []
        self.log_text = QTextEdit()
        palette = self.log_text.palette()
        palette.setColor(QPalette.Base, QColor(20, 20, 20))
        self.log_text.setPalette(palette)
        font = self.log_text.font()
        font.setPointSize(12)
        self.log_text.setFont(font)
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)

        self.input_line = QLineEdit()
        self.input_line.returnPressed.connect(self.submit_input)
        self.input_line.setEnabled(False)

        right_layout.addWidget(self.log_text)
        right_layout.addWidget(self.input_line)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.action_order_text)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)
        
        self.client = Client("ws://localhost:55716")
        self.client.update_action_order_text.connect(self.update_action_order_text)
        self.client.append_battle_log.connect(self.append_battle_log)
        self.client.set_input_state.connect(self.set_input_state)
        self.client.start()
    
    def update_action_order_text(self, text):
        self.action_order_text.setText(text)
    
    def append_battle_log(self, text):
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(text)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()
    
    def set_input_state(self, state):
        self.input_line.setEnabled(state)
        if state:
            self.input_line.setPlaceholderText(self.client.ask_handler.input_prompt)
        else:
            self.input_line.setPlaceholderText("")
        self.input_line.setFocus()
    
    def submit_input(self):
        text = self.input_line.text()
        self.input_line.setText("")
        self.append_battle_log(f"<span style=\"color: white;\">{text}</span><br>")
        self.client.submit_input(text)

app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec_())
