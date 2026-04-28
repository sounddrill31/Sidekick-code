from hal import Pin, reset
from hal import sleep_ms, ticks_ms, ticks_diff
from pin_values import code_debug_pin_value, buzzer_pin_value, led_pin_value, code_ok_pin_value
import settings_store
import json
import os, sys
import oled_functions

PRESERVE_CUSTOM_CODE = {'custom_code_Dice.py', 'custom_code_ButtonClick.py', 'custom_code_Pomodoro.py', 'custom_code_Stopwatch.py', 'custom_code_WinBLE-RickRoll.py', 'custom_code_DeviceTemp.py', 'custom_code_WifiScan.py', 'custom_code_BLEStageControl.py', 'custom_code_RhythmGame.py', 'custom_code_FlappyGame.py', 'custom_code_DinoGame.py', 'custom_code_SnakeGame.py', 'custom_code_Breakout.py'}  # Files never deleted by wipe

def get_preserved_files():
    return PRESERVE_CUSTOM_CODE

# Helper to detect custom core availability
def _custom_core_available():
    try:
        with open('custom_core.json','r') as f:
            data = json.load(f)
        return isinstance(data, dict) and ('faces' in data or 'sounds' in data)
    except Exception:
        return False

# Scan for custom code scripts (pattern custom_code_*.py)
def _list_custom_code():
    files = []
    try:
        for fn in os.listdir():
            if fn.startswith('custom_code_') and fn.endswith('.py'):
                files.append(fn)
    except Exception:
        pass
    files.sort()
    return files

# Ensure example file exists (no longer inlined here; separate file)
def _ensure_example():
    example = 'custom_code_ButtonClick.py'
    if example not in _list_custom_code():
        try:
            with open(example, 'w') as f:
                f.write(('# Auto-restored button counter example.\n' 
                         'from hal import Pin, reset\n'
                         'from time import sleep_ms\n' 
                         'from pin_values import code_ok_pin_value, code_debug_pin_value\n' 
                         'def run(env):\n' 
                         '    oled = env.get("oled")\n' 
                         '    ok_button = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)\n' 
                         '    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)\n' 
                         '    if oled:\n' 
                         '        oled.fill(0)\n' 
                         '        oled.text("Button Counter", 0, 0)\n' 
                         '        oled.text("Press OK", 0, 20)\n' 
                         '        oled.show()\n' 
                         '    count = 0\n' 
                         '    while True:\n' 
                         '        if menu_button.value() == 0:\n' 
                         '            return\n' 
                         '        if ok_button.value() == 0:\n' 
                         '            count += 1\n' 
                         '            if oled:\n' 
                         '                oled.fill(0)\n' 
                         '                oled.text(f"Pressed: {count}", 0, 20)\n' 
                         '                oled.show()\n' 
                         '            while ok_button.value() == 0:\n' 
                         '                sleep_ms(20)\n' 
                         '        sleep_ms(50)\n'))
        except Exception:
            pass

# Wipe custom code (except preserved examples)
def _wipe_custom_code():
    try:
        for fn in _list_custom_code():
            if fn in PRESERVE_CUSTOM_CODE:
                continue
            try:
                os.remove(fn)
            except Exception:
                pass
    except Exception:
        pass
    _ensure_example()

# Execute a selected script (reload each time)
def _run_script(filename, env):
    name = filename[:-3]
    try:
        if name in sys.modules:
            sys.modules.pop(name)
    except Exception:
        pass
    try:
        mod = __import__(name)
        if hasattr(mod, 'run'):
            mod.run(env)
        else:
            print('No run(env) in', filename)
            oled = env.get('oled')
            if oled:
                upside_down = env.get('upside_down', False)
                oled.fill(0)
                _text(oled, "Error in:", 0, 0, upside_down)
                _text(oled, filename, 0, 12, upside_down)
                _text(oled, "No run() found", 0, 24, upside_down)
                _text(oled, "Press OK", 0, 48, upside_down)
                oled.show()
                ok_button = env.get('ok_button')
                if ok_button:
                    while ok_button.value() == 0: sleep_ms(20) # Wait for release
                    while ok_button.value() != 0: sleep_ms(20) # Wait for press
                    while ok_button.value() == 0: sleep_ms(20) # Wait for release

    except Exception as e:
        print(e) # Print full traceback to console
        print('Error executing', filename, e)
        oled = env.get('oled')
        if oled:
            upside_down = env.get('upside_down', False)
            oled.fill(0)
            _text(oled, "Error in:", 0, 0, upside_down)
            _text(oled, filename, 0, 12, upside_down)
            
            error_str = str(e)
            if len(error_str) > 16:
                _text(oled, error_str[:16], 0, 24, upside_down)
                if len(error_str) > 32:
                    _text(oled, error_str[16:32], 0, 36, upside_down)
                else:
                    _text(oled, error_str[16:], 0, 36, upside_down)
            else:
                _text(oled, error_str, 0, 24, upside_down)

            _text(oled, "Press OK", 0, oled.height - 10, upside_down)
            oled.show()
            ok_button = env.get('ok_button')
            if ok_button:
                while ok_button.value() == 0: sleep_ms(20) # Wait for release
                while ok_button.value() != 0: sleep_ms(20) # Wait for press
                while ok_button.value() == 0: sleep_ms(20) # Wait for release

# Helper to render text respecting upside_down

def _text(oled, s, x, y, upside_down=False):
    if not oled: return
    if hasattr(oled, 'text'):
        if upside_down:
            oled.text(s, oled.width - (x + len(s)*8), oled.height - (y + 8), 1)
        else:
            oled.text(s, x, y)

def _reinit_buttons():
    """(Re)initialize button pins. Safe if hardware absent."""
    global code_debug_pin, code_ok_pin
    try:
        code_debug_pin = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)
        code_ok_pin = Pin(code_ok_pin_value, Pin.IN, Pin.PULL_UP)
    except Exception:
        pass

# Initial creation
_reinit_buttons()

# (Remove fixed MENU_ITEMS; build dynamically in open_menu)
MENU_FOOTER = "OP=Down,OK=Yes"


def _render_menu(oled, items, idx, debug=False, upside_down=False):
    if oled is None:
        print("--- MENU ---")
        window_size = 4
        start = 0
        if len(items) > window_size:
            # Try to center selection
            start = max(0, min(idx - window_size // 2, len(items) - window_size))
        view = items[start:start+window_size]
        for i, item in enumerate(view):
            global_index = start + i
            prefix = ">" if global_index == idx else " "
            if item["type"] == "toggle":
                state = "ON" if settings_store.is_muted() else "OFF"
                print(f"{prefix} {item['name']}: {state}")
            else:
                print(f"{prefix} {item['name']}")
        if start > 0:
            print("(↑ more)")
        if start + window_size < len(items):
            print("(↓ more)")
        return
    try:
        oled.fill(0)
        window_size = 4  # lines available between header and footer
        if len(items) <= window_size:
            start = 0
        else:
            start = max(0, min(idx - window_size // 2, len(items) - window_size))
        footer = MENU_FOOTER
        # Prepare slice
        slice_items = items[start:start+window_size]
        lines = []
        for i, item in enumerate(slice_items):
            global_index = start + i
            marker = ">" if global_index == idx else " "
            if item["type"] == "toggle":
                state = "ON" if settings_store.is_muted() else "OFF"
                line = f"{marker}{item['name']}:{state}"
            else:
                line = f"{marker}{item['name']}"
            lines.append(line[:16])
        # Indicators for overflow
        up_indicator = start > 0
        down_indicator = (start + window_size) < len(items)
        if upside_down:
            _text(oled, footer, 0, oled.height - 10, True)
            base_y = oled.height - 20
            for line in reversed(lines):
                _text(oled, line, 0, base_y, True)
                base_y -= 10
            _text(oled, "Settings", 0, 0, True)
            if up_indicator:
                _text(oled, "^", oled.width - 8, 0, True)
            if down_indicator:
                _text(oled, "v", oled.width - 8, oled.height - 10, True)
        else:
            _text(oled, "Menu", 0, 0, False)
            for i, line in enumerate(lines):
                _text(oled, line, 0, 12 + i * 10, False)
            _text(oled, footer, 0, oled.height - 10, False)
            if up_indicator:
                _text(oled, "^", oled.width - 8, 0, False)
            if down_indicator:
                _text(oled, "v", oled.width - 8, oled.height - 10, False)
        if debug:
            _text(oled, "DBG", oled.width - 28, 0, upside_down)
        oled.show()
    except Exception:
        pass

def _display_ids(oled, upside_down, ok_button):
    user_name = settings_store._settings.get('user_name', 'User')
    sidekick_name = settings_store._settings.get('sidekick_name', 'Sidekick')
    sidekick_id = settings_store._settings.get('sidekick_id', 'Sidekick')

    if oled:
        oled.fill(0)
        _text(oled, "User:", 0, 0, upside_down)
        _text(oled, user_name, 0, 12, upside_down)
        _text(oled, "Sidekick:", 0, 24, upside_down)
        _text(oled, sidekick_name, 0, 36, upside_down)
        _text(oled, f"Sidekick ID:{sidekick_id}", 0, 44, upside_down)
        _text(oled, "Press OK", 0, oled.height - 10, upside_down)
        oled.show()
    else:
        print(f"User: {user_name}")
        print(f"Sidekick: {sidekick_name}")
        print(f"Sidekick ID: {sidekick_id}")
        print("Press OK to exit")

    if ok_button:
        while ok_button.value() == 0: sleep_ms(20) # Wait for release
        while ok_button.value() != 0: sleep_ms(20) # Wait for press
        while ok_button.value() == 0: sleep_ms(20) # Wait for release


def open_menu(oled=None, debug_mode=False, upside_down=False, called_from_main=True, env=None):
    _reinit_buttons()  # ensure fresh button objects each time menu opens
    print("Now in menu mode")
    has_custom = _custom_core_available()
    if not has_custom and settings_store.get_core_type() != 'Default':
        pass
    core_label = settings_store.get_core_type() if has_custom else 'Default'
    base_items = [
        {"name": f"Mute", "key": "mute", "type": "toggle"},
        {"name": f"Core: {core_label}", "key": "core", "type": "action"},
        {"name": "See IDs", "key": "sidekick_id", "type": "action"},
        {"name": "Run Custom Apps", "key": "exec", "type": "action"},
        {"name": "Wipe Extra Apps", "key": "wipe_custom", "type": "action"},
        {"name": "Start Web Server", "key": "start_web_server", "type": "action"},
        {"name": "Reset Settings", "key": "reset", "type": "action"},
    ]
    if called_from_main:
        base_items.append({"name": "Go Back", "key": "exit", "type": "action"})
    else:
        base_items.extend([
            {"name": "Go Back", "key": "back", "type": "action"},
            {"name": "Exit to Main", "key": "exit", "type": "action"},
        ])
    menu_items = base_items
    selected = 1 if len(menu_items) > 1 else 0
    while True:
        display_core = settings_store.get_core_type() if has_custom else 'Default'
        for it in menu_items:
            if it.get('key') == 'core':
                it['name'] = f"Core: {display_core}"
        _render_menu(oled, menu_items, selected, debug_mode, upside_down)
        # DOWN / UP navigation: short press = down, long press (>=450ms) = up
        if code_debug_pin.value() == 0:
            t0 = ticks_ms()
            long = False
            while code_debug_pin.value() == 0:
                if ticks_diff(ticks_ms(), t0) >= 450:
                    long = True
                sleep_ms(25)
            if long:
                selected = (selected - 1) % len(menu_items)
            else:
                selected = (selected + 1) % len(menu_items)
        # Select / activate
        if code_ok_pin.value() == 0:
            sleep_ms(20)
            if code_ok_pin.value() == 0:
                item = menu_items[selected]
                if item['key'] == 'mute':
                    settings_store.toggle_mute()
                elif item['key'] == 'core':
                    if has_custom:
                        settings_store.toggle_core_type()
                        oled_functions.reload_core()
                elif item['key'] == 'sidekick_id':
                    _display_ids(oled, upside_down, env.get('ok_button'))
                elif item['key'] == 'exec':
                    result = _execute_code_menu(oled, debug_mode, upside_down, env)
                    if result == 'home':
                        return 'exit'
                elif item['key'] == 'wipe_custom':
                    _wipe_custom_code()
                elif item['key'] == 'start_web_server':
                    import web_server
                    web_server.start_web_server(oled, upside_down)
                elif item['key'] == 'reset':
                    settings_store.reset_settings()
                    import sys
                    reset()
                elif item['key'] in ('exit','back'):
                    while code_ok_pin.value()==0:
                        sleep_ms(15)
                    return item['key']
                while code_ok_pin.value()==0:
                    sleep_ms(15)
        sleep_ms(35)

# Updated execute submenu with Back & Home, up/down nav and upside_down passed in env
def _execute_code_menu(oled, debug_mode, upside_down, env):
    _reinit_buttons()
    _ensure_example()
    all_scripts = _list_custom_code()
    
    try:
        try:
            s = os.statvfs('/')
            free_kb = (s[0] * s[3]) // 1024
        except Exception:
            free_kb = 0
        storage_str = f'{free_kb}KB'
    except Exception:
        storage_str = ''

    deletable_scripts = [s for s in all_scripts if s not in PRESERVE_CUSTOM_CODE]
    preserved_scripts = [s for s in all_scripts if s in PRESERVE_CUSTOM_CODE]
    
    CONTROL = ['<  Back', '<< Home']
    idx = 0
    while True:
        total_list = deletable_scripts + preserved_scripts + CONTROL
        window_size = 4
        if len(total_list) <= window_size:
            start = 0
        else:
            start = max(0, min(idx - window_size // 2, len(total_list) - window_size))
        view = total_list[start:start+window_size]
        try:
            if oled:
                oled.fill(0)
                _text(oled, 'Apps', 0, 0, upside_down)
                if storage_str:
                    storage_x = oled.width - len(storage_str) * 8
                    _text(oled, storage_str, storage_x, 0, upside_down)

                for i, entry in enumerate(view):
                    global_index = start + i
                    marker = '>' if global_index == idx else ' '
                    label = entry if entry in CONTROL else entry.replace('custom_code_','')[:-3]
                    _text(oled, (marker+label)[:16], 0, 12 + i*10, upside_down)
                # Scroll indicators
                if start > 0:
                    _text(oled, '^', oled.width - 8, 0, upside_down)
                if (start + window_size) < len(total_list):
                    _text(oled, 'v', oled.width - 8, oled.height - 10, upside_down)
                _text(oled, 'OP=Down,OK=Yes', 0, oled.height - 10, upside_down)
                oled.show()
            else:
                print('--- EXECUTE ---')
                for i, entry in enumerate(view):
                    global_index = start + i
                    pref = '>' if global_index == idx else ' '
                    print(pref, entry)
                if start > 0: print('(↑ more)')
                if (start + window_size) < len(total_list): print('(↓ more)')
        except Exception:
            pass
        # Navigation
        if code_debug_pin.value()==0:
            t0 = ticks_ms(); long=False
            while code_debug_pin.value()==0:
                if ticks_diff(ticks_ms(), t0) >= 450: long=True
                sleep_ms(25)
            idx = (idx - 1) % len(total_list) if long else (idx + 1) % len(total_list)
        if code_ok_pin.value()==0:
            sleep_ms(20)
            if code_ok_pin.value()==0:
                sel = total_list[idx]
                if sel == '<  Back':
                    while code_ok_pin.value()==0: sleep_ms(15)
                    _reinit_buttons()
                    return 'back'
                if sel == '<< Home':
                    while code_ok_pin.value()==0: sleep_ms(15)
                    _reinit_buttons()
                    return 'home'
                try:
                    env_full = env.copy() if env else {}
                    env_full.update({
                        'oled': env.get('oled') if env else oled,
                        'mpu': env.get('mpu') if env else None,
                        'i2c': env.get('i2c') if env else None, # Pass i2c bus
                        'menu_button': code_debug_pin,
                        'ok_button': code_ok_pin,
                        'settings': settings_store,
                        'Pin': Pin,
                        'upside_down': upside_down,
                    })
                except Exception:
                    env_full = {'oled': oled, 'menu_button': code_debug_pin, 'ok_button': code_ok_pin, 'upside_down': upside_down}
                _run_script(sel, env_full)
                while code_ok_pin.value()==0: sleep_ms(15)
                _reinit_buttons()  # refresh buttons after user script returns
        # Exit combo (both buttons) remains for emergency escape
        if code_debug_pin.value()==0 and code_ok_pin.value()==0:
            hold = 0
            while code_debug_pin.value()==0 and code_ok_pin.value()==0 and hold < 600:
                sleep_ms(30); hold += 30
            if hold >= 600:
                while code_debug_pin.value()==0 or code_ok_pin.value()==0: sleep_ms(15)
                return 'back'
        sleep_ms(35)