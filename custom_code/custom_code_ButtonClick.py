from buzzer_sounds import tick_audio
from hal import sleep_ms
from hal import Pin

from pin_values import code_ok_pin_value, code_debug_pin_value

def run(env):
    oled = env.get('oled')
    upside_down = env.get('upside_down', False)

    # Initialize hardware
    ok_button = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)
    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)

    # Local text function to handle upside_down
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

    if oled:
        oled.fill(0)
        oled_text('Button Counter', 0, 0)
        oled_text('Press OK', 0, 20)
        oled_text('Menu to exit', 0, 40)
        oled.show()

    # Wait for button release from menu
    if menu_button:
        while menu_button.value() == 0:
            sleep_ms(20)
    if ok_button:
        while ok_button.value() == 0:
            sleep_ms(20)

    press_count = 0
    while True:
        try: tick_audio()
        except: pass
        if menu_button and menu_button.value() == 0:
            if oled: oled.fill(0); oled.show()
            return

        if ok_button and ok_button.value() == 0:
            press_count += 1
            if oled:
                oled.fill(0)
                oled_text('Ok Button Press', 0, 20)
                oled_text(f'Count: {press_count}', 0, 40)
                oled.show()
            
            # Wait for release
            while ok_button.value() == 0:
                sleep_ms(20)
        
        sleep_ms(50)
