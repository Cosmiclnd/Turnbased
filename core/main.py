import logging

from decision import base as decision

def main(provider_name: str, log_to_file: bool):
    if log_to_file:
        logging.basicConfig(filename="latest.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")
    logging.root.addHandler(logging.StreamHandler())

    logging.info("Hello world! from Turnbased")

    decision.start_provider(provider_name)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", type=str, default="server_provider")
    parser.add_argument("--log", type=bool, default=True)
    args = parser.parse_args()

    main(args.provider, args.log)
