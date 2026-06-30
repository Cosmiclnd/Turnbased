import websockets
import json
import pytest

port = 55716

async def send_message(websocket, message):
    await websocket.send(json.dumps(message))

async def recv_message(websocket):
    return json.loads(await websocket.recv())

async def start(name):
    async with websockets.connect(f'ws://localhost:{port}') as websocket:
        await send_message(websocket, {"type": "init_battle"})
        with open(f"mirror_test/{name}/data.json") as f:
            data = json.load(f)
        await send_message(websocket, {"type": "setup_monsters", "record": data["monsters"]})
        for record in data["characters"]:
            await send_message(websocket, {"type": "add_character", "record": record})
        for uuid, state in data["initial_state"].items():
            await send_message(websocket, {"type": "set_initial_state", "target": uuid, "state": state})
        await send_message(websocket, {"type": "setup_random", "config": {"use_random": False}})
        await send_message(websocket, {"type": "start_battle"})
        await main(websocket, data)

class Tester:
    def __init__(self, uuids):
        self.uuids = uuids
    
    def test(self, type, test, message):
        method = getattr(self, type)
        method(test, message)
    
    def assert_message_name(self, test, message):
        assert message["type"] == test["type"]
        assert message["name"] == test["name"]
    
    def assert_target(self, test, message):
        name = test["name"]
        uuid_name = test["uuid"]
        assert message[name]["uuid"] == self.uuids[uuid_name]
    
    def assert_damage_types(self, test, message):
        assert message["damage"]["types"] == test["types"]
    
    def assert_damage_crit(self, test, message):
        assert message["damage"]["crit"] == test["crit"]
    
    def assert_damage_amount(self, test, message):
        assert pytest.approx(message["damage"]["amount"], abs=2) == test["amount"]  # TODO: error too high

async def main(websocket, data):
    tester = Tester(data["uuids"])
    process = data["process"]
    for step in process:
        message = await recv_message(websocket)
        for test in step["tests"]:
            type = test["$type"]
            tester.test(type, test, message)
        await send_message(websocket, step["response"])
