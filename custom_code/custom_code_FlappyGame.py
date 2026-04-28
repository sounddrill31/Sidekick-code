from buzzer_sounds import tick_audio
# custom_code_FlappyGame.py
# A clone of the Flappy Bird game, inspired by the Android Lollipop easter egg.

import random
from hal import sleep_ms, ticks_ms, ticks_diff
from oled_functions import _text, DEFAULT_UPSIDE
from buzzer_sounds import play_tone

# --- Game Constants ---
SCREEN_WIDTH, SCREEN_HEIGHT = 128, 64

# --- Player Settings (New abstract shape) ---
PLAYER_X = 32
PLAYER_WIDTH = 10
PLAYER_HEIGHT = 10
FLAP_STRENGTH = 2.3
GRAVITY = 0.28

# --- Pipe Settings ---
PIPE_WIDTH = 14
PIPE_GAP_SIZE = 30
PIPE_SPEED = 1.5
PIPE_SPAWN_DISTANCE = 80

# --- Drawing Helpers (to handle upside_down) ---
def _draw_pixel(oled, x, y, c, upside_down):
    if upside_down:
        oled.pixel(SCREEN_WIDTH - 1 - x, SCREEN_HEIGHT - 1 - y, c)
    else:
        oled.pixel(x, y, c)

def _draw_hline(oled, x, y, w, c, upside_down):
    if upside_down:
        oled.hline(SCREEN_WIDTH - x - w, SCREEN_HEIGHT - 1 - y, w, c)
    else:
        oled.hline(x, y, w, c)

def _draw_vline(oled, x, y, h, c, upside_down):
    if upside_down:
        oled.vline(SCREEN_WIDTH - 1 - x, SCREEN_HEIGHT - y - h, h, c)
    else:
        oled.vline(x, y, h, c)

def _draw_rect_filled(oled, x, y, w, h, c, upside_down):
    if upside_down:
        oled.fill_rect(SCREEN_WIDTH - x - w, SCREEN_HEIGHT - y - h, w, h, c)
    else:
        oled.fill_rect(x, y, w, h, c)

def _draw_rounded_rect(oled, x, y, w, h, r, c, upside_down):
    _draw_hline(oled, x + r, y, w - 2 * r, c, upside_down)
    _draw_hline(oled, x + r, y + h - 1, w - 2 * r, c, upside_down)
    _draw_vline(oled, x, y + r, h - 2 * r, c, upside_down)
    _draw_vline(oled, x + w - 1, y + r, h - 2 * r, c, upside_down)
    _draw_pixel(oled, x + r - 1, y + r - 1, c, upside_down)
    _draw_pixel(oled, x + w - r, y + r - 1, c, upside_down)
    _draw_pixel(oled, x + r - 1, y + h - r, c, upside_down)
    _draw_pixel(oled, x + w - r, y + h - r, c, upside_down)

# --- Game State ---
game_state = {}

def init_game():
    global game_state
    game_state = {
        "player_y": SCREEN_HEIGHT // 2, "player_vy": 0,
        "pipes": [], "score": 0, "game_over": False,
    }
    spawn_pipe(SCREEN_WIDTH)
    spawn_pipe(SCREEN_WIDTH + PIPE_SPAWN_DISTANCE)
    spawn_pipe(SCREEN_WIDTH + 2 * PIPE_SPAWN_DISTANCE)

def spawn_pipe(x_pos):
    gap_y = random.randint(10, SCREEN_HEIGHT - 10 - PIPE_GAP_SIZE)
    game_state["pipes"].append({'x': x_pos, 'gap_y': gap_y, 'scored': False})

def draw_player(oled, upside_down):
    y = int(game_state["player_y"]) - (PLAYER_HEIGHT // 2)
    # Body
    _draw_rect_filled(oled, PLAYER_X, y, PLAYER_WIDTH, PLAYER_HEIGHT, 1, upside_down)
    # Eye (simple animation)
    eye_y = y + 3
    eye_x = PLAYER_X + PLAYER_WIDTH - 3
    if game_state["player_vy"] > 0.5: # Looking down when falling
        eye_y += 2
    _draw_pixel(oled, eye_x, eye_y, 0, upside_down)

def draw_pipes(oled, upside_down):
    for pipe in game_state["pipes"]:
        x = int(pipe['x'])
        # Top pipe
        _draw_rect_filled(oled, x, 0, PIPE_WIDTH, pipe['gap_y'], 1, upside_down)
        _draw_rounded_rect(oled, x - 2, pipe['gap_y'] - 4, PIPE_WIDTH + 4, 4, 1, 1, upside_down)
        # Bottom pipe
        bottom_pipe_y = pipe['gap_y'] + PIPE_GAP_SIZE
        _draw_rect_filled(oled, x, bottom_pipe_y, PIPE_WIDTH, SCREEN_HEIGHT - bottom_pipe_y, 1, upside_down)
        _draw_rounded_rect(oled, x - 2, bottom_pipe_y, PIPE_WIDTH + 4, 4, 1, 1, upside_down)

def draw_game(oled, upside_down):
    oled.fill(0)
    if game_state["game_over"]:
        _text(oled, "Game Over", 32, 20, upside_down)
        _text(oled, f"Score: {game_state['score']}", 36, 32, upside_down)
        oled.show()
        return

    draw_pipes(oled, upside_down)
    draw_player(oled, upside_down)
    _text(oled, str(game_state["score"]), SCREEN_WIDTH // 2 - 4, 4, upside_down)
    oled.show()

def update_game(flap_button):
    if game_state["game_over"]: return

    if flap_button.value() == 0:
        game_state["player_vy"] = -FLAP_STRENGTH
        play_tone(1800, 10)
        while flap_button.value() == 0: sleep_ms(10)
    
    game_state["player_vy"] += GRAVITY
    game_state["player_y"] += game_state["player_vy"]

    for pipe in game_state["pipes"]:
        pipe['x'] -= PIPE_SPEED
        if not pipe['scored'] and pipe['x'] + PIPE_WIDTH < PLAYER_X:
            pipe['scored'] = True
            game_state["score"] += 1
            play_tone(2500, 20)

    if game_state["pipes"][0]['x'] < -PIPE_WIDTH - 4:
        game_state["pipes"].pop(0)
        spawn_pipe(game_state["pipes"][-1]['x'] + PIPE_SPAWN_DISTANCE)

    player_y = game_state["player_y"]
    if not (0 < player_y < SCREEN_HEIGHT):
        game_state["game_over"] = True

    for pipe in game_state["pipes"]:
        if PLAYER_X + PLAYER_WIDTH//2 > pipe['x'] and PLAYER_X - PLAYER_WIDTH//2 < pipe['x'] + PIPE_WIDTH:
            if not (pipe['gap_y'] < player_y - PLAYER_HEIGHT//2 and player_y + PLAYER_HEIGHT//2 < pipe['gap_y'] + PIPE_GAP_SIZE):
                game_state["game_over"] = True
                break
    
    if game_state["game_over"]:
        play_tone(440, 100); sleep_ms(50); play_tone(220, 200)

def run(env):
    print("custom_code_FlappyGame.run() started")
    oled = env.get("oled"); upside_down = env.get("upside_down", DEFAULT_UPSIDE)
    flap_button = env.get("ok_button"); menu_button = env.get("menu_button")

    if not all([oled, flap_button, menu_button]): print("Missing required hardware"); return

    while True:
        try: tick_audio()
        except: pass
        init_game()
        oled.fill(0); _text(oled, "Flappy", 40, 20, upside_down); _text(oled, "Press OK", 32, 40, upside_down); oled.show()
        while flap_button.value() == 1:
            if menu_button.value() == 0: sleep_ms(500); return
            sleep_ms(50)

        last_frame_time = ticks_ms()
        while not game_state["game_over"]:
            if menu_button.value() == 0: sleep_ms(500); return

            now = ticks_ms()
            if ticks_diff(now, last_frame_time) < 20: continue
            last_frame_time = now

            update_game(flap_button)
            draw_game(oled, upside_down)

        draw_game(oled, upside_down)
        sleep_ms(1000)
        
        _text(oled, "Press OK", 32, 45, upside_down); oled.show()
        while flap_button.value() == 1:
            if menu_button.value() == 0: sleep_ms(500); return
            sleep_ms(50)