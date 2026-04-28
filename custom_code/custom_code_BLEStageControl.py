from buzzer_sounds import tick_audio
from hal import sleep_ms, ticks_ms, ticks_diff
from hal import Pin
import ubluetooth as bluetooth
import struct

from pin_values import code_ok_pin_value, code_debug_pin_value
import settings_store
import oled_functions
import menu

# --- Key Codes for Presentation Remote ----------------------------------------
# These are standard HID usage codes for keyboard keys.
KEY_LEFT_ARROW = 0x50
KEY_RIGHT_ARROW = 0x4F
KEY_UP_ARROW = 0x52
KEY_DOWN_ARROW = 0x51
KEY_PAGE_UP = 0x4B
KEY_PAGE_DOWN = 0x4E

# Modifier keys (not used for simple arrow/page keys, but good to have)
MOD_NONE = 0x00

# --- HID Service and Report Descriptor (Standard Keyboard) --------------------
_HID_SERVICE_UUID = bluetooth.UUID(0x1812)
_REPORT_CHAR_UUID = bluetooth.UUID(0x2A4D)
_REPORT_MAP_CHAR_UUID = bluetooth.UUID(0x2A4B)

# HID Report Descriptor for a standard keyboard (8-byte report)
_HID_REPORT_DESCRIPTOR = bytearray([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x06,        # Usage (Keyboard)
    0xA1, 0x01,        # Collection (Application)
    0x05, 0x07,        #   Usage Page (Key Codes)
    0x19, 0xE0,        #   Usage Minimum (224) - Left Control
    0x29, 0xE7,        #   Usage Maximum (231) - Right GUI
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x08,        #   Report Count (8) - 8 modifier bits
    0x81, 0x02,        #   Input (Data, Variable, Absolute) - Modifier byte
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x08,        #   Report Size (8)
    0x81, 0x01,        #   Input (Constant) - Reserved byte
    0x95, 0x06,        #   Report Count (6) - 6 key codes
    0x75, 0x08,        #   Report Size (8)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x65,        #   Logical Maximum (101)
    0x05, 0x07,        #   Usage Page (Key Codes)
    0x19, 0x00,        #   Usage Minimum (0)
    0x29, 0x65,        #   Usage Maximum (101)
    0x81, 0x00,        #   Input (Data, Array, Absolute) - Key array
    0xC0               # End Collection
])

# --- BLE HID Class ------------------------------------------------------------
class BLEHIDPeripheral:
    def __init__(self, name='Sidekick'):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        sleep_ms(100) # Give BLE stack a moment to initialize
        self._ble.irq(self._irq)
        hid_service = (_HID_SERVICE_UUID, ((_REPORT_MAP_CHAR_UUID, bluetooth.FLAG_READ), (_REPORT_CHAR_UUID, bluetooth.FLAG_NOTIFY),))
        handles = self._ble.gatts_register_services((hid_service,))
        self._report_map_handle = handles[0][0]
        self._report_handle = handles[0][1]
        self._ble.gatts_write(self._report_map_handle, _HID_REPORT_DESCRIPTOR)
        self._connections = set()
        self._name = name
        self._advertise()

    def _advertise(self, interval_us=500000):
        # Flags: General Discoverable, BR/EDR Not Supported
        adv_data = bytearray(b'\x02\x01\x06')
        # Complete Local Name
        adv_data += bytes([len(self._name) + 1, 0x09]) + self._name.encode()
        self._ble.gap_advertise(interval_us, adv_data=adv_data)
        print(f"Advertising as {self._name}")

    def _irq(self, event, data):
        if event == 1: # _IRQ_CENTRAL_CONNECT
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print(f"Connected: {conn_handle}")
        elif event == 2: # _IRQ_CENTRAL_DISCONNECT
            conn_handle = data[0] if isinstance(data, tuple) else data
            if conn_handle in self._connections:
                self._connections.remove(conn_handle)
            print(f"Disconnected: {conn_handle}")
            self._advertise() # Restart advertising after disconnection

    def is_connected(self):
        return len(self._connections) > 0

    def send_report(self, report):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._report_handle, report)

    def deinit(self):
        self._ble.active(False)
        print("BLE HID deinitialized.")

# --- Keyboard Functions -------------------------------------------------------
def send_key(ble_hid, modifier, keycode):
    # HID keyboard report is 8 bytes:
    # [modifier byte] [reserved byte] [6 keycode bytes]
    report = bytearray(8)
    report[0] = modifier  # Modifier byte (e.g., Shift, Ctrl, Alt, GUI)
    report[2] = keycode   # First keycode
    ble_hid.send_report(report)
    sleep_ms(50) # Short delay for host to register key press

    # Release all keys
    report[0] = 0x00
    report[2] = 0x00
    ble_hid.send_report(report)
    sleep_ms(50) # Short delay for host to register key release

# --- Main Run Function --------------------------------------------------------
def run(env):
    oled = env.get('oled')
    upside_down = env.get('upside_down', False)
    ok_button = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)
    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)

    sidekick_id = settings_store.get_sidekick_id()
    device_name = f"Sidekick_{sidekick_id}"

    ble_hid = None
    connection_status = "Initializing..."
    current_keybind_index = 0
    keybind_options = [
        ("(L/R)", KEY_LEFT_ARROW, KEY_RIGHT_ARROW),
        ("(Up/Dwn)", KEY_UP_ARROW, KEY_DOWN_ARROW),
        ("Pg(Up/Down)", KEY_PAGE_UP, KEY_PAGE_DOWN)
    ]
    
    # Default to L/R Arrows
    current_keybind_name = keybind_options[current_keybind_index][0]
    
    def display_status():
        if not oled: return
        oled.fill(0)
        oled_functions._text(oled, "BLEStageControl", 0, 0, upside_down)
        oled_functions._text(oled, f"{device_name}", 0, 10, upside_down)
        oled_functions._text(oled, f"{connection_status}", 0, 20, upside_down)
        oled_functions._text(oled, f"Keybind: {current_keybind_name}", 0, 40, upside_down)
        oled_functions._text(oled, "Hold Menu: Exit", 0, 54, upside_down)
        oled.show()

    display_status()

    # Initialize BLE
    try:
        ble_hid = BLEHIDPeripheral(name=device_name)
        connection_status = "Searching..."
        display_status()
    except Exception as e:
        connection_status = f"BLE Error: {e}"
        display_status()
        sleep_ms(2000)
        if oled: oled.fill(0); oled.show()
        return # Exit if BLE init fails

    last_ok_press_time = 0
    last_menu_press_time = 0
    HOLD_THRESHOLD_MS = 700 # Milliseconds for a "hold" action

    while True:
        try: tick_audio()
        except: pass
        # Update connection status
        if ble_hid and ble_hid.is_connected() and connection_status != "Connected":
            connection_status = "Connected"
            display_status()
        elif ble_hid and not ble_hid.is_connected() and connection_status != "Advertising...":
            connection_status = "Searching..."
            display_status()

        # OK Button Handling
        if ok_button.value() == 0: # Button is pressed
            press_start_time = ticks_ms()
            while ok_button.value() == 0:
                sleep_ms(20)
                if ticks_diff(ticks_ms(), press_start_time) >= HOLD_THRESHOLD_MS:
                    # Hold OK: Cycle Keybinds
                    if ticks_diff(ticks_ms(), last_ok_press_time) > HOLD_THRESHOLD_MS: # Prevent rapid cycling on hold
                        current_keybind_index = (current_keybind_index + 1) % len(keybind_options)
                        current_keybind_name = keybind_options[current_keybind_index][0]
                        display_status()
                        last_ok_press_time = ticks_ms()
                    # Keep holding until released
                    while ok_button.value() == 0:
                        sleep_ms(20)
                    break # Exit inner loop after hold action
            else: # Short press OK: Next Slide
                if ble_hid and ble_hid.is_connected():
                    _, _, next_slide_keycode = keybind_options[current_keybind_index]
                    send_key(ble_hid, MOD_NONE, next_slide_keycode)
                sleep_ms(200) # Debounce
            last_ok_press_time = ticks_ms() # Update last press time for debounce/hold logic

        # Menu Button Handling
        if menu_button.value() == 0: # Button is pressed
            press_start_time = ticks_ms()
            while menu_button.value() == 0:
                sleep_ms(20)
                if ticks_diff(ticks_ms(), press_start_time) >= HOLD_THRESHOLD_MS:
                    # Hold Menu: Go back to menu
                    if ble_hid: ble_hid.deinit()
                    if oled: oled.fill(0); oled.show()
                    menu.open_menu(oled=oled, debug_mode=False, upside_down=upside_down, called_from_main=False, env=env)
                    return # Exit this custom code
            else: # Short press Menu: Previous Slide
                if ble_hid and ble_hid.is_connected():
                    _, prev_slide_keycode, _ = keybind_options[current_keybind_index]
                    send_key(ble_hid, MOD_NONE, prev_slide_keycode)
                sleep_ms(200) # Debounce
            last_menu_press_time = ticks_ms() # Update last press time for debounce/hold logic

        sleep_ms(50) # Main loop delay