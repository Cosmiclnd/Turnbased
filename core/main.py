import logging
from websockets.sync.server import serve

import battle
import server

logging.basicConfig(filename="latest.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logging.root.addHandler(logging.StreamHandler())

logging.info("Hello world! from Turnbased")

with serve(server.handle, "127.0.0.1", server.port) as s:
    s.serve_forever()
