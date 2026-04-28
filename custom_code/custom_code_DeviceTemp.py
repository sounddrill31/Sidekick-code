from buzzer_sounds import tick_audio
try:
    import microcontroller
except:
    pass
from oled_functions import _text, _draw_ascii, DEFAULT_UPSIDE
from hal import sleep_ms

# Function to get the internal temperature in Celsius
def get_device_temperature_celsius():
    temp_c = esp32.mcu_temperature() # esp32.mcu_temperature() directly returns Celsius for ESP32-C3
    return temp_c

def run(env):
    print("custom_code_DeviceTemp.run() started") # Debug print
    oled = env.get("oled")
    upside_down = env.get("upside_down", DEFAULT_UPSIDE)
    menu_button = env.get("menu_button") # Get the menu button (debug button)
    ok_button = env.get("ok_button") # Get the OK button

    if not oled:
        print("OLED object not found in environment.")
        return

    while True:
        try: tick_audio()
        except: pass
        # Check for menu button press to exit
        if menu_button and menu_button.value() == 0: # Assuming active low
            print("Menu button pressed, exiting.") # Debug print
            while menu_button.value() == 0:
                sleep_ms(20)
            return
        temp_c = get_device_temperature_celsius()
        temp_str = "{:.1f}".format(temp_c) + "°C"

        oled.fill(0) # Clear the display

        # Display "Device Temp" label
        _text(oled, "Device Temp:", 0, 0, upside_down)

        # Display the temperature value prominently
        # Centered horizontally, slightly below the label
        temp_x = (128 - len(temp_str) * 8 * 2) // 2 # Calculate x for centered text, scale 2
        _draw_ascii(oled, temp_str, temp_x, 20, 2, upside_down)

        _text(oled, "Press Menu: Back", 0, 50, upside_down)

        # Show the content
        oled.show()
        sleep_ms(50) # Reduced sleep for responsiveness

if __name__ == "__main__":
    print("Running custom_code_DeviceTemp.py directly is not supported.")
    print("This script expects an 'oled' object to be passed to its 'main' function.")
