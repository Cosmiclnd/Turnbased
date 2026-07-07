from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt
import asyncio
import json
import copy
import uuid

import client
import record
import config

element_names = {
    "physical": "Physical",
    "fire": "Fire",
    "ice": "Ice",
    "lightning": "Lightning",
    "wind": "Wind",
    "quantum": "Quantum",
    "imaginary": "Imaginary"
}
path_names = {
    "destruction": "Destruction",
    "the_hunt": "The Hunt",
    "erudition": "Erudition",
    "harmony": "Harmony",
    "nihility": "Nihility",
    "preservation": "Preservation",
    "abundance": "Abundance"
}
stat_names = {
    "spd": "SPD",
    "hp": "HP",
    "atk": "ATK",
    "def": "DEF",
    "hp%": "HP%",
    "atk%": "ATK%",
    "def%": "DEF%",
    "crt_rate": "CRIT Rate",
    "crt_dmg": "CRIT DMG",
    "break_eff": "Break Effect",
    "eff_hr": "Effect Hit Rate",
    "eff_res": "Effect RES",
    "energy_regen_rate": "Energy Regeneration Rate",
    "outgoing_healing_boost": "Outgoing Healing Boost",
    "physical_dmg_boost": "Physical DMG Boost",
    "fire_dmg_boost": "Fire DMG Boost",
    "ice_dmg_boost": "Ice DMG Boost",
    "lightning_dmg_boost": "Lightning DMG Boost",
    "wind_dmg_boost": "Wind DMG Boost",
    "quantum_dmg_boost": "Quantum DMG Boost",
    "imaginary_dmg_boost": "Imaginary DMG Boost"
}

class ChooseHostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Choose Host And Port")
        self.setModal(True)
        self.setFixedSize(400, 200)

        layout = QVBoxLayout(self)

        line1 = QHBoxLayout()
        host_label = QLabel("Host:")
        self.host_input = QLineEdit()
        self.host_input.setText("localhost")
        line1.addWidget(host_label)
        line1.addWidget(self.host_input)
        layout.addLayout(line1)

        line2 = QHBoxLayout()
        port_label = QLabel("Port:")
        self.port_input = QLineEdit()
        self.port_input.setText("55716")
        line2.addWidget(port_label)
        line2.addWidget(self.port_input)
        layout.addLayout(line2)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

class SetupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Setup")
        self.resize(1200, 800)
        self.showMaximized()

        self.character_tab = QWidget()
        self.monster_tab = QWidget()
        self.battle_tab = QWidget()

        self.init_characters()
        self.init_monsters()
        self.init_battle()

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        tab = QTabWidget()
        tab.addTab(self.character_tab, "Characters")
        tab.addTab(self.monster_tab, "Monsters")
        tab.addTab(self.battle_tab, "Battle Config")

        layout.addWidget(tab)
    
    def init_characters(self):
        layout = QVBoxLayout(self.character_tab)

        uid_line = QHBoxLayout()
        uid_label = QLabel("UID:")
        self.uid_input = QLineEdit()
        self.uid_btn = QPushButton("Fetch")
        self.uid_btn.clicked.connect(self.on_uid_btn)
        uid_line.addWidget(uid_label)
        uid_line.addWidget(self.uid_input)
        uid_line.addWidget(self.uid_btn)
        layout.addLayout(uid_line)

        self.character_frames = QHBoxLayout()
        layout.addLayout(self.character_frames)

        self.character_ok_btn = QPushButton("Save")
        self.character_ok_btn.clicked.connect(self.on_character_ok_btn)
        layout.addWidget(self.character_ok_btn)
        self.character_records = None
        
        layout.addStretch()
    
    def init_monsters(self):
        pass
    
    def init_battle(self):
        layout = QVBoxLayout(self.battle_tab)

        self.lineup_list = QListWidget()
        self.lineup_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.lineup_list.setDragDropMode(QAbstractItemView.InternalMove)
        layout.addWidget(self.lineup_list)

        self.lineup_ok_btn = QPushButton("OK")
        self.lineup_ok_btn.clicked.connect(self.on_lineup_ok_btn)
        layout.addWidget(self.lineup_ok_btn)

        layout.addStretch()
    
    def on_uid_btn(self):
        uid = self.uid_input.text()
        try:
            self.character_records = list(filter(None, asyncio.run(record.fetch_record(int(uid)))))
            if not self.character_records:
                return
            self.refresh_character_frames()
        except Exception as e:
            print("Error:", e)
            raise  # TODO: debug
    
    def refresh_character_frames(self):
        while not self.character_frames.isEmpty():
            child = self.character_frames.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for record in self.character_records:
            frame = self.get_character_frame(record)
            self.character_frames.addWidget(frame)
        self.character_frames.addStretch()
    
    def get_character_frame(self, record):
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box | QFrame.Raised)

        layout = QVBoxLayout(frame)

        title_font = QFont()
        title_font.setBold(True)
        config_data = config.load_config_data("characters", record["name"])
        name_label = QLabel(config_data["name"] + f" ({record['name']}) Lv.{record['level']} E{record['eidolons']}")
        name_label.setFont(title_font)
        info_label = QLabel(f"✦{config_data['rarity']} {path_names[config_data['path']]} - {element_names[config_data['element']]}")
        layout.addWidget(name_label)
        layout.addWidget(info_label)

        if record["lightcone"]:
            lightcone_frame = QFrame()
            lightcone_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
            lightcone_layout = QVBoxLayout(lightcone_frame)
            config_data = config.load_config_data("lightcones", record["lightcone"]["name"])
            name_label = QLabel(config_data["name"] + f" Lv.{record['lightcone']['level']} S{record['lightcone']['stacks']}")
            name_label.setFont(title_font)
            info_label = QLabel(f"✦{config_data['rarity']} {path_names[config_data['path']]}")
            lightcone_layout.addWidget(name_label)
            lightcone_layout.addWidget(info_label)
            layout.addWidget(lightcone_frame)
        
        sub_font = QFont()
        sub_font.setPixelSize(16)
        for type, relic in record.get("relics", {}).items():
            relic_frame = QFrame()
            relic_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
            relic_layout = QVBoxLayout(relic_frame)
            config_data = config.load_config_data("relics", relic["name"])
            name_label = QLabel(config_data["name"] + f" Lv.{relic['level']}")
            name_label.setFont(title_font)
            main_label = QLabel(stat_names[relic["main_stat_type"]])
            relic_layout.addWidget(name_label)
            relic_layout.addWidget(main_label)
            for sub_stat, enhancement in zip(relic["sub_stat_types"], relic["enhancements"]):
                count = len(enhancement)
                steps = sum(enhancement)
                sub_layout = QHBoxLayout()
                sub_name = QLabel(stat_names[sub_stat])
                sub_name.setFont(sub_font)
                sub_enhancement = QLabel(f"{count} +{steps}")
                sub_enhancement.setFont(sub_font)
                sub_enhancement.setAlignment(Qt.AlignRight)
                sub_layout.addWidget(sub_name)
                sub_layout.addWidget(sub_enhancement)
                relic_layout.addLayout(sub_layout)
            layout.addWidget(relic_frame)
        
        layout.addStretch()
        return frame
    
    def on_character_ok_btn(self):
        if self.character_records:
            with open("client/userdata/characters.json", "w", encoding="utf-8") as f:
                json.dump(self.character_records, f, indent=4)
            self.lineup_list.clear()
            for r in self.character_records:
                self.lineup_list.addItem(r["name"])
        
    def on_lineup_ok_btn(self):
        config = {
            "characters": []
        }
        for item in self.lineup_list.selectedItems():
            for record in self.character_records:
                if record["name"] == item.text():
                    record = copy.copy(record)
                    break
            record["uuid"] = str(uuid.uuid4())
            config["characters"].append(record)
        with open("client/userdata/config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

        self.client = client.Client()
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
    
    def init_ui(self):
        self.setWindowTitle("Turnbased Client")
        self.resize(1200, 800)
        self.showMaximized()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        tool_bar = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.on_connect_btn)
        tool_bar.addWidget(self.connect_btn)
        self.setup_btn = QPushButton("Setup")
        #self.setup_btn.setEnabled(False)
        self.setup_btn.clicked.connect(self.on_setup_btn)
        tool_bar.addWidget(self.setup_btn)
        self.start_btn = QPushButton("Start")
        self.start_btn.setEnabled(False)
        tool_bar.addWidget(self.start_btn)
        tool_bar.addStretch()
        main_layout.addLayout(tool_bar)

        main_layout.addStretch()

    def on_connect_btn(self):
        dialog = ChooseHostDialog(self)
        try:
            if dialog.exec_() == QDialog.Accepted:
                self.client.connect_to_server(dialog.host_input.text(), int(dialog.port_input.text()))
        except Exception as e:
            messagebox = QMessageBox(self)
            messagebox.critical(self, "Error", f"Error: {e}")
            dialog.close()
    
    def on_setup_btn(self):
        self.setup_window = SetupWindow()
        self.setup_window.show()
    
    def on_connected(self):
        self.connect_btn.setEnabled(False)
    
    def on_disconnected(self):
        self.connect_btn.setEnabled(True)
