from PIL import Image
import flet as ft
import threading
import sys
import os
import yaml
import subprocess
import time
import base64
from io import BytesIO


# Import the simulator dependencies early
# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from hal import hal

def run_bot_loop():
    try:
        import main as bot_main
        bot_main.main_loop()
    except Exception as e:
        print(f"Bot failed to start: {e}")

def main(page: ft.Page):
    page.title = "MakerSidekick Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 400
    page.window_height = 800

    # -------------------------
    # Simulator State & UI
    # -------------------------
    oled_image = ft.Image(src_base64="", width=256, height=128, fit=ft.BoxFit.CONTAIN)

    def update_oled():
        if hal.oled and getattr(hal.oled, '_updated', False):
            hal.oled._updated = False
            # Convert raw 1-bit buffer to image
            w, h = 128, 64
            img = Image.new('1', (w, h))
            pixels = img.load()
            for y in range(h):
                for x in range(w):
                    idx = (y // 8) * w + x
                    val = (hal.oled.buffer[idx] >> (y % 8)) & 1
                    pixels[x, y] = 1 if val else 0

            # Scale up for visibility
            img = img.resize((256, 128), Image.Resampling.NEAREST)
            buf = BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            oled_image.src_base64 = b64
            page.update()

    def simulator_loop():
        while True:
            update_oled()
            time.sleep(0.05)

    # Load buttons from yaml
    try:
        with open('hardware.yaml', 'r') as f:
            hw = yaml.safe_load(f)
    except Exception:
        hw = {'pins': {'button_1': 1, 'button_2': 0}}

    controls = []
    def btn_down(pin_num):
        hal.get_button(pin_num).set_value(0)
    def btn_up(pin_num):
        hal.get_button(pin_num).set_value(1)

    for name, pin in hw.get('pins', {}).items():
        if 'button' in name.lower():
            btn = ft.ElevatedButton(
                text=name,
                on_click=lambda e: None,
            )
            # Flet doesn't have native on_mouse_down/up easily without GestureDetector on container.
            # Using simple toggle for mock instead or GestureDetector:
            controls.append(
                ft.GestureDetector(
                    content=ft.ElevatedButton(name),
                    on_tap_down=lambda e, p=pin: btn_down(p),
                    on_tap_up=lambda e, p=pin: btn_up(p),
                    on_pan_end=lambda e, p=pin: btn_up(p)
                )
            )

    # --- Simulator Tab ---
    # --- Simulator Tab ---
    def toggle_web_server(e):
        import web_server
        # We start the web server loop in background.
        # Hal uses Mock if ON_DEVICE is false.
        import asyncio
        import threading

        def run_web():
            try:
                web_server.start_web_server(hal.oled, False)
            except Exception as ex:
                print("Web Server Error:", ex)

        threading.Thread(target=run_web, daemon=True).start()
        e.control.text = "Web Server Started on port 80"
        e.control.disabled = True
        e.control.update()

    sim_content = ft.Column(
        [
            ft.Text("Simulator", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Container(
                content=oled_image,
                width=256,
                height=128,
                bgcolor=ft.colors.BLACK,
                alignment=ft.alignment.center,
                border=ft.border.all(1, ft.colors.WHITE),
            ),
            ft.Text("Controls:"),
            ft.Row(controls, alignment=ft.MainAxisAlignment.CENTER),
            ft.Text("Shake Sensor Simulator (ADXL345):"),
            ft.ElevatedButton("Simulate Shake", on_click=lambda e: setattr(hal, 'sim_shake', True)),
            ft.Text("Web Preview:"),
            ft.ElevatedButton("Start Local Web Server", on_click=toggle_web_server)
        ],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True
    )

    # ... keep flash and design tabs simple for now

    def flash_device(e):
        try:
            subprocess.Popen(["pixi", "run", "fulldev"])
            e.control.text = "Flashing started!"
            e.control.update()
        except Exception as ex:
            e.control.text = f"Error: {ex}"
            e.control.update()

    flash_content = ft.Column(
        [
            ft.Text("Flash to ESP32", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.ElevatedButton("Upload & Run (fulldev)", on_click=flash_device)
        ],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True
    )

    # --- Design Tab ---
    def update_json(e):
        try:
            with open("custom_core.json", "w") as f:
                f.write(json_editor.value)

            # Hot reload in simulator
            from personality import personality
            personality.reload()

            e.control.text = "Saved & Reloaded!"
        except Exception as ex:
            e.control.text = f"Error: {ex}"
        e.control.update()

    try:
        with open("custom_core.json", "r") as f:
            current_json = f.read()
    except:
        current_json = """{\n  "faces": {},\n  "sounds": {}\n}"""

    json_editor = ft.TextField(
        value=current_json,
        multiline=True,
        min_lines=15,
        max_lines=25,
        text_size=12,
        expand=True
    )

    design_content = ft.Column(
        [
            ft.Text("Design Faces & Sounds", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            json_editor,
            ft.ElevatedButton("Save to custom_core.json", on_click=update_json)
        ],
        alignment=ft.MainAxisAlignment.START,
        expand=True
    )


    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="Simulator", content=sim_content),
            ft.Tab(text="Flash", content=flash_content),
            ft.Tab(text="Design", content=design_content),
        ],
        expand=1,
    )

    page.add(tabs)

    # Start background threads
    threading.Thread(target=simulator_loop, daemon=True).start()
    threading.Thread(target=run_bot_loop, daemon=True).start()

if __name__ == "__main__":
    ft.app(target=main)
