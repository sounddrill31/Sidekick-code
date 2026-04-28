from buzzer_sounds import tick_audio
try:
    import wifi
except ImportError:
    pass
from hal import sleep_ms, ticks_ms, ticks_diff
from oled_functions import _text, _draw_ascii, DEFAULT_UPSIDE

# Constants for RSSI to percentage conversion
RSSI_MAX = -30  # dBm, considered 100% signal
RSSI_MIN = -90  # dBm, considered 0% signal

def rssi_to_percentage(rssi):
    if rssi >= RSSI_MAX:
        return 100
    if rssi <= RSSI_MIN:
        return 0
    return int(((rssi - RSSI_MIN) / (RSSI_MAX - RSSI_MIN)) * 100)

def get_wifi_networks():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    networks = []
    try:
        scan_results = wlan.scan()
        for net in scan_results:
            ssid = net[0].decode('utf-8', 'ignore') # Decode SSID, ignore errors
            rssi = net[3]
            networks.append({'ssid': ssid, 'rssi': rssi})
    except Exception as e:
        print("WiFi scan error:", e)
    finally:
        wlan.active(False) # Deactivate WLAN after scan
    
    # Sort by RSSI in descending order
    networks.sort(key=lambda x: x['rssi'], reverse=True)
    return networks

def draw_signal_bar(oled, x, y, width, height, percentage, upside_down):
    fill_width = int(width * (percentage / 100))
    if upside_down:
        # Adjust coordinates for upside-down display
        oled.rect(128 - (x + width), 64 - (y + height), width, height, 1) # Outline
        oled.fill_rect(128 - (x + fill_width), 64 - (y + height), fill_width, height, 1) # Filled part
    else:
        oled.rect(x, y, width, height, 1) # Outline
        oled.fill_rect(x, y, fill_width, height, 1) # Filled part

def run(env):
    print("custom_code_WifiScan.run() started")
    oled = env.get("oled")
    upside_down = env.get("upside_down", DEFAULT_UPSIDE)
    menu_button = env.get("menu_button")
    ok_button = env.get("ok_button")

    if not oled:
        print("OLED object not found in environment.")
        return

    networks = []
    current_scroll_pos = 0
    display_lines = 4 # Number of network entries to display at once

    # Initial scan
    oled.fill(0)
    _text(oled, "Scanning WiFi...", 0, 0, upside_down)
    oled.show()
    networks = get_wifi_networks()

    while True:
        try: tick_audio()
        except: pass
        # Check for menu button press to exit
        if menu_button and menu_button.value() == 0:
            print("Menu button pressed, exiting.")
            while menu_button.value() == 0:
                sleep_ms(20)
            return

        # Check for OK button for scrolling or rescan
        if ok_button and ok_button.value() == 0:
            t0 = ticks_ms()
            long_press = False
            while ok_button.value() == 0:
                if ticks_diff(ticks_ms(), t0) >= 500: # 500ms for long press
                    long_press = True
                    break
                sleep_ms(20)
            
            if long_press:
                # Rescan on long press
                print("OK button long pressed, rescanning.")
                oled.fill(0)
                _text(oled, "Rescanning...", 0, 0, upside_down)
                oled.show()
                networks = get_wifi_networks()
                current_scroll_pos = 0 # Reset scroll position on rescan
            else:
                # Scroll down on short press
                print("OK button short pressed, scrolling.")
                if len(networks) > display_lines:
                    current_scroll_pos = (current_scroll_pos + 1) % (len(networks) - display_lines + 1)
            
            # Wait for button release
            while ok_button.value() == 0:
                sleep_ms(20)

        oled.fill(0)
        _text(oled, "WiFiScan(HoldOK)", 0, 0, upside_down)

        if not networks:
            _text(oled, "No networks found.", 0, 20, upside_down)
        else:
            # Display networks with scrolling
            for i in range(display_lines):
                idx = current_scroll_pos + i
                if idx < len(networks):
                    net = networks[idx]
                    ssid = net['ssid']
                    rssi = net['rssi']
                    percentage = rssi_to_percentage(rssi)

                    display_ssid = ssid[:10] # Truncate SSID if too long
                    line_y = 12 + i * 12

                    _text(oled, f"{display_ssid}", 0, line_y, upside_down)
                    _text(oled, f"{percentage:>3}%", 80, line_y, upside_down) # Right align percentage
                    
                    # Draw signal bar next to percentage
                    bar_x = 108 # X position for the bar
                    bar_y = line_y + 2 # Y position for the bar
                    bar_width = 16
                    bar_height = 6
                    draw_signal_bar(oled, bar_x, bar_y, bar_width, bar_height, percentage, upside_down)

        oled.show()
        sleep_ms(50) # Short delay for responsiveness

if __name__ == "__main__":
    print("This script is meant to be run from menu.py on an ESP32-C3.")
