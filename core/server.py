import websockets
import logging
import json
import os
import sys
import io
import uuid
import msgpack

import battle
import config
import action

LOG_MESSAGE = False

port = 55716
handler = None

def handle_message_outbattle(message):
    import target  # TODO: Python 3.15 lazy import
    type = message["type"]
    if type == "init_battle":
        battle.current = battle.Battle()
        battle.current.action_list = action.ActionList()
    elif type == "start_battle":
        battle.current.start()
    elif type == "add_character":
        character = config.load_class("characters", message["record"]["name"])(message["record"])
        battle.current.characters.append(character)
    elif type == "setup_monsters":
        battle.current.monster_setup.set_record(message["record"])
    elif type == "setup_random":
        battle.current.random = battle.Random(message["config"])
    elif type == "set_initial_state":
        t = target.from_uuid(uuid.UUID(message["target"]))
        if t is None:
            return
        t.initial_state = message["state"]
    elif type == "use_technique":
        t = target.from_uuid(uuid.UUID(message["target"]))
        from characters import base as character  # TODO: Python 3.15 lazy import
        if t is None or not isinstance(t, character.Character):
            return
        t.use_technique = True
    elif type == "set_battle_config":
        battle.current.config = battle.BattleConfig(battle.BattleType.dict_nameid[message["config"]["type"]])
        # TODO: config["trigger"] triggers the battle
    elif type == "use_feature":
        battle.current.features.use(message["feature"])

class CloseServer(Exception):
    pass

def handle(websocket):
    global handler
    handler = InbattleHandler(websocket)
    while True:
        try:
            try:
                message = msgpack.unpackb(websocket.recv())
                handle_message_outbattle(message)
            except (CloseServer, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                logging.info("connection closed")
                break
            except Exception as e:
                    logging.exception(e)
                    logging.error(battle.current.event_bus.format_stack())
                    websocket.close()
        except Exception as e:
            logging.critical(e)
            os._exit(1)

# 服务端的战斗内通信分为以下三种
# ANSWER: 回复客户端的请求
# ASK: 要求客户端操作
# UPDATE: 通知客户端更新
# 只要客户端发出QUERY就要ANSWER
class InbattleHandler:
    def __init__(self, websocket):
        self.websocket = websocket
        self.updates = []
        self.answer_handlers = {}
    
    def add_answer_handler(self, name, handler):
        self.answer_handlers[name] = handler
    
    def send_and_recv(self, message):
        self.websocket.send(msgpack.packb(message))
        return msgpack.unpackb(self.websocket.recv())
    
    def check_client_query(self, message):
        if message["type"] != "query":
            return
        if message["name"] in self.answer_handlers:
            try:
                response = {"info": "ok"}
                response |= self.answer_handlers[message["name"]](message)
            except Exception:
                response = {"info": "internal_error"}
            response["type"] = "answer"
            return response
    
    def ask_client(self, message, handler):
        self.flush_updates()
        if LOG_MESSAGE:
            logging.info(f"Calling ask_client {message}")
        message["type"] = "ask"
        message["info"] = None
        while True:
            temp = message
            while True:
                response = self.send_and_recv(temp)
                if (answer := self.check_client_query(response)) is not None:
                    temp = answer
                else:
                    break
            try:
                message["info"] = handler(response)
            except Exception:
                message["info"] = "internal_error"
            if message["info"] == "ok":
                return response
            elif LOG_MESSAGE:
                logging.warning(f"Handler returned {message['info']}")
    
    def update_client(self, message):
        if LOG_MESSAGE:
            logging.info(f"Calling update_client {message}")
        message["type"] = "update"
        self.updates.append(message)
    
    def flush_updates(self):
        if not self.updates:
            return
        message = {"type": "updates", "updates": self.updates} if len(self.updates) > 1 else self.updates[0]
        while True:
            response = self.send_and_recv(message)
            if (answer := self.check_client_query(response)) is not None:
                message = answer
            else:
                break
        self.updates = []
    
    def close(self):
        raise CloseServer

def server_handler(func):  # 提示功能
    return func

def server_responder(func):  # 提示功能
    return func
