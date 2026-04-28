# Based on Example code for (GY-521) MPU6050 Accelerometer/Gyro Module
# Written in MicroPython by Warayut Poomiwatracanont JAN 2023
# Base Code: https://github.com/Lezgend/MPU6050-MicroPython/blob/main/main.py
# Current Project: https://github.com/MakerSidekick/MakerSidekick-Bot/blob/main/main.py

# === DEBUG SETTINGS ===
SET_DEBUG = False  # Will be set to True automatically if hardware fails

from ADXL345 import ADXL345
from hal import Pin, hal
from hal import sleep_ms
from buzzer_sounds import (
    startup_shush, startup_sequence, happy_sound,
    angry_sound, shook_sound, headpat_sound, curious_scared_sound
)
from happy_meter import meter as get_happy
from personality import personality
from buzzer_sounds import tick_audio
from menu import open_menu
from pin_values import code_debug_pin_value
try:
    import ssd1306
except ImportError:
    pass
import oled_functions
from collections import deque
import math



# Deactivate AP on boot to ensure clean state
# ap_if = network.WLAN(network.AP_IF)
# if ap_if.active():
#     ap_if.active(False)
#     print("Deactivated lingering AP on boot.")

# === OLED HELPER FUNCTION ===
def safe_oled_update(display_type, value=None):
    """Safely update OLED - skip if OLED is not available"""
    if oled is not None:
        oled_functions.update_oled(oled, display_type, value, UPSIDE_DOWN, SET_DEBUG)
    elif SET_DEBUG:
        if value is not None:
            print(f"🖥️ OLED: {display_type} = {value}")
        else:
            print(f"🖥️ OLED: {display_type}")

import settings_store

# === OLED & I2C Initialization ===

from pin_values import i2c_scl_pin, i2c_sda_pin
i2c_bus = hal.get_i2c(scl_pin=i2c_scl_pin, sda_pin=i2c_sda_pin, freq=400_000)
sleep_ms(100)

# Try to initialize OLED - enable debug mode if it fails
oled = None
try:
    oled_w = hal.hw_config['oled']['width']
    oled_h = hal.hw_config['oled']['height']

    if hal.on_device:
        # In CircuitPython we might use adafruit_ssd1306
        # But keeping it similar, using the ported lib or standard wrapper
        try:
            import adafruit_ssd1306
            oled = adafruit_ssd1306.SSD1306_I2C(oled_w, oled_h, i2c_bus)
        except ImportError:
            try:
                import ssd1306
                oled = ssd1306.SSD1306_I2C(oled_w, oled_h, i2c_bus)
            except:
                oled = None
    else:
        oled = hal.oled
        if oled is None:
            from hal import OledMock
            oled = OledMock()
            hal.oled = oled

    print("✅ OLED initialized successfully")
except OSError as e:
    SET_DEBUG = True  # Enable debug mode on failure
    print(f"⚠️ OLED initialization failed: {e}")
    print("🔧 Debug mode enabled: Continuing without OLED...")
    oled = None

# === DISPLAY SETTINGS ===
UPSIDE_DOWN = True  # Set to True to flip the display 180 degrees

# === FIRST BOOT CHECK ===
if not settings_store._settings.get('setup_completed', False):
    import first_boot
    first_boot.run_first_boot(oled, UPSIDE_DOWN)

# === DEVICES/SENSORS ===
# Initialize ADXL345 with error handling built-in
try:
    mpu = ADXL345(i2c_bus, SET_DEBUG)
    print("✅ ADXL345 initialized successfully")
except Exception as e:
    SET_DEBUG = True  # Enable debug mode on failure
    print(f"⚠️ ADXL345 initialization failed: {e}")
    print("🔧 Debug mode enabled: Creating basic dummy accelerometer...")
    
    # Simple fallback dummy class
    class BasicDummy:
        def read_accel_data(self):
            return (0, 0, 1000)
        def read_accel_abs(self):
            return 1000.0
        def is_shaking(self):
            return False
    mpu = BasicDummy()

debug_button = Pin(code_debug_pin_value, Pin.IN, Pin.PULL_UP)

# === DISPLAY SETTINGS ===
UPSIDE_DOWN = True  # Set to True to flip the display 180 degrees

# === EMOTIONAL STATE COUNTERS ===
happy_level = 50
movement_count = 0
shake_count = 0
headpat_count = 0
gentle_movement_count = 0

# === ROLLING AVERAGE FOR MOVEMENT DETECTION ===
# Use a deque to store recent movement force values
MOVEMENT_HISTORY_SIZE = 10
movement_history = deque([0] * MOVEMENT_HISTORY_SIZE, MOVEMENT_HISTORY_SIZE)

# === Constants ===
HEADPAT_THRESHOLD = 4
SHAKE_THRESHOLD = 7
MOVEMENT_SENSITIVITY = 2
GENTLE_MOVEMENT_THRESHOLD = 15 # How long gentle movement is needed for a reward
# Adjusted thresholds for the new rolling average method
GENTLE_MOVEMENT_MIN = 1000 # Min threshold to be considered gentle movement (filters noise)
GENTLE_MOVEMENT_MAX = 35000 # Max threshold to be considered gentle movement
ROUGH_MOVEMENT = 80000

# --- New adaptive noise / stillness parameters ---
NOISE_ALPHA = 0.02              # EMA smoothing factor for noise floor
BASELINE_NOISE_START = 1500.0    # Initial guess of sensor jitter
ACTIVE_MARGIN = 500              # Force above baseline to count as "active" sample (reduced from 800)
GENTLE_ACTIVE_MIN_SAMPLES = 2    # Minimum active samples in history window (was 4)
STILL_RANGE_THRESHOLD = 1200     # If (max-min) below this AND low active samples, treat as still (was 2500)
baseline_noise = BASELINE_NOISE_START

# === STARTUP/INTRO ===
print("🤖 Sidekick Starting Up! (˶ᵔ ᵕ ᵔ˶)")
personality.set_mood("happy", 0)
startup_shush()
startup_sequence()
print("🎮 Sidekick Ready! (っ´ω`)ﾉ")

# Initialize previous_accel for difference calculation
try:
    previous_accel = mpu.read_accel_data()
except Exception as e:
    previous_accel = (0, 0, 0)
    if SET_DEBUG:
        print(f"⚠️ Initial accel read failed: {e}")

# === MAIN LOOP ===
def main_loop():
    global previous_accel, baseline_noise, movement_count, happy_level
    global shake_count, gentle_movement_count

    while True:
        try:
            # Build env reference for dynamic code each loop (lightweight)
            env = {
                'oled': oled,
                'mpu': mpu,
                'i2c': i2c_bus, # Add i2c bus to env
                'open_menu': lambda : open_menu(oled, SET_DEBUG, UPSIDE_DOWN, True, env=env),
            }
            # Read accelerometer data and calculate movement force
            try:
                current_accel = mpu.read_accel_data()

                # Calculate the difference from the previous reading
                diff_x = current_accel[0] - previous_accel[0]
                diff_y = current_accel[1] - previous_accel[1]
                diff_z = current_accel[2] - previous_accel[2]

                # Calculate the magnitude of the difference vector
                movement_force = math.sqrt(diff_x**2 + diff_y**2 + diff_z**2)

                # Update the previous acceleration value for the next iteration
                previous_accel = current_accel

                # Add the new force to our history
                movement_history.append(movement_force)

                if SET_DEBUG:
                    print(f"📊 IMU: accel={current_accel}, force={movement_force:.1f}")
            except Exception as e:
                movement_force = 0
                if SET_DEBUG:
                    print(f"💥 Accelerometer error: {e}")

            # === Adaptive noise baseline update ===
            # Only update baseline with very low movements close to current baseline
            if movement_force < (baseline_noise + 600):  # narrower adaptive window
                baseline_noise += NOISE_ALPHA * (movement_force - baseline_noise)

            # Calculate the average movement force from the history
            average_force = sum(movement_history) / MOVEMENT_HISTORY_SIZE
            range_force = max(movement_history) - min(movement_history)
            active_samples = sum(1 for f in movement_history if f > (baseline_noise + ACTIVE_MARGIN))

            if SET_DEBUG:
                print(f"🔎 avg={average_force:.0f} base={baseline_noise:.0f} rng={range_force:.0f} act={active_samples}")

            # Shake reactions
            if movement_count >= MOVEMENT_SENSITIVITY:
                print("😵 I'm getting dizzy! (⸝⸝๑﹏๑⸝⸝)")
                personality.set_mood("shake", 2000, "happy")
                shook_sound()
                # Wait a bit
                # but since shook_sound
                # We can let it play out fully.
                shake_count += 1
                movement_count = 0
                if shake_count >= SHAKE_THRESHOLD:
                    happy_level = 0
                    shake_count = 0
                    print("💔 All trust lost! I'm extremely dizzy and sad...")
                    sleep_ms(150)
                    personality.set_mood("dizzy", 5000, "sad")
                continue

            # Movement logic based on refined criteria
            is_still = ((range_force < STILL_RANGE_THRESHOLD and active_samples < GENTLE_ACTIVE_MIN_SAMPLES) or (average_force <= baseline_noise + ACTIVE_MARGIN))

            if average_force <= GENTLE_MOVEMENT_MIN or is_still:
                # Reset counters if movement stops or treated as still
                movement_count = 0
                gentle_movement_count = 0
            elif GENTLE_MOVEMENT_MIN < average_force <= GENTLE_MOVEMENT_MAX:
                # If movement is gentle and shows real variation, increment gentle counter
                gentle_movement_count += 1
                movement_count = 0 # Reset rough movement counter
                if SET_DEBUG:
                    print(f"🌱 gentle_progress={gentle_movement_count}/{GENTLE_MOVEMENT_THRESHOLD}")
                if gentle_movement_count >= GENTLE_MOVEMENT_THRESHOLD:
                    print("😊 This is a nice stroll! (´▽｀)")
                    happy_level = get_happy("add", happy_level, 0.1) # Gradual increase
                    gentle_movement_count = 0 # Reset after reward
            elif average_force >= ROUGH_MOVEMENT:
                # If movement is rough, increment rough counter
                movement_count += 1
                gentle_movement_count = 0 # Reset gentle counter
                if happy_level < 75:
                    angry_sound()
                    print("😠 Hey! What was that for! ヽ(｀Д´)ﾉ")
                else:
                    curious_scared_sound()
                    print("😮 Whoa, are you taking me somewhere? (ﾟοﾟ)")

                # Safe happiness adjustment
                happy_level = get_happy("reduce", happy_level, 1.0)

            # --- Tick Audio and Personality ---
            tick_audio()
            face, x_offset = personality.tick(movement_force)
            oled_functions.render_face(oled, face, x_offset, UPSIDE_DOWN, SET_DEBUG)

            # Debug menu access
            if debug_button.value() == 0:
                open_menu(oled, SET_DEBUG, UPSIDE_DOWN, True, env)
                startup_sequence()
                personality.set_mood("happy", 0)

            sleep_ms(50)  # Faster loop for better shake detection (was 150ms)

        except Exception as e:
            print("Error in main loop:", e)
            sleep_ms(1000)
if __name__ == '__main__':
        main_loop()
