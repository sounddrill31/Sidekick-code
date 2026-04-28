from buzzer_sounds import tick_audio
# custom_code_Breakout.py
# A clone of the classic Breakout game using the accelerometer.

import random
import math
from hal import sleep_ms, ticks_ms, ticks_diff
from oled_functions import _text, DEFAULT_UPSIDE
from ADXL345 import ADXL345
from buzzer_sounds import play_tone

# --- Game Constants ---
SCREEN_WIDTH, SCREEN_HEIGHT = 128, 64

# --- Paddle Settings ---
PADDLE_WIDTH = 48
PADDLE_HEIGHT = 4
PADDLE_Y = SCREEN_HEIGHT - 8
PADDLE_MAX_SPEED = 8
ACCEL_DEAD_ZONE = 40 # Tilt values smaller than this won't cause movement
ACCEL_MAX_TILT = 250 # Tilt values larger than this will be capped

# --- Ball Settings ---
BALL_RADIUS = 2
INITIAL_BALL_SPEED = 2.0

# --- Brick Settings ---
BRICK_ROWS = 4
BRICK_COLS = 8
BRICK_WIDTH = SCREEN_WIDTH // BRICK_COLS
BRICK_HEIGHT = 5
BRICK_Y_OFFSET = 10
LIVES_total = 3

# --- Game State ---
game_state = {}
best_score = 0 # Persist best score across games

# --- Drawing Helper (to handle upside_down) ---
def _draw_rect(oled, x, y, w, h, c, upside_down):
    if upside_down:
        oled.rect(SCREEN_WIDTH - x - w, SCREEN_HEIGHT - y - h, w, h, c)
    else:
        oled.rect(x, y, w, h, c)

def reset_ball_and_paddle():
    game_state["paddle_x"] = (SCREEN_WIDTH - PADDLE_WIDTH) // 2
    game_state["paddle_vx"] = 0
    game_state["ball_x"] = SCREEN_WIDTH // 2
    game_state["ball_y"] = SCREEN_HEIGHT // 2
    angle = random.uniform(0.7, 2.4)
    game_state["ball_vx"] = math.cos(angle) * INITIAL_BALL_SPEED
    game_state["ball_vy"] = math.sin(angle) * INITIAL_BALL_SPEED

def init_game():
    global game_state
    game_state = {
        "score": 0, "lives": LIVES_total, "bricks_left": BRICK_ROWS * BRICK_COLS,
        "game_over": False, "game_won": False,
        "ax_offset": 0, "ay_offset": 0,
        "new_life_sequence": True,
        "paddle_vx": 0,
    }
    bricks = []
    for r in range(BRICK_ROWS):
        for c in range(BRICK_COLS):
            bricks.append({'x': c * BRICK_WIDTH, 'y': r * BRICK_HEIGHT + BRICK_Y_OFFSET, 'alive': True})
    game_state["bricks"] = bricks

def countdown_and_calibrate(adxl, oled, upside_down):
    global best_score
    ax_total = 0
    ay_total = 0
    num_readings = 0

    for i in range(3, 0, -1):
        oled.fill(0)
        _text(oled, "Keep device still", 0, 0, upside_down)
        _text(oled, f"Score: {game_state['score']}", 0, 10, upside_down)
        _text(oled, f"Best: {best_score}", 0, 20, upside_down)
        _text(oled, str(i), 60, 40, upside_down)
        oled.show()
        
        t_start = ticks_ms()
        while ticks_diff(ticks_ms(), t_start) < 1000:
            raw_ax, raw_ay, _ = adxl.read_accel_data()
            if upside_down:
                raw_ax = -raw_ax
                raw_ay = -raw_ay
            ax_total += raw_ax
            ay_total += raw_ay
            num_readings += 1
            sleep_ms(20)

    if num_readings > 0:
        game_state["ax_offset"] = ax_total // num_readings
        game_state["ay_offset"] = ay_total // num_readings

def draw_game(oled, upside_down):
    oled.fill(0)
    if game_state["game_over"]:
        _text(oled, "Game Over", 32, 20, upside_down)
    elif game_state["game_won"]:
        _text(oled, "You Win!", 36, 20, upside_down)
    
    if game_state["game_over"] or game_state["game_won"]:
        _text(oled, f"Score: {game_state['score']}", 36, 32, upside_down)
        oled.show()
        return

    _draw_rect(oled, int(game_state["paddle_x"]), PADDLE_Y, PADDLE_WIDTH, PADDLE_HEIGHT, 1, upside_down)
    _draw_rect(oled, int(game_state["ball_x"]) - BALL_RADIUS, int(game_state["ball_y"]) - BALL_RADIUS, BALL_RADIUS*2, BALL_RADIUS*2, 1, upside_down)
    for brick in game_state["bricks"]:
        if brick['alive']:
            _draw_rect(oled, brick['x'], brick['y'], BRICK_WIDTH - 1, BRICK_HEIGHT - 1, 1, upside_down)
    
    _text(oled, f"S:{game_state['score']} L:{game_state['lives']}", 0, 0, upside_down)
    oled.show()

def update_paddle_position(adxl, upside_down):
    raw_ax, raw_ay, _ = adxl.read_accel_data()
    if upside_down:
        raw_ax = -raw_ax
        raw_ay = -raw_ay

    is_ax_control = abs(raw_ax - game_state["ax_offset"]) > abs(raw_ay - game_state["ay_offset"])
    control_val = raw_ax if is_ax_control else raw_ay
    offset = game_state["ax_offset"] if is_ax_control else game_state["ay_offset"]
    effective_tilt = control_val - offset
    
    paddle_vx = 0
    if abs(effective_tilt) > ACCEL_DEAD_ZONE:
        clamped_tilt = max(-ACCEL_MAX_TILT, min(effective_tilt, ACCEL_MAX_TILT))
        paddle_vx = -(clamped_tilt / ACCEL_MAX_TILT) * PADDLE_MAX_SPEED

    if upside_down:
        paddle_vx *= -1

    # Simplest possible logic: apply velocity and clamp.
    next_pos = game_state["paddle_x"] + paddle_vx
    game_state["paddle_x"] = max(0, min(next_pos, SCREEN_WIDTH - PADDLE_WIDTH))

def update_game(adxl, upside_down):
    if game_state["game_over"] or game_state["game_won"] or game_state.get("new_life_sequence", False): return

    update_paddle_position(adxl, upside_down)

    # --- Ball and Game Logic ---
    game_state["ball_x"] += game_state["ball_vx"]
    game_state["ball_y"] += game_state["ball_vy"]
    bx, by = game_state["ball_x"], game_state["ball_y"]

    if bx - BALL_RADIUS < 0 or bx + BALL_RADIUS > SCREEN_WIDTH:
        game_state["ball_vx"] *= -1; play_tone(1200, 10)
    if by - BALL_RADIUS < 0:
        game_state["ball_vy"] *= -1; play_tone(1200, 10)

    if (game_state["paddle_x"] < bx < game_state["paddle_x"] + PADDLE_WIDTH and
        PADDLE_Y < by + BALL_RADIUS < PADDLE_Y + PADDLE_HEIGHT):
        game_state["ball_vy"] *= -1
        hit_pos = (bx - game_state["paddle_x"]) / PADDLE_WIDTH
        game_state["ball_vx"] += (hit_pos - 0.5) * 2.0
        play_tone(880, 20)

    for brick in game_state["bricks"]:
        if brick['alive']:
            if (brick['x'] < bx < brick['x'] + BRICK_WIDTH and brick['y'] < by < brick['y'] + BRICK_HEIGHT):
                brick['alive'] = False; game_state["ball_vy"] *= -1
                game_state["score"] += 10; game_state["bricks_left"] -= 1
                play_tone(1500, 15); break

    if by - BALL_RADIUS > SCREEN_HEIGHT:
        game_state["lives"] -= 1
        play_tone(220, 200)
        if game_state["lives"] <= 0:
            game_state["game_over"] = True
        else:
            game_state["new_life_sequence"] = True # Trigger countdown for next life
        return

    if game_state["bricks_left"] <= 0:
        game_state["game_won"] = True; play_tone(2000, 500)

def run(env):
    print("custom_code_Breakout.run() started")
    global best_score
    oled = env.get("oled"); i2c = env.get("i2c"); upside_down = env.get("upside_down", DEFAULT_UPSIDE)
    menu_button = env.get("menu_button"); ok_button = env.get("ok_button")

    if not all([oled, i2c, menu_button, ok_button]): print("Missing required hardware"); return

    adxl = ADXL345(i2c)
    if not adxl.available: _text(oled, "ADXL345 Error", 0, 0, upside_down); oled.show(); sleep_ms(2000); return

    while True:
        try: tick_audio()
        except: pass
        init_game()
        last_frame_time = ticks_ms()

        while not game_state["game_over"] and not game_state["game_won"]:
            if menu_button.value() == 0: 
                sleep_ms(200); return

            if game_state.get("new_life_sequence"):
                countdown_and_calibrate(adxl, oled, upside_down)
                reset_ball_and_paddle()
                # Get Ready Phase
                t_start = ticks_ms()
                while ticks_diff(ticks_ms(), t_start) < 1000:
                    update_paddle_position(adxl, upside_down)
                    draw_game(oled, upside_down)
                    sleep_ms(16)
                game_state["new_life_sequence"] = False
                last_frame_time = ticks_ms()

            now = ticks_ms()
            if ticks_diff(now, last_frame_time) < 16: continue
            last_frame_time = now

            update_game(adxl, upside_down)
            draw_game(oled, upside_down)

        # --- Game Over / You Win Screen ---
        if game_state["score"] > best_score:
            best_score = game_state["score"]
            
        draw_game(oled, upside_down)
        sleep_ms(1000)
        
        _text(oled, "OK:Retry Menu:Exit", 0, 50, upside_down)
        oled.show()

        while True:
            try: tick_audio()
            except: pass
            if ok_button.value() == 0:
                sleep_ms(200); break
            if menu_button.value() == 0:
                sleep_ms(200); return
            sleep_ms(50)