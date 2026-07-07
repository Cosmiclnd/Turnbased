from PyQt5.QtCore import QUrl
from PyQt5.QtWebSockets import QWebSocket
import json

class Client(QWebSocket):
    def __init__(self):
        super().__init__()
    
    def connect_to_server(self, host, port):
        self.open(QUrl(f"ws://{host}:{port}"))
    
    def send_message(self, message):
        self.sendTextMessage(json.dumps(message))
    
    def on_received(self, message):
        pass  # TODO
