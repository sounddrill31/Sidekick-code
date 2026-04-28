from buzzer_sounds import tick_audio
from hal import sleep_ms, ticks_ms, ticks_diff
from hal import Pin

from pin_values import code_ok_pin_value, code_debug_pin_value
from buzzer_sounds import buzzer_beeping

# --- Constants ----------------------------------------------------------------
WORK_MINUTES = 25
BREAK_MINUTES = 5
HOLD_THRESHOLD_MS = 1000  # 1 second to register a hold

# --- States -------------------------------------------------------------------
IDLE = 0
WORK = 1
BREAK = 2
WORK_DONE = 3
BREAK_DONE = 4

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
    pomodoros_completed = 0
    timer_end_ms = 0
    session_start_ms = 0
    total_work_seconds = 0
    total_break_seconds = 0

    # --- Initial Display ------------------------------------------------------
    def update_display():
        if not oled: return
        oled.fill(0)
        if state == IDLE:
            oled_text("Pomodoro Timer", 0, 0)
            oled_text("Hold OK - start", 0, 12)
            oled_text(f"Work: {total_work_seconds // 60}m {total_work_seconds % 60}s", 0, 30)
            oled_text(f"Break: {total_break_seconds // 60}m {total_break_seconds % 60}s", 0, 42)
        elif state == WORK:
            remaining_seconds = max(0, ticks_diff(timer_end_ms, ticks_ms()) // 1000)
            oled_text("Work Session", 0, 0)
            oled_text(f"Time: {remaining_seconds // 60:02d}:{remaining_seconds % 60:02d}", 0, 20)
            oled_text("Hold OK - break", 0, 40)
        elif state == BREAK:
            remaining_seconds = max(0, ticks_diff(timer_end_ms, ticks_ms()) // 1000)
            oled_text("Break Time", 0, 0)
            oled_text(f"Time: {remaining_seconds // 60:02d}:{remaining_seconds % 60:02d}", 0, 20)
            oled_text("Press OK - Work", 0, 40)
            oled_text("Hold OK - END", 0, 50)
        elif state == WORK_DONE:
            oled_text("Work Done!", 0, 0)
            oled_text("Start Break?", 0, 20)
            oled_text("Press OK - Break", 0, 40)
            oled_text("Hold OK - END", 0, 50)
        elif state == BREAK_DONE:
            oled_text("Break Done!", 0, 0)
            oled_text("Continue Work?", 0, 20)
            oled_text("Press OK - Work", 0, 40)
            oled_text("Hold OK - END", 0, 50)
        oled.show()

    update_display()

    # --- Main Loop ------------------------------------------------------------
    while True:
        try: tick_audio()
        except: pass
        now = ticks_ms()

        # --- Timer Events ---
        if state == WORK and now >= timer_end_ms:
            pomodoros_completed += 1
            total_work_seconds += (now - session_start_ms) // 1000
            state = WORK_DONE
            buzzer_beeping()
        elif state == BREAK and now >= timer_end_ms:
            total_break_seconds += (now - session_start_ms) // 1000
            state = BREAK_DONE
            buzzer_beeping()

        # --- Button Events ---
        if ok_button.value() == 0:
            hold_start = now
            is_held = False
            while ok_button.value() == 0:
                if ticks_diff(ticks_ms(), hold_start) > HOLD_THRESHOLD_MS:
                    is_held = True
                    break
                sleep_ms(20)
            
            if is_held:
                if state == IDLE:
                    state = WORK
                    session_start_ms = now
                    timer_end_ms = now + WORK_MINUTES * 60 * 1000
                    buzzer_beeping()
                elif state == WORK:
                    total_work_seconds += (now - session_start_ms) // 1000
                    state = BREAK
                    session_start_ms = now
                    timer_end_ms = now + BREAK_MINUTES * 60 * 1000
                    buzzer_beeping()
                elif state == BREAK:
                    total_break_seconds += (now - session_start_ms) // 1000
                    state = IDLE
                    buzzer_beeping()
                elif state == WORK_DONE or state == BREAK_DONE:
                    state = IDLE
                    buzzer_beeping()
            else: # Short press
                if state == BREAK:
                    total_break_seconds += (now - session_start_ms) // 1000
                    state = WORK
                    session_start_ms = now
                    timer_end_ms = now + WORK_MINUTES * 60 * 1000
                    buzzer_beeping()
                elif state == WORK_DONE:
                    state = BREAK
                    session_start_ms = now
                    timer_end_ms = now + BREAK_MINUTES * 60 * 1000
                    buzzer_beeping()
                elif state == BREAK_DONE:
                    state = WORK
                    session_start_ms = now
                    timer_end_ms = now + WORK_MINUTES * 60 * 1000
                    buzzer_beeping()
            
            # Wait for release
            while ok_button.value() == 0:
                sleep_ms(20)

        # --- Exit to Menu ---
        if menu_button.value() == 0:
            if oled: oled.fill(0); oled.show()
            return

        # --- Update Display ---
        update_display()
        sleep_ms(100)
