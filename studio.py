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
import wave
import struct
from io import BytesIO
from PIL import Image

# Import the simulator dependencies early
from hal import hal

# -------------------------
# Audio Engine (Standard Wave)
# -------------------------
def generate_beep_wav(frequencies_durations):
    """Generates a WAV file in memory from a list of (freq, dur) pairs"""
    sample_rate = 22050
    buf = BytesIO()
    with wave.open(buf, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for freq, dur in frequencies_durations:
            num_samples = int(sample_rate * (dur / 1000.0))
            if freq > 0:
                for i in range(num_samples):
                    val = int(32767.0 * math.sin(2.0 * math.pi * freq * i / sample_rate))
                    wav_file.writeframesraw(struct.pack('<h', val))
            else:
                wav_file.writeframesraw(struct.pack('<h', 0) * num_samples)
    
    return base64.b64encode(buf.getvalue()).decode()

# -------------------------
# Bot Thread Management
# -------------------------
bot_thread = None
bot_stop_event = threading.Event()

def run_bot_loop():
    while True:
        try:
            if 'main' in sys.modules:
                del sys.modules['main']
            import main as bot_main
            bot_main.main_loop()
        except Exception as e:
            if str(e) == "SYSTEM_RESET":
                print("Simulator rebooting bot loop...")
                time.sleep(1)
                continue
            print(f"Bot failed to start: {e}")
            break

def main(page: ft.Page):
    page.title = "MakerSidekick Studio - Ultimate Lab"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1400
    page.window_height = 1000
    page.padding = 0
    page.spacing = 0

    # -------------------------
    # State & Config
    # -------------------------
    if hal.oled is None:
        from hal import OledMock
        hal.oled = OledMock()
        
    SIM_PORT = 8080
    
    try:
        with open('hardware.yaml', 'r') as f:
            hw = yaml.safe_load(f)
    except Exception:
        hw = {'pins': {'button_1': 1, 'button_2': 0, 'led': 1, 'buzzer': 8}}
    
    # Lab State
    lab_state = {
        "mood": "happy",
        "face_timeline": ["(˶ᵔ ᵕ ᵔ˶)"],
        "sound_timeline": [[1000, 100], [1500, 100], [2000, 200]],
        "threshold": 75
    }
    
    # Face Parts for Easy Building
    FACE_PARTS = {
        "eyes": ["^ ^", "o o", "O O", "x x", "> <", "- -", "v v", "* *", "@ @", ". .", "U U", "n n"],
        "mouths": ["_", ".", "o", "w", "u", "v", "O", "D", "P", "m", "~", "3"],
        "brows": ["None", "/ \\", "\\ /", "- -", "~ ~", "v v", "^ ^"]
    }

    # -------------------------
    # Helpers
    # -------------------------
    def notify(text, color=ft.Colors.AMBER_400):
        sb = ft.SnackBar(content=ft.Text(text, weight="bold"), bgcolor=color)
        page.overlay.append(sb)
        sb.open = True
        page.update()

    def safe_load_core():
        try:
            if not os.path.exists("custom_core.json"):
                return {"faces": {}, "sounds": {}}
            with open("custom_core.json", "r") as f:
                content = f.read().strip()
                if not content: return {"faces": {}, "sounds": {}}
                return json.loads(content)
        except Exception as e:
            print(f"Load Error: {e}")
            return {"faces": {}, "sounds": {}}

    # Audio player using subprocess
    import tempfile
    import subprocess

    # --- Sub-Snackbars ---
    face_status = ft.Text("", color=ft.Colors.GREEN_400, italic=True)
    audio_status = ft.Text("", color=ft.Colors.GREEN_400, italic=True)
    def notify_face(msg): face_status.value = msg; face_status.update()
    def notify_audio(msg): audio_status.value = msg; audio_status.update()

    # -------------------------
    # Composer Lab UI Refresh
    # -------------------------
    active_frame_idx = [0]
    active_note_idx = [0]

    trigger_event_dropdown = ft.Dropdown(
        label="Trigger Event",
        options=[ft.dropdown.Option("happiness"), ft.dropdown.Option("shake")],
        value="happiness",
        width=150,
        bgcolor=ft.Colors.BLACK26
    )
    
    trigger_condition_dropdown = ft.Dropdown(
        label="Condition",
        options=[ft.dropdown.Option("<="), ft.dropdown.Option(">="), ft.dropdown.Option("=="), ft.dropdown.Option("none")],
        value="<=",
        width=100,
        bgcolor=ft.Colors.BLACK26
    )
    
    trigger_value_input = ft.TextField(
        label="Value (e.g. 50%)",
        value="50",
        width=150,
        bgcolor=ft.Colors.BLACK26
    )

    def update_trigger_state(e):
        lab_state["behavior"] = {
            "event": trigger_event_dropdown.value,
            "condition": trigger_condition_dropdown.value,
            "value": int(trigger_value_input.value) if trigger_value_input.value.isdigit() else 0,
            "target_mood": lab_state["mood"],
            "duration": 3000
        }
        
    trigger_event_dropdown.on_change = update_trigger_state
    trigger_condition_dropdown.on_change = update_trigger_state
    trigger_value_input.on_change = update_trigger_state

    # Face Grid State
    grid_state = [[0]*32 for _ in range(8)]
    grid_btns = []

    def load_frame_to_grid(idx):
        active_frame_idx[0] = idx
        face_data = lab_state["face_timeline"][idx]
        is_pixel = isinstance(face_data, list)
        for r in range(8):
            for c in range(32):
                if is_pixel and r < len(face_data) and c < len(face_data[0]):
                    val = int(face_data[r][c])
                else:
                    val = 0
                grid_state[r][c] = val
                grid_btns[r][c].bgcolor = ft.Colors.WHITE if val else ft.Colors.BLACK
                grid_btns[r][c].update()

    is_dragging = [False]
    draw_tool = ["pen"]  # "pen" or "eraser"

    def set_pixel(r, c, val):
        grid_state[r][c] = val
        grid_btns[r][c].bgcolor = ft.Colors.WHITE if val else ft.Colors.BLACK
        grid_btns[r][c].update()

    def toggle_pixel(r, c):
        grid_state[r][c] = 1 - grid_state[r][c]
        grid_btns[r][c].bgcolor = ft.Colors.WHITE if grid_state[r][c] else ft.Colors.BLACK
        grid_btns[r][c].update()
        lab_state["face_timeline"][active_frame_idx[0]] = ["".join(map(str, row)) for row in grid_state]
        refresh_face_timeline()

    def set_tool(tool):
        draw_tool[0] = tool
        notify_face(f"Tool: {tool.upper()}")

    def paint_drag(e, r, c):
        if is_dragging[0]:
            tool = draw_tool[0]
            if tool == "pen":
                set_pixel(r, c, 1)
            elif tool == "eraser":
                set_pixel(r, c, 0)

    def on_drag_start(e):
        is_dragging[0] = True

    def on_drag_end(e):
        is_dragging[0] = False
        lab_state["face_timeline"][active_frame_idx[0]] = ["".join(map(str, row)) for row in grid_state]
        refresh_face_timeline()

    # Initialize Grid UI
    for r in range(8):
        row_btns = []
        for c in range(32):
            btn = ft.Container(
                width=20, height=20, bgcolor=ft.Colors.BLACK,
                border=ft.Border.all(1, ft.Colors.GREY_800),
            )
            btn.on_click = lambda e, r=r, c=c: toggle_pixel(r, c)
            btn.on_hover = lambda e, r=r, c=c: paint_drag(e, r, c)
            row_btns.append(btn)
        grid_btns.append(row_btns)

    def set_grid_state(new_state):
        for r in range(8):
            for c in range(32):
                grid_state[r][c] = new_state[r][c]
                grid_btns[r][c].bgcolor = ft.Colors.WHITE if grid_state[r][c] else ft.Colors.BLACK
                grid_btns[r][c].update()
        lab_state["face_timeline"][active_frame_idx[0]] = ["".join(map(str, row)) for row in grid_state]
        refresh_face_timeline()

    clipboard_grid = []
    def copy_grid(e):
        clipboard_grid.clear()
        for r in range(8): clipboard_grid.append(list(grid_state[r]))
        notify_face("Frame copied!")

    def shift_grid(dx, dy):
        new_state = [[0]*32 for _ in range(8)]
        for r in range(8):
            for c in range(32):
                nr = r - dy
                nc = c - dx
                if 0 <= nr < 8 and 0 <= nc < 32:
                    new_state[r][c] = grid_state[nr][nc]
        set_grid_state(new_state)

    drag_canvas = [None]

    grid_column = ft.Column([ft.Row(row, spacing=0) for row in grid_btns], spacing=0)
    drag_canvas[0] = ft.GestureDetector(
        content=grid_column,
        on_tap_down=on_drag_start,
        on_tap_up=on_drag_end,
        on_pan_end=on_drag_end,
        on_pan_start=on_drag_start,
        drag_interval=20
    )
    pixel_canvas = drag_canvas[0]

    pixel_toolbar = ft.Row([
        ft.IconButton(ft.Icons.EDIT, tooltip="Pen", icon_color=ft.Colors.GREEN_400, on_click=lambda e: set_tool("pen")),
        ft.IconButton(ft.Icons.AUTO_FIX_HIGH, tooltip="Eraser", on_click=lambda e: set_tool("eraser")),
        ft.VerticalDivider(),
        ft.IconButton(ft.Icons.COPY, tooltip="Copy Frame", on_click=copy_grid),
        ft.IconButton(ft.Icons.PASTE, tooltip="Paste Frame", on_click=lambda e: set_grid_state(clipboard_grid) if clipboard_grid else notify_face("Empty!")),
        ft.VerticalDivider(),
        ft.IconButton(ft.Icons.CLEAR, tooltip="Clear", icon_color=ft.Colors.RED_400, on_click=lambda e: set_grid_state([[0]*32 for _ in range(8)])),
        ft.IconButton(ft.Icons.FORMAT_PAINT, tooltip="Fill", on_click=lambda e: set_grid_state([[1]*32 for _ in range(8)])),
    ])

    # Audio Step Sequencer
    freq_sliders = []
    dur_sliders = []
    
    def update_audio_state(e, idx, is_freq):
        if idx < len(lab_state["sound_timeline"]):
            if is_freq:
                lab_state["sound_timeline"][idx][0] = int(e.control.value)
            else:
                lab_state["sound_timeline"][idx][1] = int(e.control.value)

    def rebuild_audio_sequencer():
        freq_sliders.clear()
        dur_sliders.clear()
        for i, note in enumerate(lab_state["sound_timeline"]):
            fs = ft.Slider(min=0, max=4000, value=note[0], label="{value}Hz", expand=True, on_change=lambda e, idx=i: update_audio_state(e, idx, True))
            ds = ft.Slider(min=10, max=1000, value=note[1], label="{value}ms", expand=True, on_change=lambda e, idx=i: update_audio_state(e, idx, False))
            freq_sliders.append(fs)
            dur_sliders.append(ds)

    def refresh_face_timeline():
        face_list.controls.clear()
        for i, face in enumerate(lab_state["face_timeline"]):
            is_active = (i == active_frame_idx[0])
            card = ft.Container(
                content=ft.Text(f"F{i+1}", size=12, color=ft.Colors.WHITE if is_active else ft.Colors.GREY_500),
                padding=10, bgcolor=ft.Colors.BLUE_800 if is_active else ft.Colors.BLACK45,
                border_radius=5, border=ft.Border.all(2, ft.Colors.WHITE if is_active else ft.Colors.TRANSPARENT),
                on_click=lambda e, idx=i: (load_frame_to_grid(idx), refresh_face_timeline(), page.update())
            )
            face_list.controls.append(card)
        page.update()

    def refresh_audio_timeline():
        rebuild_audio_sequencer()
        sound_list.controls.clear()
        for i in range(len(lab_state["sound_timeline"])):
            step_col = ft.Column([
                ft.Text(f"S{i+1}", size=10, color=ft.Colors.GREY_500),
                ft.Container(content=freq_sliders[i], height=150),
                ft.Container(content=dur_sliders[i], height=80)
            ], horizontal_alignment="center", spacing=5)
            sound_list.controls.append(step_col)
        page.update()

    def refresh_lab_ui():
        mood_dropdown.value = lab_state["mood"]
        
        behavior = lab_state.get("behavior", {})
        trigger_event_dropdown.value = behavior.get("event", "happiness")
        trigger_condition_dropdown.value = behavior.get("condition", "<=")
        trigger_value_input.value = str(behavior.get("value", 50))
        
        refresh_face_timeline()
        load_frame_to_grid(0)
        refresh_audio_timeline()

    def load_mood(mood):
        core = safe_load_core()
        if mood not in core.get("faces", {}):
            try:
                with open("default_core.json", "r") as f:
                    default = json.load(f)
                    core["faces"].update(default.get("faces", {}))
                    core["sounds"].update(default.get("sounds", {}))
            except: pass

        lab_state["mood"] = mood
        lab_state["face_timeline"] = core.get("faces", {}).get(mood, [["0"*32 for _ in range(8)]])
        sound_entry = core.get("sounds", {}).get(f"{mood}_sound", {})
        lab_state["sound_timeline"] = sound_entry.get("sequence", [[1000, 100], [0, 50], [1500, 100], [0, 50]])
        
        # Load behavior
        behaviors = core.get("behaviors", [])
        lab_state["behavior"] = next((b for b in behaviors if b.get("target_mood") == mood), {
            "event": "happiness",
            "condition": "<=",
            "value": sound_entry.get("threshold", 50),
            "target_mood": mood,
            "duration": 3000
        })
        
        refresh_lab_ui()
        notify(f"Loaded emotion: {mood}", ft.Colors.BLUE_400)

    def add_frame(e):
        lab_state["face_timeline"].append(["0"*32 for _ in range(8)])
        refresh_face_timeline()
        load_frame_to_grid(len(lab_state["face_timeline"]) - 1)

    def duplicate_active_frame(e):
        import copy
        lab_state["face_timeline"].insert(active_frame_idx[0] + 1, copy.deepcopy(lab_state["face_timeline"][active_frame_idx[0]]))
        refresh_face_timeline()
        load_frame_to_grid(active_frame_idx[0] + 1)

    def delete_active_frame(e):
        if len(lab_state["face_timeline"]) > 1:
            lab_state["face_timeline"].pop(active_frame_idx[0])
            new_idx = max(0, active_frame_idx[0] - 1)
            refresh_face_timeline()
            load_frame_to_grid(new_idx)

    def add_note(e):
        lab_state["sound_timeline"].append([1000, 100])
        refresh_audio_timeline()

    def remove_note(e):
        if len(lab_state["sound_timeline"]) > 1:
            lab_state["sound_timeline"].pop()
            refresh_audio_timeline()

    # --- Maintenance Actions ---
    def reboot_bot(e):
        notify("Rebooting Simulator...", ft.Colors.CYAN_700)
        page.update()
        time.sleep(0.5)
        os.execl(sys.executable, sys.executable, *sys.argv)

    def wipe_slate(e):
        def confirm_wipe(e):
            try:
                if os.path.exists("custom_core.json"):
                    os.remove("custom_core.json")
                lab_state["face_timeline"] = ["(._.)"]
                lab_state["sound_timeline"] = [[1000, 100]]
                lab_state["mood"] = "happy"
                wipe_dialog.open = False
                refresh_lab_ui()
                notify("Slate Wiped Clean!", ft.Colors.RED_700)
            except Exception as ex:
                notify(f"Wipe Failed: {ex}", ft.Colors.RED_400)

        def close_wipe(e):
            wipe_dialog.open = False
            page.update()

        wipe_dialog = ft.AlertDialog(
            title=ft.Text("Wipe Slate?"),
            content=ft.Text("This will delete your custom_core.json and all saved emotions!"),
            actions=[
                ft.TextButton("Cancel", on_click=close_wipe),
                ft.ElevatedButton("WIPE EVERYTHING", bgcolor=ft.Colors.RED_800, on_click=confirm_wipe)
            ]
        )
        page.show_dialog(wipe_dialog)

    # --- Global Lab Actions ---
    def preview_all(e):
        if not lab_state["sound_timeline"]: return
        b64_wav = generate_beep_wav(lab_state["sound_timeline"])
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(base64.b64decode(b64_wav))
                f.flush()
                def play_sound():
                    subprocess.call(["aplay", "-q", f.name])
                    try: os.unlink(f.name)
                    except: pass
                threading.Thread(target=play_sound, daemon=True).start()
        except Exception as ex:
            print(f"Audio error: {ex}")
        
        def animate():
            from oled_functions import render_face
            for face in lab_state["face_timeline"]:
                render_face(hal.oled, face, 0, display_flipped[0])
                time.sleep(0.4)
        threading.Thread(target=animate, daemon=True).start()
        notify("Previewing Animation & Audio...", ft.Colors.PURPLE_400)

    def save_emotion(e):
        try:
            core = safe_load_core()
            if "faces" not in core: core["faces"] = {}
            if "sounds" not in core: core["sounds"] = {}
            if "behaviors" not in core: core["behaviors"] = []
            
            core["faces"][lab_state["mood"]] = lab_state["face_timeline"]
            core["sounds"][f"{lab_state['mood']}_sound"] = {
                "sequence": lab_state["sound_timeline"],
            }
            
            # Update or append behavior
            behavior = lab_state.get("behavior", {
                "event": trigger_event_dropdown.value,
                "condition": trigger_condition_dropdown.value,
                "value": int(trigger_value_input.value) if trigger_value_input.value.isdigit() else 0,
                "target_mood": lab_state["mood"],
                "duration": 3000
            })
            
            # Remove old behavior for this mood if exists
            core["behaviors"] = [b for b in core["behaviors"] if b.get("target_mood") != lab_state["mood"]]
            core["behaviors"].append(behavior)
            
            with open("custom_core.json", "w") as f:
                json.dump(core, f, indent=2)
            
            from personality import personality
            personality.reload()
            notify(f"Emotion '{lab_state['mood']}' Saved & Synced!", ft.Colors.GREEN_700)
        except Exception as ex:
            print(f"Crash in save_emotion: {ex}")
            notify(f"Save Failed: {ex}", ft.Colors.RED_400)

    # -------------------------
    # Lab Layout (Pro Composer)
    # -------------------------
    mood_dropdown = ft.Dropdown(
        label="Target Emotion",
        options=[ft.dropdown.Option(m) for m in ["happy", "neutral", "sad", "angry", "curious", "scared", "eepy"]],
        on_select=lambda e: load_mood(e.control.value),
        width=200,
        bgcolor=ft.Colors.BLACK26
    )
    face_list = ft.Row(scroll="auto", spacing=10)
    sound_list = ft.Row(scroll="auto", spacing=10)

    # Combined Header
    lab_header = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME_MOTION, color=ft.Colors.AMBER_400, size=30),
                ft.Text("Composer Lab", size=24, weight="bold"),
                ft.VerticalDivider(),
                mood_dropdown,
            ], vertical_alignment="center"),
            ft.Row([
                ft.Text("Trigger:"),
                trigger_event_dropdown,
                trigger_condition_dropdown,
                trigger_value_input,
            ], vertical_alignment="center"),
        ]),
        padding=25, bgcolor=ft.Colors.BLACK45, border_radius=15, margin=ft.margin.only(bottom=20)
    )

    lab_content = ft.Container(
        content=ft.Column([
            lab_header,
            
            # Face Timeline & Editor
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Pixel Editor", size=18, weight="bold", color=ft.Colors.AMBER_100),
                        face_status,
                    ]),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Frames", size=12, color=ft.Colors.GREY_500),
                            face_list,
                        ], scroll="auto"),
                        height=60, bgcolor=ft.Colors.BLACK12, border_radius=5
                    ),
                    ft.Container(
                        content=pixel_canvas,
                        padding=5,
                        bgcolor=ft.Colors.BLACK,
                        border_radius=5,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        alignment=ft.Alignment(0, 0)
                    ),
                    pixel_toolbar,
                    ft.Row([
                        ft.ElevatedButton("+", on_click=add_frame, width=35),
                        ft.IconButton(ft.Icons.COPY, icon_color=ft.Colors.BLUE_400, on_click=duplicate_active_frame),
                        ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED_400, on_click=delete_active_frame),
                    ])
                ]),
                padding=15, bgcolor=ft.Colors.WHITE10, border_radius=12
            ),
            
            ft.Container(height=20),

            # Audio Sequencer
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Audio Step Sequencer", size=20, weight="bold", color=ft.Colors.BLUE_100),
                        audio_status,
                        ft.Row([
                            ft.ElevatedButton("Add Step", icon=ft.Icons.ADD, on_click=add_note),
                            ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED_400, on_click=remove_note),
                        ])
                    ], alignment="spaceBetween"),
                    ft.Container(content=sound_list, padding=15, bgcolor=ft.Colors.BLACK12, border_radius=15, height=300),
                ]),
                padding=20, bgcolor=ft.Colors.WHITE10, border_radius=15
            ),

            ft.Container(height=30),
            ft.Row([
                ft.ElevatedButton("PREVIEW SEQUENCE", icon=ft.Icons.PLAY_CIRCLE_FILL, on_click=preview_all, style=ft.ButtonStyle(padding=25), bgcolor=ft.Colors.DEEP_PURPLE_800, color=ft.Colors.WHITE),
                ft.ElevatedButton("COMMIT TO CORE", icon=ft.Icons.SAVE, on_click=save_emotion, style=ft.ButtonStyle(padding=25), bgcolor=ft.Colors.GREEN_900, color=ft.Colors.WHITE),
            ], alignment="center", spacing=30)
        ], scroll="auto"),
        padding=40,
        expand=True
    )

    # -------------------------
    # Simulator Sidebar Components (Revised)
    # -------------------------
    initial_w, initial_h = hal.oled.width * 2, hal.oled.height * 2
    oled_image = ft.Image(src="", width=initial_w, height=initial_h, fit=ft.BoxFit.CONTAIN)
    
    oled_display = ft.Container(
        content=oled_image, width=initial_w + 20, height=initial_h + 20,
        bgcolor=ft.Colors.BLACK, alignment=ft.Alignment(0, 0),
        border=ft.Border.all(4, ft.Colors.GREY_900), border_radius=10, padding=10
    )

    led_indicator = ft.Container(width=30, height=30, border_radius=15, bgcolor=ft.Colors.GREY_800, border=ft.Border.all(2, ft.Colors.WHITE24))
    buzzer_indicator = ft.Icon(icon=ft.Icons.VOLUME_MUTE, color=ft.Colors.GREY_800, size=30)
    
    hw_buttons_row = ft.Row(wrap=True, alignment="center", spacing=15)
    def create_hw_btn(name, pin):
        lbl = "MENU" if "button_1" in name else "OK"
        c = ft.Container(content=ft.Text(lbl, weight="bold"), bgcolor=ft.Colors.BLUE_GREY_800, padding=20, border_radius=15)
        def down(e): hal.get_button(pin).set_value(0); c.bgcolor=ft.Colors.BLUE_GREY_600; c.update()
        def up(e): hal.get_button(pin).set_value(1); c.bgcolor=ft.Colors.BLUE_GREY_800; c.update()
        return ft.GestureDetector(content=c, on_tap_down=down, on_tap_up=up, on_tap_cancel=up, mouse_cursor=ft.MouseCursor.CLICK)

    for n, p in hw.get('pins', {}).items():
        if 'button' in n.lower(): hw_buttons_row.controls.append(create_hw_btn(n, int(p)))

    # Dashboard logic
    db_status = ft.Text("OFFLINE", color=ft.Colors.RED_400, weight="bold")
    def start_web(e):
        threading.Thread(target=lambda: (importlib.import_module('web_server').start_web_server(hal.oled, False, port=SIM_PORT)), daemon=True).start()
        db_status.value="ONLINE"; db_status.color=ft.Colors.GREEN_400; e.control.disabled=True; page.update()
    
    import importlib

    display_flipped = [True]
    def toggle_flip(e):
        display_flipped[0] = not display_flipped[0]
        e.control.text = "Orientation: Hardware" if display_flipped[0] else "Orientation: Upright"
        try: import main as bot_main; bot_main.UPSIDE_DOWN = display_flipped[0]
        except: pass
        e.control.update()

    device_pane = ft.Column([
        ft.Text("Virtual Sidekick", size=24, weight="bold", color=ft.Colors.BLUE_200),
        ft.Container(height=20),
        oled_display,
        ft.Container(height=20),
        ft.Row([
            ft.ElevatedButton("Orientation: Hardware", icon=ft.Icons.SCREEN_ROTATION, on_click=toggle_flip),
            ft.IconButton(ft.Icons.DELETE_SWEEP, icon_color=ft.Colors.RED_400, tooltip="Wipe Slate", on_click=wipe_slate),
            ft.IconButton(ft.Icons.RESTART_ALT, icon_color=ft.Colors.CYAN_400, tooltip="Reboot Bot", on_click=reboot_bot),
        ], alignment="center"),
        ft.Divider(height=1, color=ft.Colors.WHITE10),
        ft.Text("Hardware Controls", size=16, weight="bold"),
        hw_buttons_row,
        ft.Row([
            ft.Column([ft.Text("LED"), led_indicator], horizontal_alignment="center"), 
            ft.Column([ft.Text("Buzzer"), buzzer_indicator], horizontal_alignment="center")
        ], alignment="center", spacing=40),
    ], horizontal_alignment="center", alignment="center", spacing=15)

    dashboard_pane = ft.Column([
        ft.Text("Dashboard Service", size=24, weight="bold", color=ft.Colors.GREEN_200),
        ft.Container(height=20),
        ft.Row([ft.Text("Status: "), db_status], alignment="center"),
        ft.Container(height=20),
        ft.ElevatedButton("Start Server", icon=ft.Icons.PLAY_ARROW, on_click=start_web),
        ft.ElevatedButton("Open Browser", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda _: webbrowser.open(f"http://localhost:{SIM_PORT}")),
    ], horizontal_alignment="center", alignment="center", spacing=15)

    # -------------------------
    # Main View Switcher
    # -------------------------
    sim_view = ft.Row([
        ft.Container(content=device_pane, padding=40, bgcolor=ft.Colors.BLACK26, expand=True, border_radius=20, margin=10),
        ft.Container(content=dashboard_pane, padding=40, bgcolor=ft.Colors.BLACK26, expand=True, border_radius=20, margin=10, border=ft.Border(left=ft.BorderSide(1, ft.Colors.WHITE10)))
    ], expand=True)
    main_content = ft.Container(content=sim_view, expand=True)

    def navigate(e):
        dest = sidebar.destinations[e.control.selected_index].data
        if dest == "sim": main_content.content = sim_view
        elif dest == "lab": main_content.content = lab_content; refresh_lab_ui()
        elif dest == "flash": subprocess.Popen(["pixi", "run", "fulldev"])
        page.update()

    sidebar = ft.NavigationRail(
        selected_index=0, label_type="all", min_width=100, group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.DEVICES_OUTLINED, selected_icon=ft.Icons.DEVICES, label="Simulator", data="sim"),
            ft.NavigationRailDestination(icon=ft.Icons.MUSIC_NOTE_OUTLINED, selected_icon=ft.Icons.PSYCHOLOGY, label="Composer", data="lab"),
            ft.NavigationRailDestination(icon=ft.Icons.BOLT, label="Flash", data="flash"),
        ],
        on_change=navigate
    )

    page.add(ft.Row([sidebar, ft.VerticalDivider(width=1), main_content], expand=True))

    # -------------------------
    # Sync Loop
    # -------------------------
    def ui_sync_loop():
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
                
                # Indicators
                if 'led' in hw.get('pins', {}):
                    on = hal.get_button(int(hw['pins']['led'])).value() == 1
                    led_indicator.bgcolor = ft.Colors.RED if on else ft.Colors.GREY_800
                if 'buzzer' in hw.get('pins', {}):
                    bz = hal.get_buzzer(int(hw['pins']['buzzer']))
                    active = hasattr(bz, '_freq') and bz._freq > 0 and bz._duty > 0
                    buzzer_indicator.icon = ft.Icons.VOLUME_UP if active else ft.Icons.VOLUME_MUTE
                    buzzer_indicator.color = ft.Colors.YELLOW if active else ft.Colors.GREY_800
                page.update()
            time.sleep(0.05)

    threading.Thread(target=ui_sync_loop, daemon=True).start()
    threading.Thread(target=run_bot_loop, daemon=True).start()

if __name__ == "__main__":
    if hasattr(ft, 'run'):
        ft.run(main)
    else:
        ft.app(main)
