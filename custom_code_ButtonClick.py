# Auto-restored button counter example.
from hal import Pin, reset
from time import sleep_ms
from pin_values import code_ok_pin_value, code_debug_pin_value
def run(env):
    oled = env.get("oled")
    ok_button = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)
    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)
    if oled:
        oled.fill(0)
        oled.text("Button Counter", 0, 0)
        oled.text("Press OK", 0, 20)
        oled.show()
    count = 0
    while True:
        if menu_button.value() == 0:
            return
        if ok_button.value() == 0:
            count += 1
            if oled:
                oled.fill(0)
                oled.text(f"Pressed: {count}", 0, 20)
                oled.show()
            while ok_button.value() == 0:
                sleep_ms(20)
        sleep_ms(50)
