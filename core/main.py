import logging

from decision import base as decision
import config

def main():
    if config.core_config["log_to_file"]:
        logging.basicConfig(filename="latest.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")
    logging.root.addHandler(logging.StreamHandler())

    logging.info("Hello world! from Turnbased")

    decision.start_provider(config.core_config["provider"])

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="core/core_config.json")
    args = parser.parse_args()

    with open(args.config) as f:
        config.core_config = json.load(f)

    main()
