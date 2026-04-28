# MakerSidekick Bot Agent Spec

Welcome, Future Knowledge Worker!

## Architecture

This project has been rewritten to be fully compatible with CircuitPython while still retaining the original MicroPython-esque flow. It achieves this by abstracting hardware interactions through the `hal.py` module.

### `hal.py` (Hardware Abstraction Layer)
- If the code is running on a compatible device (e.g., an ESP32 or Pico), `hal.py` utilizes CircuitPython's standard modules (`board`, `digitalio`, `busio`, `pwmio`, etc.).
- If the code is running on a PC (via `pixi run simulator`), `hal.py` uses mock classes (`ButtonMock`, `OledMock`, `BuzzerMock`, `I2CMock`).
- **Rule:** Do NOT import `machine` or hardware-specific modules in logic files (`main.py`, `menu.py`, `ADXL345.py`, etc). Always import from `hal.py` (e.g., `from hal import Pin, sleep_ms`).

### `hardware.yaml`
- The hardware pinout is strictly defined in `hardware.yaml`.
- `hal.py` and `pin_values.py` parse this file to allocate resources.
- `studio.py` reads this file to dynamically generate Simulator UI buttons.

### `studio.py` (Flet Simulator)
- We use Flet to render a complete desktop application for designing and testing.
- The Simulator tab visualizes the mocked `OledMock` buffer and provides clickable inputs for the `ButtonMock`.
- The `main.py` core logic runs in a background thread inside `studio.py`, meaning standard loops `while True:` work without blocking the UI.

### Extending
- To add a new sensor, define its logic in its own file using `hal.py` (e.g., `hal.get_i2c()`), add the pins to `hardware.yaml`, and update `studio.py` if a visual representation or manual trigger is desired in the simulator.

### Important Instructions for Agents
Always test the thing locally once in a way that catches the error you're trying to fix. For example, if you fix a Flet GUI crash, actually run the simulator via `pixi run simulator` or programmatically import it to verify the fix works and doesn't throw a new TypeError. Do not just blindly commit without testing the UI.
