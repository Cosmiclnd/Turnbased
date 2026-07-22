# Turnbased: A Battle Simulator

[简体中文](README-zh.md)

![Static Badge](https://img.shields.io/badge/License-MIT-yellow)
![Static Badge](https://img.shields.io/badge/python-3.11+-blue)
![Static Badge](https://img.shields.io/badge/status-alpha-red)

A high-fidelity turn-based battle simulation engine written in Python.

> Inspired by the intricate mechanics of Honkai: Star Rail.

## How It Works

- **Event Bus**: All in‑game events (`hit`, `heal`, `weakness_break`, etc.) are dispatched by the event bus, allowing clean separation of concerns.

- **Modifier System**: Every stat (`ATK`, `SPD`, etc.) is a `Stat` object with a list of `Modifiers`. `Modifiers` can have dynamic validators (e.g., only apply when in Complete Combustion state).

- **Damage Pipeline**: Damage calculation is decomposed into independent factors (`DMG_BOOST`, `DEFENCE`, `RESISTANCE`, etc.), each with its own base function and modifier logic.

## Quick Start

![Demo Image](docs/screenshots/demo.png)

### Prerequisites

- Python 3.11 or higher
- `pip` (or `pipenv`)

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/Cosmiclnd/Turnbased.git
cd Turnbased
pip install -r requirements.txt
```

Build the Cython extensions:

```bash
python setup.py build_ext --inplace
```

### Running the Simulator

1. **Start the server** (in a terminal):

```bash
python -m core.main
```

This starts a WebSocket server on `ws://127.0.0.1:55716`.

2. **Launch the client** (in another terminal):

```bash
python client/main.py
```

The client will connect automatically, load the default battle configuration, and you can begin interacting.

> Currently you have to edit `client/userdata/config.json` to create your own battles. A graphical interface will be provided for editing battles in the future.

## Project Structure

```text
client/         # PyQt5 frontend
config/         # All static game data in JSON
core/           # Backend server
docs/           # Documentation (currently under work)
mirror_test/    # Pre‑recorded test scenarios (manually crafted)
utilities/      # Utility scripts
```

## License

This project is open-sourced under the MIT License. You are free to use, modify, and distribute the code for both non-commercial and commercial purposes, provided the original copyright notice is retained.

## Disclaimer

- All game data, character names, skill names, and associated lore are the intellectual property of COGNOSPHERE PTE. LTD. (HoYoverse).
- This project is not affiliated with, endorsed by, or sponsored by HoYoverse.
- The numerical values and mechanics in this repository are either derived from publicly available sources, estimated through in-game observation, or created for testing purposes. They are not guaranteed to be accurate representations of the official game.
- This software is provided "as is", for educational and research purposes only. Do not use it for any commercial endeavors.

## Contributing

While this is a personal project, issues and pull requests are welcome! Please ensure your code adheres to the existing event-driven patterns.
