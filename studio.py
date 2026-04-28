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
    try:
        import main as bot_main
        # Note: bot_main.main_loop() usually has a while True. 
        # For a true 'reboot', we might need to reload modules or use a process.
        # For now, we'll just try to start it.
        bot_main.main_loop()
    except Exception as e:
        print(f"Bot failed to start: {e}")

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

    # -------------------------
    # Composer Lab UI Refresh
    # -------------------------
    def refresh_lab_ui():
        mood_dropdown.value = lab_state["mood"]
        threshold_slider.value = lab_state["threshold"]
        
        face_list.controls.clear()
        for i, face in enumerate(lab_state["face_timeline"]):
            face_list.controls.append(create_face_frame_card(i, face))
        
        sound_list.controls.clear()
        for i, note in enumerate(lab_state["sound_timeline"]):
            sound_list.controls.append(create_sound_note_card(i, note))
            
        page.update()

    def load_mood(mood):
        core = safe_load_core()
        # Fallback to default core if not in custom
        if mood not in core.get("faces", {}):
            try:
                with open("default_core.json", "r") as f:
                    default = json.load(f)
                    core["faces"].update(default.get("faces", {}))
                    core["sounds"].update(default.get("sounds", {}))
            except: pass

        lab_state["mood"] = mood
        lab_state["face_timeline"] = core.get("faces", {}).get(mood, ["(._.)"])
        sound_entry = core.get("sounds", {}).get(f"{mood}_sound", {})
        lab_state["sound_timeline"] = sound_entry.get("sequence", [[1000, 50]])
        lab_state["threshold"] = sound_entry.get("threshold", 50)
        refresh_lab_ui()
        notify(f"Loaded emotion: {mood}", ft.Colors.BLUE_400)

    # --- Face Frame Card ---
    def create_face_frame_card(idx, face_str):
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"#{idx+1}", size=10, color=ft.Colors.GREY_500),
                    ft.Text(face_str, size=20, weight="bold"),
                    ft.Row([
                        ft.IconButton(ft.Icons.EDIT, icon_size=16, on_click=lambda e: open_face_builder(idx)),
                        ft.IconButton(ft.Icons.COPY, icon_size=16, on_click=lambda e: duplicate_frame(idx)),
                        ft.IconButton(ft.Icons.DELETE, icon_size=16, icon_color=ft.Colors.RED_400, on_click=lambda e: delete_frame(idx)),
                    ], spacing=0, alignment="center")
                ], alignment="center", horizontal_alignment="center", spacing=5),
                padding=10, width=130, height=120
            ),
            elevation=2
        )

    def open_face_builder(idx):
        face = lab_state["face_timeline"][idx]
        # Extremely naive parser: look for chars inside parens
        # (˶ᵔ ᵕ ᵔ˶) -> ˶ᵔ ᵕ ᵔ˶
        inner = face.strip("() ")
        
        def save_built_face(e):
            new_face = f"({eye_sel.value.split(' ')[0]}{mouth_sel.value}{eye_sel.value.split(' ')[1]})"
            if brow_sel.value != "None":
                b_l, b_r = brow_sel.value.split(" ")
                new_face = f"{b_l}{new_face}{b_r}"
            lab_state["face_timeline"][idx] = new_face
            face_builder_dialog.open = False
            refresh_lab_ui()

        eye_sel = ft.Dropdown(label="Eyes", options=[ft.dropdown.Option(o) for o in FACE_PARTS["eyes"]], value="^ ^")
        mouth_sel = ft.Dropdown(label="Mouth", options=[ft.dropdown.Option(o) for o in FACE_PARTS["mouths"]], value="_")
        brow_sel = ft.Dropdown(label="Brows", options=[ft.dropdown.Option(o) for o in FACE_PARTS["brows"]], value="None")

        face_builder_dialog = ft.AlertDialog(
            title=ft.Text(f"Frame {idx+1} Builder"),
            content=ft.Column([eye_sel, mouth_sel, brow_sel], tight=True),
            actions=[ft.TextButton("Cancel", on_click=lambda _: setattr(face_builder_dialog, 'open', False)), ft.ElevatedButton("Apply", on_click=save_built_face)]
        )
        page.dialog = face_builder_dialog
        face_builder_dialog.open = True
        page.update()

    def duplicate_frame(idx):
        lab_state["face_timeline"].insert(idx + 1, lab_state["face_timeline"][idx])
        refresh_lab_ui()

    def delete_frame(idx):
        if len(lab_state["face_timeline"]) > 1:
            lab_state["face_timeline"].pop(idx)
            refresh_lab_ui()

    # --- Sound Note Card ---
    def create_sound_note_card(idx, note):
        freq, dur = note
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"#{idx+1}", size=10, color=ft.Colors.GREY_500),
                    ft.Text(f"{freq}Hz", size=16, weight="bold", color=ft.Colors.BLUE_200),
                    ft.Text(f"{dur}ms", size=12),
                    ft.Row([
                        ft.IconButton(ft.Icons.EDIT, icon_size=16, on_click=lambda e: open_note_editor(idx)),
                        ft.IconButton(ft.Icons.DELETE, icon_size=16, icon_color=ft.Colors.RED_400, on_click=lambda e: delete_note(idx)),
                    ], spacing=0, alignment="center")
                ], alignment="center", horizontal_alignment="center", spacing=5),
                padding=10, width=110, height=120
            ),
            elevation=2
        )

    def open_note_editor(idx):
        note = lab_state["sound_timeline"][idx]
        f_slider = ft.Slider(min=0, max=5000, value=note[0], label="{value}Hz")
        d_slider = ft.Slider(min=10, max=1000, value=note[1], label="{value}ms")
        
        def save_note(e):
            lab_state["sound_timeline"][idx] = [int(f_slider.value), int(d_slider.value)]
            note_editor.open = False
            refresh_lab_ui()

        note_editor = ft.AlertDialog(
            title=ft.Text(f"Note {idx+1} Editor"),
            content=ft.Column([ft.Text("Frequency (Hz)"), f_slider, ft.Text("Duration (ms)"), d_slider], tight=True),
            actions=[ft.TextButton("Cancel", on_click=lambda _: setattr(note_editor, 'open', False)), ft.ElevatedButton("Apply", on_click=save_note)]
        )
        page.dialog = note_editor
        note_editor.open = True
        page.update()

    def delete_note(idx):
        if len(lab_state["sound_timeline"]) > 1:
            lab_state["sound_timeline"].pop(idx)
            refresh_lab_ui()

    # --- Maintenance Actions ---
    def reboot_bot(e):
        notify("Rebooting Sidekick Core...", ft.Colors.CYAN_700)
        # In a real app we'd kill the thread, but we'll just re-import or reset hal
        try:
            hal.reset() # This usually exits, studio.py should be run with a watcher or just restart manually
        except: 
            os._exit(0)

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

        wipe_dialog = ft.AlertDialog(
            title=ft.Text("Wipe Slate?"),
            content=ft.Text("This will delete your custom_core.json and all saved emotions!"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(wipe_dialog, 'open', False)),
                ft.ElevatedButton("WIPE EVERYTHING", bgcolor=ft.Colors.RED_800, on_click=confirm_wipe)
            ]
        )
        page.dialog = wipe_dialog
        wipe_dialog.open = True
        page.update()

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
                render_face(hal.oled, face, 0, True) # Force hardware orientation for preview
                time.sleep(0.4)
        threading.Thread(target=animate, daemon=True).start()
        notify("Previewing Animation & Audio...", ft.Colors.PURPLE_400)

    def save_emotion(e):
        try:
            core = safe_load_core()
            if "faces" not in core: core["faces"] = {}
            if "sounds" not in core: core["sounds"] = {}
            core["faces"][lab_state["mood"]] = lab_state["face_timeline"]
            core["sounds"][f"{lab_state['mood']}_sound"] = {
                "sequence": lab_state["sound_timeline"],
                "threshold": int(threshold_slider.value)
            }
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
    threshold_slider = ft.Slider(min=0, max=100, value=75, label="Happiness Threshold: {value}%", expand=True)
    
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
                ft.Text("Happiness Trigger:"),
                threshold_slider,
                ft.IconButton(ft.Icons.DELETE_SWEEP, icon_color=ft.Colors.RED_400, tooltip="Wipe Slate", on_click=wipe_slate),
                ft.IconButton(ft.Icons.RESTART_ALT, icon_color=ft.Colors.CYAN_400, tooltip="Reboot Bot", on_click=reboot_bot),
            ], vertical_alignment="center"),
        ]),
        padding=25, bgcolor=ft.Colors.BLACK45, border_radius=15, margin=ft.margin.only(bottom=20)
    )

    lab_content = ft.Container(
        content=ft.Column([
            lab_header,
            
            # Face Timeline
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Face Animation Timeline", size=20, weight="bold", color=ft.Colors.AMBER_100),
                        ft.ElevatedButton("Add Frame", icon=ft.Icons.ADD, on_click=lambda _: (lab_state["face_timeline"].append("(._.)"), refresh_lab_ui())),
                    ], alignment="spaceBetween"),
                    ft.Container(content=face_list, padding=15, bgcolor=ft.Colors.BLACK12, border_radius=15, height=180),
                ]),
                padding=20, bgcolor=ft.Colors.WHITE10, border_radius=15
            ),
            
            ft.Container(height=20),

            # Sound Timeline
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Sound Synth Timeline", size=20, weight="bold", color=ft.Colors.BLUE_100),
                        ft.ElevatedButton("Add Note", icon=ft.Icons.MUSIC_NOTE, on_click=lambda _: (lab_state["sound_timeline"].append([1000, 50]), refresh_lab_ui())),
                    ], alignment="spaceBetween"),
                    ft.Container(content=sound_list, padding=15, bgcolor=ft.Colors.BLACK12, border_radius=15, height=180),
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

    device_pane = ft.Column([
        ft.Text("Virtual Sidekick", size=24, weight="bold", color=ft.Colors.BLUE_200),
        ft.Container(height=20),
        oled_display,
        ft.Container(height=20),
        ft.Text("Hardware Controls", size=16, weight="bold"),
        hw_buttons_row,
        ft.Row([ft.Column([ft.Text("LED"), led_indicator], horizontal_alignment="center"), ft.Column([ft.Text("Buzzer"), buzzer_indicator], horizontal_alignment="center")], alignment="center", spacing=40),
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
