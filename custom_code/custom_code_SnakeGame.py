from buzzer_sounds import tick_audio
# custom_code_SnakeGame.py
# A classic Snake game controlled by two buttons.

import random
from hal import sleep_ms, ticks_ms, ticks_diff
from oled_functions import _text, DEFAULT_UPSIDE
from buzzer_sounds import play_tone

# --- Game Constants ---
SCREEN_WIDTH, SCREEN_HEIGHT = 128, 48 # Changed to 128x48 resolution
GRID_SIZE = 8 # Each cell is 8x8 pixels
GRID_WIDTH = SCREEN_WIDTH // GRID_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // GRID_SIZE # Will be 48 // 8 = 6

# --- Game Settings ---
INITIAL_SNAKE_LENGTH = 3
INITIAL_GAME_SPEED_MS = 200 # Milliseconds per frame
SPEED_INCREASE_AMOUNT_MS = 10 # Decrease delay by this much per food
MIN_GAME_SPEED_MS = 50

# --- Directions ---
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

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

def _draw_rect_outline(oled, x, y, w, h, c, upside_down):
    _draw_hline(oled, x, y, w, c, upside_down)
    _draw_hline(oled, x, y + h - 1, w, c, upside_down)
    _draw_vline(oled, x, y, h, c, upside_down)
    _draw_vline(oled, x + w - 1, y, h, c, upside_down)

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
    """Initializes or resets the game state."""
    global game_state
    game_state = {
        "snake": [],
        "snake_direction": RIGHT,
        "food_pos": (0, 0),
        "score": 0,
        "game_speed_ms": INITIAL_GAME_SPEED_MS,
        "game_over": False,
        "prev_menu_state": 1, # 1 means not pressed
        "prev_ok_state": 1, # 1 means not pressed
    }
    # Initialize snake
    for i in range(INITIAL_SNAKE_LENGTH):
        game_state["snake"].append((GRID_WIDTH // 2 - i, GRID_HEIGHT // 2))
    
    spawn_food()

def spawn_food():
    """Places food at a random, empty grid cell."""
    while True:
        try: tick_audio()
        except: pass
        x = random.randint(0, GRID_WIDTH - 1)
        y = random.randint(0, GRID_HEIGHT - 1)
        if (x, y) not in game_state["snake"]:
            game_state["food_pos"] = (x, y)
            break

def draw_game(oled, upside_down):
    oled.fill(0)
    if game_state["game_over"]:
        _text(oled, "Game Over", 32, 20, upside_down)
        _text(oled, f"Score: {game_state['score']}", 36, 32, upside_down)
        oled.show()
        return

    # Draw snake
    for segment_x, segment_y in game_state["snake"]:
        _draw_rounded_rect(oled, segment_x * GRID_SIZE, segment_y * GRID_SIZE, GRID_SIZE, GRID_SIZE, 2, 1, upside_down)

    # Draw food
    food_x, food_y = game_state["food_pos"]
    _draw_rect_outline(oled, food_x * GRID_SIZE, food_y * GRID_SIZE, GRID_SIZE, GRID_SIZE, 1, upside_down)

    # Draw score
    _text(oled, f"Score: {game_state['score']}", 0, 0, upside_down)
    oled.show()

def update_game(menu_button, ok_button):
    if game_state["game_over"]: return

    # --- Handle Input (Turn Left/Right) ---
    current_direction = game_state["snake_direction"]
    new_direction = current_direction

    menu_current_state = menu_button.value()
    ok_current_state = ok_button.value()

    menu_just_pressed = (menu_current_state == 0 and game_state["prev_menu_state"] == 1)
    ok_just_pressed = (ok_current_state == 0 and game_state["prev_ok_state"] == 1)

    if menu_just_pressed: # Menu Button: Turn Left
        if current_direction == RIGHT: new_direction = UP
        elif current_direction == LEFT: new_direction = DOWN
        elif current_direction == UP: new_direction = LEFT
        elif current_direction == DOWN: new_direction = RIGHT
        play_tone(1000, 5)
    elif ok_just_pressed: # OK Button: Turn Right
        if current_direction == RIGHT: new_direction = DOWN
        elif current_direction == LEFT: new_direction = UP
        elif current_direction == UP: new_direction = RIGHT
        elif current_direction == DOWN: new_direction = LEFT
        play_tone(1000, 5)
    
    game_state["snake_direction"] = new_direction

    # Update previous button states for next frame
    game_state["prev_menu_state"] = menu_current_state
    game_state["prev_ok_state"] = ok_current_state

    # --- Move Snake ---
    head_x, head_y = game_state["snake"][0]
    new_head_x = head_x + game_state["snake_direction"][0]
    new_head_y = head_y + game_state["snake_direction"][1]

    # --- Boundary and Collision Logic ---
    # Wrap around all four sides
    if new_head_y < 0:
        new_head_y = GRID_HEIGHT - 1
    elif new_head_y >= GRID_HEIGHT:
        new_head_y = 0
    if new_head_x < 0:
        new_head_x = GRID_WIDTH - 1
    elif new_head_x >= GRID_WIDTH:
        new_head_x = 0

    # Self-collision
    if (new_head_x, new_head_y) in game_state["snake"]:
        game_state["game_over"] = True
        play_tone(440, 100); sleep_ms(50); play_tone(220, 200)
        return

    game_state["snake"].insert(0, (new_head_x, new_head_y))

    # Check if food was eaten
    if (new_head_x, new_head_y) == game_state["food_pos"]:
        game_state["score"] += 1
        game_state["game_speed_ms"] = max(MIN_GAME_SPEED_MS, game_state["game_speed_ms"] - SPEED_INCREASE_AMOUNT_MS)
        spawn_food()
        play_tone(2500, 20)
    else:
        game_state["snake"].pop() # Remove tail segment

def run(env):
    print("custom_code_SnakeGame.run() started")
    oled = env.get("oled"); upside_down = env.get("upside_down", DEFAULT_UPSIDE)
    menu_button = env.get("menu_button"); ok_button = env.get("ok_button")

    if not all([oled, menu_button, ok_button]): print("Missing required hardware"); return

    while True:
        try: tick_audio()
        except: pass
        init_game()
        # Show start screen
        oled.fill(0)
        _text(oled, "Snake", 40, 20, upside_down)
        _text(oled, "Menu:Left, OK:Right", 0, 32, upside_down)
        _text(oled, "Press OK to Start", 0, 40, upside_down)
        oled.show()
        while ok_button.value() == 1:
            # Check for hold both to exit during start screen
            if menu_button.value() == 0 and ok_button.value() == 0:
                t0 = ticks_ms()
                while menu_button.value() == 0 and ok_button.value() == 0:
                    if ticks_diff(ticks_ms(), t0) > 1000: 
                        _text(oled, "Exiting...", 32, 28, upside_down); oled.show(); sleep_ms(500); return
                    sleep_ms(20)
            sleep_ms(50)
        
        last_frame_time = ticks_ms() # Initialize last_frame_time here

        while not game_state["game_over"]:
            # Check for hold both to exit during gameplay
            if menu_button.value() == 0 and ok_button.value() == 0:
                t0 = ticks_ms()
                while menu_button.value() == 0 and ok_button.value() == 0:
                    if ticks_diff(ticks_ms(), t0) > 1000: 
                        _text(oled, "Exiting...", 32, 28, upside_down); oled.show(); sleep_ms(500); return
                    sleep_ms(20)

            now = ticks_ms()
            if ticks_diff(now, last_frame_time) < game_state["game_speed_ms"]:
                continue
            last_frame_time = now

            update_game(menu_button, ok_button)
            draw_game(oled, upside_down)

        draw_game(oled, upside_down)
        sleep_ms(1000)
        
        _text(oled, "Press OK", 32, 45, upside_down); oled.show()
        while ok_button.value() == 1:
            # Check for hold both to exit during game over screen
            if menu_button.value() == 0 and ok_button.value() == 0:
                t0 = ticks_ms()
                while menu_button.value() == 0 and ok_button.value() == 0:
                    if ticks_diff(ticks_ms(), t0) > 1000: 
                        _text(oled, "Exiting...", 32, 28, upside_down); oled.show(); sleep_ms(500); return
                    sleep_ms(20)
            sleep_ms(50)