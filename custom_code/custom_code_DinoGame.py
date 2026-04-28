from buzzer_sounds import tick_audio
# custom_code_DinoGame.py
# A clone of the classic Chrome Dino game.

import random
from hal import sleep_ms, ticks_ms, ticks_diff
from oled_functions import _text, DEFAULT_UPSIDE
from buzzer_sounds import play_tone

# --- Game Constants ---
SCREEN_WIDTH, SCREEN_HEIGHT = 128, 64
GROUND_Y = SCREEN_HEIGHT - 10

# --- Player Settings (New abstract shape) ---
PLAYER_X = 10
PLAYER_WIDTH = 12
PLAYER_HEIGHT = 14
JUMP_STRENGTH = 5.5
GRAVITY = 0.3

# --- Game Dynamics ---
INITIAL_SPEED = 2.5
SPEED_INCREASE_INTERVAL = 200
SPEED_INCREASE_AMOUNT = 0.1

# --- Obstacle Settings ---
OBSTACLE_MIN_GAP = 80
OBSTACLE_MAX_GAP = 150

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

def _draw_rounded_rect(oled, x, y, w, h, r, c, upside_down):
    """Draws a rounded rectangle. r is the corner radius."""
    _draw_hline(oled, x + r, y, w - 2 * r, c, upside_down) # Top
    _draw_hline(oled, x + r, y + h - 1, w - 2 * r, c, upside_down) # Bottom
    _draw_vline(oled, x, y + r, h - 2 * r, c, upside_down) # Left
    _draw_vline(oled, x + w - 1, y + r, h - 2 * r, c, upside_down) # Right
    # Corners
    _draw_pixel(oled, x + r - 1, y + r - 1, c, upside_down)
    _draw_pixel(oled, x + w - r, y + r - 1, c, upside_down)
    _draw_pixel(oled, x + r - 1, y + h - r, c, upside_down)
    _draw_pixel(oled, x + w - r, y + h - r, c, upside_down)

# --- Game State ---
game_state = {}

def init_game():
    global game_state
    game_state = {
        "player_y": GROUND_Y, "player_vy": 0, "is_jumping": False,
        "game_speed": INITIAL_SPEED, "score": 0, "last_score_speed_increase": 0,
        "obstacles": [], "next_obstacle_x": SCREEN_WIDTH + 20, "game_over": False,
    }

def draw_player(oled, frame, upside_down):
    """Draws the abstract Sidekick character."""
    player_y = int(game_state["player_y"]) - PLAYER_HEIGHT
    # Body
    _draw_rounded_rect(oled, PLAYER_X, player_y + 4, 10, 10, 2, 1, upside_down)
    # Head
    _draw_rounded_rect(oled, PLAYER_X + 3, player_y, 4, 4, 1, 1, upside_down)
    # Leg animation
    if frame % 2 == 0:
        _draw_vline(oled, PLAYER_X + 2, player_y + 14, 2, 1, upside_down)
        _draw_vline(oled, PLAYER_X + 7, player_y + 14, 3, 1, upside_down)
    else:
        _draw_vline(oled, PLAYER_X + 2, player_y + 14, 3, 1, upside_down)
        _draw_vline(oled, PLAYER_X + 7, player_y + 14, 2, 1, upside_down)

def draw_obstacle(oled, obs, upside_down):
    x = int(obs['x'])
    h = obs['height']
    w = obs['width']
    _draw_rounded_rect(oled, x, GROUND_Y - h, w, h, 2, 1, upside_down)

def draw_game(oled, upside_down):
    oled.fill(0)
    if game_state["game_over"]:
        _text(oled, "Game Over", 32, 20, upside_down)
        _text(oled, f"Score: {int(game_state['score'])}", 28, 32, upside_down)
        oled.show()
        return

    _draw_hline(oled, 0, GROUND_Y, SCREEN_WIDTH, 1, upside_down)
    anim_frame = (int(game_state["score"]) // 5) % 2
    draw_player(oled, anim_frame, upside_down)
    for obs in game_state["obstacles"]:
        draw_obstacle(oled, obs, upside_down)
    _text(oled, f"HI {int(game_state['score'])}", 80, 0, upside_down)
    oled.show()

def update_game(jump_button):
    if game_state["game_over"]: return

    game_state["score"] += game_state["game_speed"] * 0.1
    if game_state["score"] - game_state["last_score_speed_increase"] > SPEED_INCREASE_INTERVAL:
        game_state["game_speed"] += SPEED_INCREASE_AMOUNT
        game_state["last_score_speed_increase"] = game_state["score"]

    if game_state["is_jumping"]:
        game_state["player_vy"] += GRAVITY
        game_state["player_y"] += game_state["player_vy"]
        if game_state["player_y"] >= GROUND_Y:
            game_state["player_y"] = GROUND_Y
            game_state["is_jumping"] = False
            game_state["player_vy"] = 0
    elif jump_button.value() == 0:
        game_state["is_jumping"] = True
        game_state["player_vy"] = -JUMP_STRENGTH
        play_tone(1200, 20)

    for obs in game_state["obstacles"]:
        obs['x'] -= game_state["game_speed"]

    game_state["obstacles"] = [obs for obs in game_state["obstacles"] if obs['x'] + obs['width'] > 0]

    if not game_state["obstacles"] or game_state["obstacles"][-1]['x'] < game_state["next_obstacle_x"]:
        height = random.choice([8, 12, 13])
        width = random.choice([4, 6, 8])
        game_state["obstacles"].append({'x': SCREEN_WIDTH, 'height': height, 'width': width})
        game_state["next_obstacle_x"] = SCREEN_WIDTH - random.randint(OBSTACLE_MIN_GAP, OBSTACLE_MAX_GAP)

    player_y = int(game_state["player_y"]) - PLAYER_HEIGHT
    player_rect = {'x': PLAYER_X, 'y': player_y, 'w': PLAYER_WIDTH, 'h': PLAYER_HEIGHT}
    
    for obs in game_state["obstacles"]:
        obs_rect = {'x': obs['x'], 'y': GROUND_Y - obs['height'], 'w': obs['width'], 'h': obs['height']}
        if (player_rect['x'] < obs_rect['x'] + obs_rect['w'] and
            player_rect['x'] + player_rect['w'] > obs_rect['x'] and
            player_rect['y'] < obs_rect['y'] + obs_rect['h'] and
            player_rect['h'] + player_rect['y'] > obs_rect['y']):
            game_state["game_over"] = True
            play_tone(440, 100); sleep_ms(50); play_tone(220, 200)
            break

def run(env):
    print("custom_code_DinoGame.run() started")
    oled = env.get("oled"); upside_down = env.get("upside_down", DEFAULT_UPSIDE)
    jump_button = env.get("ok_button"); menu_button = env.get("menu_button")

    if not all([oled, jump_button, menu_button]): print("Missing required hardware"); return

    while True:
        try: tick_audio()
        except: pass
        init_game()
        last_frame_time = ticks_ms()

        while not game_state["game_over"]:
            if menu_button.value() == 0: sleep_ms(500); return

            now = ticks_ms()
            if ticks_diff(now, last_frame_time) < 16: continue
            last_frame_time = now

            update_game(jump_button)
            draw_game(oled, upside_down)

        draw_game(oled, upside_down)
        sleep_ms(1000)
        
        _text(oled, "Press OK", 32, 45, upside_down); oled.show()
        while jump_button.value() == 1:
            if menu_button.value() == 0: sleep_ms(500); return
            sleep_ms(50)