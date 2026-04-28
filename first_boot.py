import oled_functions
import settings_store
from hal import Pin
from hal import sleep_ms, ticks_ms, ticks_diff
from pin_values import code_debug_pin_value, code_ok_pin_value

def run_first_boot(oled, upside_down):
    """
    Manages the first boot setup process with a redesigned horizontal UI.
    """
    menu_items = [
        {"name": "Web Setup", "key": "web"},
        {"name": "Offline", "key": "skip"},
    ]
    selected_index = 0

    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)
    ok_button = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)

    # Calculate initial positions
    web_text = menu_items[0]["name"]
    skip_text = menu_items[1]["name"]
    web_text_width = len(web_text) * 8
    skip_text_width = len(skip_text) * 8
    total_width = web_text_width + skip_text_width + 24
    web_x = (oled.width - total_width) // 2
    skip_x = web_x + web_text_width + 24

    selector_x = float(web_x - 6)

    while True:
        oled.fill(0)

        # Title
        title = "Sidekick Setup"
        title_x = (oled.width - len(title) * 8) // 2
        oled_functions.update_oled(oled, "text", title, upside_down=upside_down, x=title_x, y=4)

        # Selector logic
        if selected_index == 0:
            target_selector_x = web_x - 6
            selector_width = web_text_width + 12
        else:
            target_selector_x = skip_x - 6
            selector_width = skip_text_width + 12
        
        # Smooth animation for selector
        selector_x += (target_selector_x - selector_x) * 0.9
        
        # Draw selector as a filled rectangle
        oled_functions.fill_rect(oled, int(selector_x), 25, selector_width, 15, 1, upside_down)

        # Draw text (inverted on selector)
        oled_functions.update_oled(oled, "text", web_text, upside_down=upside_down, x=web_x, y=29, color=(0 if selected_index == 0 else 1))
        oled_functions.update_oled(oled, "text", skip_text, upside_down=upside_down, x=skip_x, y=29, color=(0 if selected_index == 1 else 1))

        # Instructions
        oled_functions.update_oled(oled, "text", "Skip", upside_down=upside_down, x=1, y=oled.height - 10)
        oled_functions.update_oled(oled, "text", "Web", upside_down=upside_down, x=oled.width - 24 - 4, y=oled.height - 10)

        oled.show()

        # Handle input
        if menu_button.value() == 0:
            sleep_ms(100) # Debounce
            selected_index = (selected_index + 1) % len(menu_items)
            while menu_button.value() == 0:
                sleep_ms(20)

        if ok_button.value() == 0:
            sleep_ms(100) # Debounce
            
            press_start_time = ticks_ms()
            is_long_press = False
            while ok_button.value() == 0:
                if ticks_diff(ticks_ms(), press_start_time) > 1000: # 1 second
                    is_long_press = True
                    break
                sleep_ms(20)

            if is_long_press:
                oled.fill(0)
                oled_functions.update_oled(oled, "text", "Using Defaults...", upside_down=upside_down, line=2)
                oled.show()
                sleep_ms(1000)
                settings_store._settings['user_name'] = "User"
                settings_store._settings['sidekick_name'] = "Sidekick"
                settings_store._settings['setup_completed'] = True
                settings_store._save()
                sleep_ms(100)
                break

            # Short press logic
            selection = menu_items[selected_index]['key']
            
            if selection == "web":
                import web_server
                web_server.start_web_server(oled, upside_down)
                break
            elif selection == "skip":
                settings_store._settings['user_name'] = "User"
                settings_store._settings['sidekick_name'] = "Sidekick"
                settings_store._settings['setup_completed'] = True
                settings_store._save()
                sleep_ms(100)
                break