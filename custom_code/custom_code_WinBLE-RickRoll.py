from buzzer_sounds import tick_audio
from hal import sleep_ms
from hal import Pin

import ubluetooth as bluetooth
import struct

from pin_values import code_ok_pin_value, code_debug_pin_value
from buzzer_sounds import buzzer_beeping

# --- Payloads -----------------------------------------------------------------


def run_payload(ble_hid):
    print("Sending payload...")
    sleep_ms(500)
    send_key(ble_hid, MOD_LEFT_GUI, KEY_R)
    sleep_ms(2000)
    type_string(ble_hid, "edge --new-window --app=https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    sleep_ms(2000)
    send_key(ble_hid, 0, KEY_ENTER)
    print("Payload sent.")



# --- Constants ----------------------------------------------------------------
# HID Service UUID
_HID_SERVICE_UUID = bluetooth.UUID(0x1812)
# Characteristic UUIDs
_REPORT_CHAR_UUID = bluetooth.UUID(0x2A4D)
_REPORT_MAP_CHAR_UUID = bluetooth.UUID(0x2A4B)

# HID Report Descriptor for a standard keyboard
_HID_REPORT_DESCRIPTOR = bytearray([
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01,
    0x75, 0x01, 0x95, 0x08, 0x81, 0x02, 0x95, 0x01, 0x75, 0x08, 0x81, 0x01, 0x95, 0x06, 0x75, 0x08,
    0x15, 0x00, 0x25, 0x65, 0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00, 0xC0
])

# --- Key Codes ----------------------------------------------------------------
MOD_LEFT_GUI = 0x08; MOD_LEFT_SHIFT = 0x02
KEY_A = 0x04; KEY_B = 0x05; KEY_C = 0x06; KEY_D = 0x07; KEY_E = 0x08; KEY_F = 0x09;
KEY_G = 0x0A; KEY_H = 0x0B; KEY_I = 0x0C; KEY_J = 0x0D; KEY_K = 0x0E; KEY_L = 0x0F;
KEY_M = 0x10; KEY_N = 0x11; KEY_O = 0x12; KEY_P = 0x13; KEY_Q = 0x14; KEY_R = 0x15;
KEY_S = 0x16; KEY_T = 0x17; KEY_U = 0x18; KEY_V = 0x19; KEY_W = 0x1A; KEY_X = 0x1B;
KEY_Y = 0x1C; KEY_Z = 0x1D; KEY_1 = 0x1E; KEY_2 = 0x1F; KEY_3 = 0x20; KEY_4 = 0x21;
KEY_5 = 0x22; KEY_6 = 0x23; KEY_7 = 0x24; KEY_8 = 0x25; KEY_9 = 0x26; KEY_0 = 0x27;
KEY_ENTER = 0x28; KEY_SPACE = 0x2C; KEY_DOT = 0x37; KEY_SLASH = 0x38;
KEY_SEMICOLON = 0x33; KEY_EQUAL = 0x2E;

# --- BLE HID Class ------------------------------------------------------------
class BLEHIDPeripheral:
    def __init__(self, name='sideblukeys'):
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
        adv_data = bytearray(b'\x02\x01\x06') + bytes([len(self._name) + 1, 0x09]) + self._name.encode()
        self._ble.gap_advertise(interval_us, adv_data=adv_data)
        print(f"Advertising as {self._name}")

    def _irq(self, event, data):
        if event == 1:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print(f"Connected: {conn_handle}")
        elif event == 2:
            conn_handle = data[0] if isinstance(data, tuple) else data
            if conn_handle in self._connections:
                self._connections.remove(conn_handle)
            print(f"Disconnected: {conn_handle}")
            self._advertise()

    def send_report(self, report):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._report_handle, report)

    def deinit(self):
        self._ble.active(False)
        print("BLE HID deinitialized.")

# --- Keyboard Functions -------------------------------------------------------

def send_key(ble_hid, modifier, keycode):
    report = bytearray(8)
    report[0] = modifier
    report[2] = keycode
    ble_hid.send_report(report)
    sleep_ms(20)
    report[0] = 0
    report[2] = 0
    ble_hid.send_report(report)
    sleep_ms(20)

def type_string(ble_hid, text):
    keymap = {
        'a': (0, KEY_A), 'b': (0, KEY_B), 'c': (0, KEY_C), 'd': (0, KEY_D), 'e': (0, KEY_E),
        'f': (0, KEY_F), 'g': (0, KEY_G), 'h': (0, KEY_H), 'i': (0, KEY_I), 'j': (0, KEY_J),
        'k': (0, KEY_K), 'l': (0, KEY_L), 'm': (0, KEY_M), 'n': (0, KEY_N), 'o': (0, KEY_O),
        'p': (0, KEY_P), 'q': (0, KEY_Q), 'r': (0, KEY_R), 's': (0, KEY_S), 't': (0, KEY_T),
        'u': (0, KEY_U), 'v': (0, KEY_V), 'w': (0, KEY_W), 'x': (0, KEY_X), 'y': (0, KEY_Y),
        'z': (0, KEY_Z), '1': (0, KEY_1), '2': (0, KEY_2), '3': (0, KEY_3), '4': (0, KEY_4),
        '5': (0, KEY_5), '6': (0, KEY_6), '7': (0, KEY_7), '8': (0, KEY_8), '9': (0, KEY_9),
        '0': (0, KEY_0), ' ': (0, KEY_SPACE), '.': (0, KEY_DOT), '/': (0, KEY_SLASH),
        '=': (0, KEY_EQUAL), ':': (MOD_LEFT_SHIFT, KEY_SEMICOLON), '?': (MOD_LEFT_SHIFT, KEY_SLASH),
    }
    for char in text:
        if char.isupper():
            modifier, keycode = keymap.get(char.lower(), (0, 0))
            send_key(ble_hid, MOD_LEFT_SHIFT | modifier, keycode)
        else:
            modifier, keycode = keymap.get(char, (0, 0))
            send_key(ble_hid, modifier, keycode)

# --- Main Run Function --------------------------------------------------------
def run(env):
    oled = env.get('oled')
    upside_down = env.get('upside_down', False)
    ok_button = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)
    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)

    def oled_text(s, x, y):
        if not oled: return
        if not upside_down:
            oled.text(s, x, y)
        else:
            w = len(s) * 8
            h = 8
            buf = bytearray(w * h // 8)
            fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_VLSB)
            fb.text(s, 0, 0, 1)
            for i in range(w):
                for j in range(h):
                    if fb.pixel(i, j):
                        fx = 128 - (x + (i + 1))
                        fy = 64 - (y + (j + 1))
                        if 0 <= fx < 128 and 0 <= fy < 64:
                            oled.pixel(fx, fy, 1)

    def display_update(step):
        if not oled: return
        oled.fill(0)
        oled_text("WinBluKeys", 0, 0)
        oled_text("Win/BLE Only", 0, 10)
        if step == 0:
            oled_text("OK to start BLE", 0, 30)
        elif step == 1:
            oled_text("Waiting for", 0, 20)
            oled_text("connection...", 0, 30)
        elif step == 2:
            oled_text("Paired!", 0, 20)
            oled_text("OK-Send Payload", 0, 40)
        elif step == 3:
            oled_text("Payload Sent!", 0, 20)
            oled_text("OK to exit", 0, 40)
        oled.show()

    ble_hid = None
    state = 0  # 0: Initial, 1: Waiting for connection, 2: Paired, 3: Payload sent
    display_update(state)

    while True:
        try: tick_audio()
        except: pass
        if ble_hid and state == 1 and ble_hid._connections:
            buzzer_beeping()
            state = 2
            display_update(state)

        if ok_button.value() == 0:
            if state == 0:
                ble_hid = BLEHIDPeripheral()
                state = 1
            elif state == 2:
                run_payload(ble_hid)
                state = 3
            else: # state 1 or 3, exit
                if ble_hid: ble_hid.deinit()
                if oled: oled.fill(0); oled.show()
                return
            display_update(state)
            while ok_button.value() == 0: sleep_ms(20)

        if menu_button.value() == 0:
            if ble_hid: ble_hid.deinit()
            if oled: oled.fill(0); oled.show()
            return

        sleep_ms(50)