# Control Panel

A control panel to manage and monitor various scripts.

## Files

- `control_panel.py`: The main GUI application for the control panel.
- `browser_grid_arranger.py`: A script to arrange browser windows in a grid.
- `Auto Click Script-MOD (WebSocket Client).js`: A script for auto-clicking, controlled via WebSockets.
- `itemurl.txt`: A file containing URLs.

## Setup

1. Install Python 3.
2. Install the required Python libraries:
   ```
   pip install websockets Pillow requests
   ```

## Usage

1. Run the control panel:
   ```
   python control_panel.py
   ```
2. The control panel provides buttons to start/stop the auto-click scripts and to run the browser grid arranger.
3. The control panel also features a WebSocket server to communicate with the auto-click scripts.
