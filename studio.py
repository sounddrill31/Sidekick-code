from PIL import Image
import flet as ft
import threading
import sys
import os
import yaml
import subprocess
import time
import base64
import webbrowser
import json
import random
import math
from io import BytesIO

# Import the simulator dependencies early
from hal import hal

def run_bot_loop():
    try:
        import main as bot_main
        bot_main.main_loop()
    except Exception as e:
        print(f"Bot failed to start: {e}")

def main(page: ft.Page):
    page.title = "MakerSidekick Studio - Lab"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1200
    page.window_height = 900
    page.padding = 0
    page.spacing = 0

    # -------------------------
    # State & Config
    # -------------------------
    if hal.oled is None:
        from hal import OledMock
        hal.oled = OledMock()
        
    SIM_PORT = 8080
    initial_w, initial_h = hal.oled.width * 2, hal.oled.height * 2
    oled_image = ft.Image(src="", width=initial_w, height=initial_h, fit=ft.BoxFit.CONTAIN)
    
    # Load hardware config
    try:
        with open('hardware.yaml', 'r') as f:
            hw = yaml.safe_load(f)
    except Exception:
        hw = {'pins': {'button_1': 1, 'button_2': 0, 'led': 1, 'buzzer': 8}}

    # -------------------------
    # UI Helpers
    # -------------------------
    def notify(text):
        sb = ft.SnackBar(content=ft.Text(text))
        page.overlay.append(sb)
        sb.open = True
        page.update()

    # -------------------------
    # Simulator Pane Components
    # -------------------------
    oled_display = ft.Container(
        content=oled_image,
        width=initial_w + 20,
        height=initial_h + 20,
        bgcolor=ft.Colors.BLACK,
        alignment=ft.Alignment(0, 0),
        border=ft.Border.all(4, ft.Colors.GREY_900),
        border_radius=10,
        padding=10
    )

    hw_controls = ft.Column(spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    buttons_row = ft.Row(wrap=True, alignment=ft.MainAxisAlignment.CENTER, spacing=15)
    
    led_indicator = ft.Container(width=30, height=30, border_radius=15, bgcolor=ft.Colors.GREY_800, border=ft.Border.all(2, ft.Colors.WHITE24))
    buzzer_indicator = ft.Icon(icon=ft.Icons.VOLUME_MUTE, color=ft.Colors.GREY_800, size=30)

    btn_labels = {hw.get('pins', {}).get('button_1'): "MENU", hw.get('pins', {}).get('button_2'): "OK"}

    def create_hw_button(name, pin_val):
        btn_name = btn_labels.get(pin_val, name.replace('button_','').upper())
        btn_container = ft.Container(content=ft.Text(btn_name, weight=ft.FontWeight.BOLD), bgcolor=ft.Colors.BLUE_GREY_800, padding=20, border_radius=15, border=ft.Border.all(2, ft.Colors.BLUE_GREY_400))
        def handle_down(e): hal.get_button(pin_val).set_value(0); btn_container.bgcolor = ft.Colors.BLUE_GREY_600; btn_container.update()
        def handle_up(e): hal.get_button(pin_val).set_value(1); btn_container.bgcolor = ft.Colors.BLUE_GREY_800; btn_container.update()
        return ft.GestureDetector(content=btn_container, on_tap_down=handle_down, on_tap_up=handle_up, on_tap_cancel=handle_up, on_pan_end=handle_up, mouse_cursor=ft.MouseCursor.CLICK)

    for name, pin in hw.get('pins', {}).items():
        if 'button' in name.lower():
            try: buttons_row.controls.append(create_hw_button(name, int(pin)))
            except: pass

    display_flipped = [True]
    def toggle_flip(e):
        display_flipped[0] = not display_flipped[0]
        e.control.text = "Orientation: Hardware" if display_flipped[0] else "Orientation: upright"
        try: import main as bot_main; bot_main.UPSIDE_DOWN = display_flipped[0]
        except: pass
        e.control.update()

    hw_controls.controls.extend([
        ft.ElevatedButton("Orientation: Hardware", icon=ft.Icons.SCREEN_ROTATION, on_click=toggle_flip),
        ft.Divider(height=1, color=ft.Colors.WHITE10),
        ft.Text("Device Controls", size=18, weight=ft.FontWeight.BOLD),
        buttons_row,
        ft.Row([ft.Column([ft.Text("LED"), led_indicator], horizontal_alignment="center"), ft.Column([ft.Text("Buzzer"), buzzer_indicator], horizontal_alignment="center")], alignment="center", spacing=50),
        ft.ElevatedButton("Simulate Shake", icon=ft.Icons.VIBRATION, on_click=lambda e: setattr(hal, 'sim_shake', True))
    ])

    # -------------------------
    # Dashboard Pane
    # -------------------------
    db_status_text = ft.Text("OFFLINE", color=ft.Colors.RED_400, weight="bold", size=20)
    open_db_btn = ft.ElevatedButton("Open in Browser", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda e: webbrowser.open(f"http://localhost:{SIM_PORT}"), disabled=True)

    def handle_start_server(e):
        threading.Thread(target=lambda: (importlib.import_module('web_server').start_web_server(hal.oled, False, port=SIM_PORT)), daemon=True).start()
        db_status_text.value = "ONLINE"; db_status_text.color = ft.Colors.GREEN_400; open_db_btn.disabled = False; e.control.disabled = True; page.update()
    
    import importlib # for the lambda above

    dashboard_pane = ft.Column([
        ft.Text("Sidekick Dashboard", size=28, weight="bold"),
        ft.Container(height=30),
        ft.Row([ft.Text("Status: "), db_status_text], alignment="center"),
        ft.Container(height=20),
        open_db_btn,
        ft.ElevatedButton("Start Web Server", icon=ft.Icons.PLAY_ARROW, on_click=handle_start_server),
        ft.Container(height=30),
        ft.Divider(color=ft.Colors.WHITE24),
    ], expand=True, horizontal_alignment="center", alignment="center")

    # -------------------------
    # Creative Lab (Composer)
    # -------------------------
    
    # 1. Sound Synth Component
    # 8-step sequencer
    steps_freq = [ft.Slider(min=0, max=5000, value=random.randint(500, 2000), label="{value}Hz", expand=True) for _ in range(8)]
    steps_dur = [ft.Slider(min=10, max=500, value=50, label="{value}ms", expand=True) for _ in range(8)]
    
    def play_synth(e):
        sequence = []
        for f, d in zip(steps_freq, steps_dur):
            if f.value > 0:
                sequence.append([int(f.value), int(d.value)])
        
        # Inject into Bot's audio system if possible
        try:
            from buzzer_sounds import audio_mgr
            # Directly override current sequence for testing
            audio_mgr.current_sequence = sequence
            audio_mgr.sequence_index = 0
            audio_mgr.playing = True
            audio_mgr._start_current_note()
            notify("Synth Sequence Playing!")
        except Exception as ex:
            notify(f"Synth Error: {ex}")

    def randomize_synth(e):
        base_f = random.randint(400, 1000)
        mode = random.choice(["major", "minor", "sci-fi", "robot"])
        for i in range(8):
            if mode == "robot": steps_freq[i].value = random.choice([0, 1000, 2000, 3000, 4000])
            elif mode == "sci-fi": steps_freq[i].value = base_f + int(math.sin(i)*500)
            else: steps_freq[i].value = base_f + (i * 200)
            steps_dur[i].value = random.randint(20, 150)
        page.update()

    synth_grid = ft.Column([
        ft.Text("8-Step Wave Synth", size=20, weight="bold"),
        ft.Row([ft.Column([steps_freq[i], steps_dur[i]], expand=True) for i in range(8)], height=200),
        ft.Row([
            ft.ElevatedButton("Play Synth", icon=ft.Icons.PLAY_ARROW, on_click=play_synth),
            ft.ElevatedButton("Randomize", icon=ft.Icons.AUTO_AWESOME, on_click=randomize_synth)
        ])
    ])

    # 2. Face Lab Component
    face_input = ft.TextField(value="(˶ᵔ ᵕ ᵔ˶)", label="ASCII Face", text_size=20, text_align="center")
    
    def inject_face(e):
        try:
            from oled_functions import render_face
            render_face(hal.oled, face_input.value, 0, display_flipped[0])
            notify("Face Injected to Display!")
        except Exception as ex:
            notify(f"Injection Error: {ex}")

    def randomize_face(e):
        eyes = ["o", "0", "-", "^", "v", ">", "x", "*"]
        mouths = ["_", ".", "o", "w", "u", "v"]
        e1, e2 = random.choice(eyes), random.choice(eyes)
        m = random.choice(mouths)
        face_input.value = f"({e1}{m}{e2})"
        page.update()

    face_lab = ft.Column([
        ft.Text("Expression Lab", size=20, weight="bold"),
        face_input,
        ft.Row([
            ft.ElevatedButton("Inject Face", icon=ft.Icons.INPUT, on_click=inject_face),
            ft.ElevatedButton("Randomize", icon=ft.Icons.AUTO_AWESOME, on_click=randomize_face)
        ])
    ])

    # 3. Emotion Mixer (Save to JSON)
    mood_name = ft.Dropdown(
        options=[ft.dropdown.Option(m) for m in ["happy", "sad", "angry", "curious", "scared", "eepy"]],
        value="happy",
        label="Target Emotion"
    )

    def save_to_core(e):
        try:
            sequence = [[int(f.value), int(d.value)] for f, d in zip(steps_freq, steps_dur) if f.value > 0]
            face = face_input.value
            
            with open("custom_core.json", "r") as f: data = json.load(f)
            if "faces" not in data: data["faces"] = {}
            if "sounds" not in data: data["sounds"] = {}
            
            # Map mood to face and sound
            data["faces"][mood_name.value] = [face]
            data["sounds"][f"{mood_name.value}_sound"] = {"sequence": sequence}
            
            with open("custom_core.json", "w") as f: json.dump(data, f, indent=2)
            
            # Reload personality in bot
            from personality import personality
            personality.reload()
            notify(f"Emotion '{mood_name.value}' Saved & Hot-Reloaded!")
        except Exception as ex:
            notify(f"Save Error: {ex}")

    mixer = ft.Column([
        ft.Text("Emotion Mixer", size=20, weight="bold"),
        ft.Row([mood_name, ft.ElevatedButton("Save to custom_core.json", icon=ft.Icons.SAVE, on_click=save_to_core)])
    ])

    lab_content = ft.Container(
        content=ft.Column([
            ft.Text("Sidekick Composer Lab", size=32, weight="bold", color=ft.Colors.AMBER_200),
            ft.Divider(),
            synth_grid,
            ft.Divider(),
            face_lab,
            ft.Divider(),
            mixer,
            ft.Container(height=20),
            ft.Text("Tips: Use 'Play Synth' to test audio and 'Inject Face' to see the OLED result before saving.", size=12, italic=True, color=ft.Colors.GREY_500)
        ], scroll="auto"),
        padding=40,
        expand=True
    )

    # -------------------------
    # Main Layout
    # -------------------------
    sim_view = ft.Row([
        ft.Container(content=ft.Column([ft.Text("Device Simulator", size=24, weight="bold", color=ft.Colors.BLUE_200), ft.Container(height=30), oled_display, ft.Container(height=30), hw_controls], horizontal_alignment="center", alignment="center"), expand=1, padding=40, bgcolor=ft.Colors.BLACK26, border_radius=20, margin=10),
        ft.Container(content=dashboard_pane, expand=1, padding=40, bgcolor=ft.Colors.BLACK26, border_radius=20, margin=10, border=ft.Border(left=ft.BorderSide(1, ft.Colors.WHITE10)))
    ], expand=True)

    main_content = ft.Container(content=sim_view, expand=True)

    def navigate(e):
        dest = sidebar.destinations[e.control.selected_index].data
        if dest == "sim": main_content.content = sim_view
        elif dest == "lab": main_content.content = lab_content
        elif dest == "flash": subprocess.Popen(["pixi", "run", "fulldev"])
        page.update()

    sidebar = ft.NavigationRail(
        selected_index=0, label_type="all", min_width=100, group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.DEVICES_OUTLINED, selected_icon=ft.Icons.DEVICES, label="Simulator", data="sim"),
            ft.NavigationRailDestination(icon=ft.Icons.MUSIC_NOTE_OUTLINED, selected_icon=ft.Icons.MUSIC_NOTE, label="Composer Lab", data="lab"),
            ft.NavigationRailDestination(icon=ft.Icons.BOLT, label="Flash", data="flash"),
        ],
        on_change=navigate
    )

    page.add(ft.Row([sidebar, ft.VerticalDivider(width=1), main_content], expand=True))

    # -------------------------
    # Loops
    # -------------------------
    def update_ui_loop():
        while True:
            if hal.oled and getattr(hal.oled, '_updated', False):
                hal.oled._updated = False
                w, h = hal.oled.width, hal.oled.height
                img = Image.new('1', (w, h))
                pixels = img.load()
                for y in range(h):
                    for x in range(w):
                        idx = (y // 8) * w + x
                        pixels[x, y] = 1 if (hal.oled.buffer[idx] >> (y % 8)) & 1 else 0
                display_w, display_h = w * 2, h * 2
                img = img.resize((display_w, display_h), Image.Resampling.NEAREST)
                buf = BytesIO(); img.save(buf, format="PNG")
                oled_image.src = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
                
                # Hardware Indicators
                led_p = hw.get('pins', {}).get('led')
                if led_p is not None:
                    on = hal.get_button(int(led_p)).value() == 1
                    led_indicator.bgcolor = ft.Colors.RED if on else ft.Colors.GREY_800
                    led_indicator.border = ft.Border.all(2, ft.Colors.RED_ACCENT if on else ft.Colors.WHITE24)
                
                bz_p = hw.get('pins', {}).get('buzzer')
                if bz_p is not None:
                    bz = hal.get_buzzer(int(bz_p))
                    active = hasattr(bz, '_freq') and bz._freq > 0 and bz._duty > 0
                    buzzer_indicator.icon = ft.Icons.VOLUME_UP if active else ft.Icons.VOLUME_MUTE
                    buzzer_indicator.color = ft.Colors.YELLOW if active else ft.Colors.GREY_800
                page.update()
            time.sleep(0.05)

    threading.Thread(target=update_ui_loop, daemon=True).start()
    threading.Thread(target=run_bot_loop, daemon=True).start()

if __name__ == "__main__":
    ft.app(main)
