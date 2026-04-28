try:
    import network
except ImportError:
    pass
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio
import time
import binascii
import os
import json
import sys
import io

import settings_store
from hal import Pin, reset
from pin_values import code_debug_pin_value
from menu import get_preserved_files
from oled_functions import update_oled

# --- Globals --- #
_app_runner = None
_oled = None
_upside_down = False

class AppRunner:
    def __init__(self, env):
        self.task = None
        self.logs = io.StringIO()
        self.original_stdout = sys.stdout
        self.env = env

    def is_running(self):
        return self.task is not None and not self.task.done()

    def get_logs(self):
        return self.logs.getvalue()

    def start(self, filename):
        if self.is_running():
            return False
        
        self.logs = io.StringIO()
        sys.stdout = self.logs
        self.task = asyncio.create_task(self._run_app(filename))
        return True

    async def _run_app(self, filename):
        try:
            module_name = filename[:-3]
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            module = __import__(module_name)
            if hasattr(module, 'run'):
                module.run(self.env)
            else:
                print(f"Error: {filename} has no run(env) function.")
        except Exception as e:
            print(f"App Error: {e}")
        finally:
            self.stop()

    def stop(self):
        if self.task:
            self.task.cancel()
            self.task = None
        sys.stdout = self.original_stdout

async def handle_request(reader, writer):
    try:
        request_line = await reader.readline()
        if not request_line or request_line == b'\r\n': return

        method, path, _ = request_line.decode().split()
        headers = {}
        while True:
            line = await reader.readline()
            if not line or line == b'\r\n': break
            key, value = line.decode().split(':', 1)
            headers[key.strip().lower()] = value.strip()

        body = None
        if 'content-length' in headers:
            body = await reader.readexactly(int(headers['content-length']))

        if path == '/':
            await writer.awrite(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nCache-Control: no-cache\r\n\r\n')
            with open('sidekick-setup.html', 'rb') as f:
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    await writer.awrite(chunk)
        elif path == '/api/apps' and method == 'GET':
            preserved = get_preserved_files()
            apps = [{'name': f, 'preserved': f in preserved} for f in os.listdir('custom_code') if f.endswith('.py')]
            await writer.awrite(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n')
            await writer.awrite(json.dumps(apps).encode())
        elif path == '/api/apps' and method == 'POST':
            data = json.loads(body)
            filename = data.get('name')
            if filename in get_preserved_files():
                await writer.awrite(b'HTTP/1.1 403 Forbidden\r\n\r\nCannot modify preserved file.')
            elif filename and filename.startswith('custom_code_') and filename.endswith('.py'):
                with open(f'custom_code/{filename}', 'w') as f:
                    f.write(data.get('code', ''))
                await writer.awrite(b'HTTP/1.1 201 Created\r\n\r\n')
            else:
                await writer.awrite(b'HTTP/1.1 400 Bad Request\r\n\r\nInvalid filename.')
        elif path == '/codejar.min.js':
            with open('codejar.min.js', 'rb') as f:
                await writer.awrite(b'HTTP/1.1 200 OK\r\nContent-Type: application/javascript\r\n\r\n')
                await writer.awrite(f.read())
        elif path == '/api/status' and method == 'GET':
            status = {
                "setup_completed": settings_store._settings.get('setup_completed', False),
                "user_name": settings_store._settings.get('user_name', 'User'),
                "sidekick_name": settings_store._settings.get('sidekick_name', 'Sidekick'),
            }
            await writer.awrite(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n')
            await writer.awrite(json.dumps(status).encode())
        elif path == '/save' and method == 'POST':
            data = {k: v for k, v in [pair.split('=', 1) for pair in body.decode().split('&') if '=' in pair]}
            
            settings_store._settings['user_name'] = data.get('user_name', 'User')
            settings_store._settings['sidekick_name'] = data.get('sidekick_name', 'Sidekick')
            settings_store._settings['setup_completed'] = True
            settings_store._save()

            await writer.awrite(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n')
            await writer.awrite(json.dumps({'status': 'success'}).encode())
            finish()
        elif path.startswith('/api/app/'):
            filename = path.split('/')[-1]
            if method == 'GET':
                with open(f'custom_code/{filename}', 'r') as f: content = f.read()
                await writer.awrite(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n' + content.encode())
            elif method == 'DELETE':
                if filename in get_preserved_files():
                    await writer.awrite(b'HTTP/1.1 403 Forbidden\r\n\r\nCannot delete preserved file.')
                else:
                    os.remove(f'custom_code/{filename}')
                    await writer.awrite(b'HTTP/1.1 204 No Content\r\n\r\n')
        elif path == '/api/run' and method == 'POST':
            filename = json.loads(body).get('name')
            if not _app_runner.is_running() and filename:
                _app_runner.start(f'custom_code/{filename}')
                await writer.awrite(b'HTTP/1.1 200 OK\r\n\r\n')
            else:
                await writer.awrite(b'HTTP/1.1 409 Conflict\r\n\r\nApp already running.')
        elif path == '/api/stop' and method == 'POST':
            if _app_runner.is_running(): _app_runner.stop()
            await writer.awrite(b'HTTP/1.1 200 OK\r\n\r\n')
        elif path == '/api/logs' and method == 'GET':
            await writer.awrite(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n' + _app_runner.get_logs().encode())
        elif path == '/api/reset' and method == 'POST':
            settings_store.reset_settings()
            reset()
            await writer.awrite(b'HTTP/1.1 200 OK\r\n\r\n')
        else:
            await writer.awrite(b'HTTP/1.1 404 Not Found\r\n\r\n')
    except Exception as e:
        print(f"Request Error: {e}")
    finally:
        await writer.aclose()

async def main(oled, upside_down):
    global _app_runner, _oled, _upside_down
    _oled = oled
    _upside_down = upside_down

    env = {
        'oled': oled,
        'upside_down': upside_down,
        'settings': settings_store,
        'Pin': Pin,
        'i2c': None, 
        'mpu': None, 
    }
    _app_runner = AppRunner(env)

    try:
        import wifi
        password = settings_store.get_ap_password()
        sidekick_id = settings_store.get_sidekick_id()
        ssid = f"Sidekick_{sidekick_id}"
        wifi.radio.start_ap(ssid, password)
    except ImportError:
        # Fallback for simulator
        ssid = "Simulator_Web"
        password = "None"

    oled.fill(0)
    update_oled(oled, "text", "Web Server Mode", upside_down, line=1)
    update_oled(oled, "text", f"AP:{ssid}", upside_down, line=3)
    update_oled(oled, "text", f"Pass: {password}", upside_down, line=4)
    update_oled(oled, "text", f"192.168.4.1", upside_down, line=5)
    update_oled(oled, "text", "(Menu to Exit)", upside_down, line=6)
    oled.show()

    server = await asyncio.start_server(handle_request, '0.0.0.0', 80)
    menu_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)
    while True:
        if menu_button.value() == 0:
            break
        await asyncio.sleep_ms(100)
    
    server.close()
    await server.wait_closed()
    try:
        import wifi
        wifi.radio.stop_ap()
    except:
        pass

def finish():
    global _oled, _upside_down
    _oled.fill(0)
    update_oled(_oled, "text", "Setup Complete!", _upside_down, line=2)
    update_oled(_oled, "text", "Rebooting...", _upside_down, line=3)
    _oled.show()
    time.sleep(2) # Give time to display message
    reset()

def start_web_server(oled, upside_down):
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main(oled, upside_down))
    except Exception as e:
        print(f"Web server error: {e}")
    finally:
        # This is important to allow the event loop to be reused.
        asyncio.new_event_loop()
        # Add the hack here
        from hal import reset
        from oled_functions import update_oled
        from time import sleep_ms

        oled.fill(0)
        update_oled(oled, "text", "Saving Settings...", upside_down, line=2)
        oled.show()
        sleep_ms(1000) # Give time to display message and save settings
        reset()
