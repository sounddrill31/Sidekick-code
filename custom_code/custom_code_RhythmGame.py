from buzzer_sounds import tick_audio
# custom_code_RhythmGame.py
# A procedural rhythm game called Button Bash Rhapsody.

import random
from hal import sleep_ms, ticks_ms, ticks_diff
from oled_functions import _text, _draw_ascii, DEFAULT_UPSIDE
from hal import Pin, PWM
from pin_values import buzzer_pin_value
import settings_store

# --- Buzzer Setup ---
buzzer = PWM(Pin(buzzer_pin_value))
buzzer.duty_u16(0)

# --- Tuning and Settings ---
BPM = 120
BEATS_PER_SONG = 48
BEAT_MS = int(60000 / BPM)
TIMING_WINDOW_MS = 220
PREVIEW_WINDOW_MS = 1500

# --- Music Generation ---
SCALE = [523, 587, 659, 784, 880, 1047] # C Major Pentatonic
NOTE_DURATIONS = [BEAT_MS // 2, BEAT_MS - 50]

# --- Beat Types (Button Only) --
B1 = 1
B2 = 2
BOTH = 3

PREVIEW_CUES = { B1: "o", B2: "x", BOTH: "*" }
CUE_Y_POS = { B1: 20, B2: 35, BOTH: 28 }

# --- Game State ---
game_state = {}

def play_sound(freq, duration):
    if settings_store.is_muted():
        return
    global game_state
    if freq > 0:
        buzzer.freq(freq)
        buzzer.duty_u16(32768)
        game_state["sound_off_time"] = ticks_ms() + duration

def generate_sequence():
    sequence = []
    current_time = 1500 # Start first beat after a delay
    for i in range(BEATS_PER_SONG):
        beat_type = random.choice([B1, B2, BOTH, B1, B2]) # Only button types
        sequence.append({
            "time": current_time,
            "freq": random.choice(SCALE),
            "duration": random.choice(NOTE_DURATIONS),
            "type": beat_type,
            "hit": False, "played": False,
        })
        current_time += BEAT_MS
    return sequence

def init_game():
    global game_state
    game_state = {
        "sequence": generate_sequence(),
        "score": 0, "combo": 0, "max_combo": 0,
        "current_beat_index": 0,
        "start_time": ticks_ms(),
        "last_feedback": "", "feedback_time": 0,
        "game_over": False,
        "sound_off_time": 0,
    }

def draw_start_menu(oled, upside_down):
    oled.fill(0)
    _text(oled, "Button Bash", 16, 8, upside_down)
    _text(oled, "o: B1  x: B2  *:Both", 0, 24, upside_down)
    _text(oled, "Press B2 to Start", 0, 40, upside_down)
    _text(oled, "Press B1 to Exit", 4, 50, upside_down)
    oled.show()

def draw_game(oled, upside_down):
    oled.fill(0)
    if game_state["game_over"]:
        _text(oled, "Song Over!", 24, 12, upside_down)
        _text(oled, f"Score: {game_state['score']}", 12, 30, upside_down)
        _text(oled, f"Max Combo: {game_state['max_combo']}", 12, 40, upside_down)
        oled.show()
        return

    now = ticks_diff(ticks_ms(), game_state["start_time"])
    
    # Draw Note Highway
    hit_zone_x = 20
    oled.vline(hit_zone_x - 2, 15, 25, 1)
    oled.vline(hit_zone_x + 2, 15, 25, 1)

    for i in range(game_state["current_beat_index"], len(game_state["sequence"])):
        beat = game_state["sequence"][i]
        time_diff = beat["time"] - now
        if 0 < time_diff < PREVIEW_WINDOW_MS:
            progress = 1 - (time_diff / PREVIEW_WINDOW_MS)
            x_pos = hit_zone_x + int(progress * (128 - hit_zone_x))
            cue_char = PREVIEW_CUES.get(beat["type"], "?")
            y_pos = CUE_Y_POS.get(beat["type"], 25)
            _text(oled, cue_char, x_pos, y_pos, upside_down)

    # Draw Player Character / Feedback
    face = "(o_o)"
    if ticks_diff(ticks_ms(), game_state["feedback_time"]) < 200:
        if game_state["last_feedback"] == "Perfect!": face = "(^o^)"
        elif game_state["last_feedback"] == "Good": face = "(^_^)"
        else: face = "(>_<)"
    _draw_ascii(oled, face, 50, 45, 1, upside_down)

    _text(oled, f"S:{game_state['score']} C:{game_state['combo']}", 0, 0, upside_down)
    _text(oled, "o:B1 x:B2 *:Both", 0, 56, upside_down)
    oled.show()

def update_game(b1, b2):
    if game_state["sound_off_time"] > 0 and ticks_ms() >= game_state["sound_off_time"]:
        buzzer.duty_u16(0)
        game_state["sound_off_time"] = 0

    now = ticks_diff(ticks_ms(), game_state["start_time"])
    idx = game_state["current_beat_index"]

    if idx >= len(game_state["sequence"]):
        game_state["game_over"] = True
        return

    b1_pressed = b1.value() == 0
    b2_pressed = b2.value() == 0
    
    action_taken = b1_pressed or b2_pressed
    if action_taken:
        hit_something = False
        for i in range(idx, min(idx + 4, len(game_state["sequence"]))):
            beat = game_state["sequence"][i]
            if not beat["hit"] and abs(now - beat["time"]) < TIMING_WINDOW_MS:
                correct_input = False
                if beat["type"] == B1 and b1_pressed and not b2_pressed: correct_input = True
                elif beat["type"] == B2 and b2_pressed and not b1_pressed: correct_input = True
                elif beat["type"] == BOTH and b1_pressed and b2_pressed: correct_input = True
                
                if correct_input:
                    beat["hit"] = True
                    hit_something = True
                    timing_diff = abs(now - beat["time"])
                    if timing_diff < TIMING_WINDOW_MS / 2:
                        game_state["last_feedback"] = "Perfect!"
                        game_state["score"] += 20 + game_state["combo"]
                    else:
                        game_state["last_feedback"] = "Good"
                        game_state["score"] += 10 + game_state["combo"]
                    
                    game_state["combo"] += 1
                    if game_state["combo"] > game_state["max_combo"]: game_state["max_combo"] = game_state["combo"]
                    break
        
        if not hit_something:
            game_state["combo"] = 0
            game_state["last_feedback"] = "X"
        
        game_state["feedback_time"] = ticks_ms()

    beat = game_state["sequence"][idx]
    if not beat["played"] and now >= beat["time"]:
        play_sound(beat["freq"], beat["duration"])
        beat["played"] = True

    if now > beat["time"] + TIMING_WINDOW_MS:
        if not beat["hit"]:
            game_state["combo"] = 0
            game_state["last_feedback"] = "Miss!"
            game_state["feedback_time"] = ticks_ms()
        game_state["current_beat_index"] += 1

def run(env):
    print("custom_code_RhythmGame.run() started")
    oled = env.get("oled"); upside_down = env.get("upside_down", DEFAULT_UPSIDE)
    b1 = env.get("menu_button"); b2 = env.get("ok_button")

    if not all([oled, b1, b2]): print("Missing required hardware"); return

    # --- Start Menu Loop ---
    while True:
        try: tick_audio()
        except: pass
        draw_start_menu(oled, upside_down)
        if b2.value() == 0: # OK button to start
            while b2.value() == 0: sleep_ms(10)
            break
        if b1.value() == 0: # Menu button to exit
            return
        sleep_ms(30)

    init_game()

    while not game_state["game_over"]:
        if b1.value() == 0 and b2.value() == 0:
            t0 = ticks_ms()
            while b1.value() == 0 and b2.value() == 0:
                if ticks_diff(ticks_ms(), t0) > 1000: 
                    _text(oled, "Exiting...", 32, 28, upside_down); oled.show(); sleep_ms(500); return
                sleep_ms(20)

        update_game(b1, b2)
        draw_game(oled, upside_down)
        sleep_ms(16)
    
    draw_game(oled, upside_down)
    sleep_ms(5000)
    buzzer.duty_u16(0) # Ensure buzzer is off when the game ends
