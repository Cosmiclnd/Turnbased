import logging
import asyncio
import websockets

import battle
import server

async def main():
    async with websockets.serve(server.handle, "localhost", server.port):
        await server.shutdown_event.wait()

logging.basicConfig(filename="latest.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logging.root.addHandler(logging.StreamHandler())

logging.info("Hello world! from Turnbased")

asyncio.run(main())
