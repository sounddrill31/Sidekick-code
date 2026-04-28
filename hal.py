import sys
import time

try:
    import board
    import busio
    import digitalio
    import pwmio
    # import adafruit_ssd1306 # If we want to use the adafruit library directly, though we might still use the ported one
    ON_DEVICE = True
except ImportError:
    ON_DEVICE = False

# We need a simple parser for yaml when on device, because pyyaml is not available in circuitpython
def parse_yaml_pins(yaml_str):
    pins = {}
    lines = yaml_str.strip().split('\n')
    in_pins = False
    for line in lines:
        line = line.split('#')[0].strip()
        if not line: continue
        if line == 'pins:':
            in_pins = True
            continue
        if in_pins and ':' in line:
            parts = line.split(':')
            key = parts[0].strip()
            val = parts[1].strip()
            try:
                pins[key] = int(val)
            except ValueError:
                pins[key] = val
    return pins

_pins_config = {}
try:
    with open('hardware.yaml', 'r') as f:
        _pins_config = parse_yaml_pins(f.read())
except Exception as e:
    print("Warning: could not load hardware.yaml:", e)
    # Default fallback
    _pins_config = {
        'button_1': 1,
        'button_2': 0,
        'buzzer': 8,
        'led': 1,
        'i2c_scl': 5,
        'i2c_sda': 4
    }

def get_pin_value(name):
    return _pins_config.get(name)

# ----------------- Timing Functions -----------------
def sleep_ms(ms):
    # To support non-blocking audio while sleeping, we need to tick the audio manager
    # if it exists, otherwise just sleep.
    start = ticks_ms()
    try:
        import buzzer_sounds
        has_audio = True
    except ImportError:
        has_audio = False

    while ticks_diff(ticks_ms(), start) < ms:
        if has_audio:
            try:
                buzzer_sounds.tick_audio()
            except Exception:
                pass
        time.sleep(0.001) # Sleep 1ms to yield CPU

def ticks_ms():
    if hasattr(time, 'ticks_ms'):
        return time.ticks_ms()
    elif hasattr(time, 'monotonic'):
        return int(time.monotonic() * 1000)
    else:
        return int(time.time() * 1000)

def ticks_diff(ticks1, ticks2):
    if hasattr(time, 'ticks_diff'):
        return time.ticks_diff(ticks1, ticks2)
    else:
        # Handling wrap-around isn't strictly necessary for time.time() but standard for ticks
        return ticks1 - ticks2

# ----------------- Hardware Abstraction -----------------

class ButtonMock:
    def __init__(self, pin):
        self.pin = pin
        self._val = 1 # PULL_UP means default is 1 (unpressed), 0 is pressed
    def value(self):
        return self._val
    def set_value(self, v):
        self._val = v

class BuzzerMock:
    def __init__(self, pin):
        self.pin = pin
        self._freq = 0
        self._duty = 0
    def freq(self, f):
        self._freq = f
    def duty_u16(self, d):
        self._duty = d

class I2CMock:
    def __init__(self, scl, sda, freq):
        pass
    def writeto_mem(self, addr, memaddr, buf):
        pass
    def readfrom_mem(self, addr, memaddr, nbytes):
        return b'\x00' * nbytes
    def writeto(self, addr, buf):
        pass

class OledMock:
    def __init__(self):
        self.width = 128
        self.height = 64
        self.buffer = bytearray((self.width // 8) * self.height)
        self._updated = False

    def fill(self, color):
        val = 0xFF if color else 0x00
        for i in range(len(self.buffer)):
            self.buffer[i] = val

    def pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y // 8) * self.width + x
            if color:
                self.buffer[idx] |= (1 << (y % 8))
            else:
                self.buffer[idx] &= ~(1 << (y % 8))

    def fill_rect(self, x, y, w, h, color):
        for i in range(x, x + w):
            for j in range(y, y + h):
                self.pixel(i, j, color)

    def text(self, s, x, y, color=1):
        # We don't have font in the mock, so we'll just ignore or draw a box
        pass

    def show(self):
        self._updated = True


class PinWrapper:
    def __init__(self, pin_num, mode=None, pull=None):
        if hasattr(board, f"IO{pin_num}"):
            self.pin = digitalio.DigitalInOut(getattr(board, f"IO{pin_num}"))
        elif hasattr(board, f"D{pin_num}"):
             self.pin = digitalio.DigitalInOut(getattr(board, f"D{pin_num}"))
        else:
             self.pin = digitalio.DigitalInOut(getattr(board, f"GPIO{pin_num}"))

        if mode == 'IN':
            self.pin.direction = digitalio.Direction.INPUT
        elif mode == 'OUT':
            self.pin.direction = digitalio.Direction.OUTPUT

        if pull == 'UP':
            self.pin.pull = digitalio.Pull.UP
        elif pull == 'DOWN':
            self.pin.pull = digitalio.Pull.DOWN

    def value(self, val=None):
        if val is None:
            return 1 if self.pin.value else 0
        else:
            self.pin.value = bool(val)


class BuzzerWrapper:
    def __init__(self, pin_num):
        if hasattr(board, f"IO{pin_num}"):
            p = getattr(board, f"IO{pin_num}")
        elif hasattr(board, f"D{pin_num}"):
            p = getattr(board, f"D{pin_num}")
        else:
            p = getattr(board, f"GPIO{pin_num}")

        self.pwm = pwmio.PWMOut(p, variable_frequency=True)
        self.pwm.duty_cycle = 0

    def freq(self, f):
        if f > 0:
            self.pwm.frequency = f

    def duty_u16(self, d):
        self.pwm.duty_cycle = d

class Hal:
    def __init__(self):
        self.on_device = ON_DEVICE
        self.buttons = {}
        self.buzzers = {}
        self.i2c = None
        self.oled = None

    def get_button(self, pin_num):
        if pin_num not in self.buttons:
            if self.on_device:
                self.buttons[pin_num] = PinWrapper(pin_num, mode='IN', pull='UP')
            else:
                self.buttons[pin_num] = ButtonMock(pin_num)
        return self.buttons[pin_num]

    def get_buzzer(self, pin_num):
        if pin_num not in self.buzzers:
            if self.on_device:
                self.buzzers[pin_num] = BuzzerWrapper(pin_num)
            else:
                self.buzzers[pin_num] = BuzzerMock(pin_num)
        return self.buzzers[pin_num]

    def get_i2c(self, scl_pin, sda_pin, freq):
        if self.i2c is None:
            if self.on_device:
                if hasattr(board, f"IO{scl_pin}"):
                    scl = getattr(board, f"IO{scl_pin}")
                    sda = getattr(board, f"IO{sda_pin}")
                elif hasattr(board, f"D{scl_pin}"):
                    scl = getattr(board, f"D{scl_pin}")
                    sda = getattr(board, f"D{sda_pin}")
                else:
                    scl = getattr(board, f"GPIO{scl_pin}")
                    sda = getattr(board, f"GPIO{sda_pin}")
                self.i2c = busio.I2C(scl, sda, frequency=freq)
            else:
                self.i2c = I2CMock(scl_pin, sda_pin, freq)
        return self.i2c

    def reset(self):
        if self.on_device:
            import microcontroller
            microcontroller.reset()
        else:
            print("System Reset Requested!")
            sys.exit(0)

# Global HAL instance
hal = Hal()

# Compatibility constants to replace `machine` module where necessary
class Pin:
    IN = 'IN'
    OUT = 'OUT'
    PULL_UP = 'UP'
    PULL_DOWN = 'DOWN'

    def __new__(cls, pin, mode=None, pull=None):
        if mode == 'OUT':
            # For LED etc
            if ON_DEVICE:
                return PinWrapper(pin, mode, pull)
            else:
                return ButtonMock(pin) # Mock pin
        return hal.get_button(pin)

class PWM:
    def __new__(cls, pin_obj):
        # We assume pin_obj is a number or has a pin attribute
        p = pin_obj.pin if hasattr(pin_obj, 'pin') else pin_obj
        if (ON_DEVICE and 'digitalio' in sys.modules and isinstance(p, sys.modules['digitalio'].DigitalInOut)):
            # Hacky fallback if passed a PinWrapper's inner object
            # In CP, you shouldn't use DigitalInOut for PWM. But our code does Pin(pin_val).
            pass

        # The original code did: buzzer = PWM(Pin(buzzer_pin_value))
        # This gives a mock or PinWrapper. We extract the pin number.
        if isinstance(pin_obj, PinWrapper):
             # Hard to get pin num back from board object, so we look it up in buzzers? No, let's just pass the pin_value
             pass
        return hal.get_buzzer(p)

def reset():
    hal.reset()
