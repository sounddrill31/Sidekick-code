from buzzer_sounds import tick_audio
from hal import sleep_ms, ticks_ms, ticks_diff
from hal import Pin

from pin_values import code_ok_pin_value, code_debug_pin_value

# --- States -------------------------------------------------------------------
IDLE = 0
RUNNING = 1

def run(env):
    oled = env.get('oled')
    upside_down = env.get('upside_down', False)

    # --- Hardware Initialization ----------------------------------------------
    ok_button = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)
    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)

    # --- Local OLED Text Function ---------------------------------------------
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

    # --- State Variables ------------------------------------------------------
    state = IDLE
    start_time_ms = 0
    elapsed_time_ms = 0
    previous_times = [0, 0, 0]

    # --- Format Time Function -------------------------------------------------
    def format_time(ms):
        ss = (ms // 1000) % 60
        mm = (ms // 60000) % 60
        hh = (ms // 3600000) % 24
        dd = ms // 86400000
        return f"{dd:02d}:{hh:02d}:{mm:02d}:{ss:02d}"

    # --- Initial Display ------------------------------------------------------
    def update_display():
        if not oled: return
        oled.fill(0)
        oled_text("Simple Stopwatch", 0, 0)
        
        current_time_ms = elapsed_time_ms
        if state == RUNNING:
            current_time_ms += ticks_diff(ticks_ms(), start_time_ms)

        if state == IDLE:
            oled_text("Press OK - Start", 0, 12)
        else:
            oled_text("Press OK - Stop", 0, 12)

        oled_text(format_time(current_time_ms), 0, 24)
        
        oled_text(f"1: {format_time(previous_times[0])}", 0, 40)
        oled_text(f"2: {format_time(previous_times[1])}", 0, 50)
        oled_text(f"3: {format_time(previous_times[2])}", 0, 60)
            
        oled.show()

    update_display()

    # --- Main Loop ------------------------------------------------------------
    while True:
        try: tick_audio()
        except: pass
        # --- Button Events ---
        if ok_button.value() == 0:
            if state == IDLE:
                state = RUNNING
                start_time_ms = ticks_ms()
                elapsed_time_ms = 0
            else: # RUNNING
                state = IDLE
                previous_times.insert(0, elapsed_time_ms + ticks_diff(ticks_ms(), start_time_ms))
                previous_times.pop()
            
            # Wait for release
            while ok_button.value() == 0:
                sleep_ms(20)

        # --- Exit to Menu ---
        if menu_button.value() == 0:
            if oled: oled.fill(0); oled.show()
            return

        # --- Update Display ---
        if state == RUNNING:
            elapsed_time_ms = ticks_diff(ticks_ms(), start_time_ms)
        update_display()
        sleep_ms(50)
