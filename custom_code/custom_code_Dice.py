from buzzer_sounds import tick_audio

import random
from hal import Pin, ADC

from pin_values import code_ok_pin_value, code_debug_pin_value
from hal import sleep_ms, ticks_ms, ticks_diff

# ADC pin for entropy
ENTROPY_PIN = 34

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
            # Basic upside-down text rendering
            oled.text(s, 127 - x - (len(s) * 8), 63 - y - 8)


    def draw_dice(roll):
        if not oled: return
        oled.fill(0)
        
        dice_size = 40
        dot_size = 6

        if not upside_down:
            x_offset = (128 - dice_size) // 2
            y_offset = (64 - dice_size) // 2
        else:
            x_offset = (128 - dice_size) // 2
            y_offset = (64 - dice_size) // 2

        oled.rect(x_offset, y_offset, dice_size, dice_size, 1)

        def draw_dot(px, py):
            if not upside_down:
                oled.fill_rect(x_offset + px - dot_size//2, y_offset + py - dot_size//2, dot_size, dot_size, 1)
            else:
                # Adjust dot positions for upside-down display
                # The dice itself is drawn centered, so we only need to flip the dot positions within the dice
                oled.fill_rect(x_offset + (dice_size - px) - dot_size//2, y_offset + (dice_size - py) - dot_size//2, dot_size, dot_size, 1)


        if roll == 1:
            draw_dot(20, 20)
        elif roll == 2:
            draw_dot(10, 10)
            draw_dot(30, 30)
        elif roll == 3:
            draw_dot(10, 10)
            draw_dot(20, 20)
            draw_dot(30, 30)
        elif roll == 4:
            draw_dot(10, 10)
            draw_dot(30, 10)
            draw_dot(10, 30)
            draw_dot(30, 30)
        elif roll == 5:
            draw_dot(10, 10)
            draw_dot(30, 10)
            draw_dot(20, 20)
            draw_dot(10, 30)
            draw_dot(30, 30)
        elif roll == 6:
            draw_dot(10, 10)
            draw_dot(30, 10)
            draw_dot(10, 20)
            draw_dot(30, 20)
            draw_dot(10, 30)
            draw_dot(30, 30)
        
        oled.show()

    # --- Initial Display ------------------------------------------------------
    def display_roll_and_prompt(roll):
        if not oled: return
        oled.fill(0)
        draw_dice(roll)
        oled_text("OK - ReRoll", 28, 50) # Positioned at the bottom
        oled.show()

    # --- Main Loop ------------------------------------------------------------
    current_roll = random.randint(1, 6)
    display_roll_and_prompt(current_roll)

    while True:
        try: tick_audio()
        except: pass
        if ok_button.value() == 0:
            # Wait for button release to avoid multiple triggers
            while ok_button.value() == 0:
                sleep_ms(20)
            
            # Animation
            start_time = ticks_ms()
            while ticks_diff(ticks_ms(), start_time) < 500: # Animate for 500ms
                draw_dice(random.randint(1, 6))
                sleep_ms(50)

            # Final roll
            current_roll = random.randint(1, 6)
            display_roll_and_prompt(current_roll)
            
        if menu_button.value() == 0:
            if oled: oled.fill(0); oled.show()
            return

        sleep_ms(100)
