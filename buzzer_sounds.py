from hal import Pin, PWM, ticks_ms, ticks_diff, sleep_ms
import random
import time
import json
import settings_store
from pin_values import buzzer_pin_value

# Initialize PWM for the buzzer
buzzer = PWM(Pin(buzzer_pin_value))
buzzer.duty_u16(0)

_core_cache = None

def _load_core():
    global _core_cache
    if _core_cache is not None:
        return _core_cache
    for fname in ("custom_core.json", "default_core.json"):
        try:
            with open(fname, "r") as f:
                data = json.load(f)
            if "sounds" in data:
                _core_cache = data
                return _core_cache
        except Exception:
            continue
    _core_cache = {"sounds": {}}
    return _core_cache

_core = _load_core()

_DEFAULT_SEQUENCES = {
    "happy_sound": [[1319,18],[1568,18],[1760,18],[2093,18],[2349,18],[2637,40]],
    "angry_sound": [[1760,15],[2093,15],[1568,15],[2349,15],[1760,15],[2637,15],[1397,15],[2093,15]],
    "headpat_sound": [[1175,15],[1397,15],[1760,15],[2093,15],[2637,80]],
    "click_sound": [[3000,20],[4000,20]],
    "startup_sequence": [[2000,15],[2500,15],[3000,15],[3500,15]],
    "curious_scared_sound": [[1319,18],[1568,18],[1760,18]],
    "eepy_sound": [[2093,30],[1760,35],[1568,40],[1397,45],[1568,50],[1319,140]],
    "shook_sound": [[1568,12],[1245,12],[1568,12],[1319,12],[1568,12],[1175,12],[1568,12],[1319,12]],
    "buzzer_beeping": [[1000, 100], [0, 50], [1000, 100], [0, 50], [1000, 100]],
}

class AudioManager:
    def __init__(self):
        self.current_sequence = None
        self.sequence_index = 0
        self.note_start_time = 0
        self.playing = False
        self.next_sequence = None # For followed sequences
        self.jitter = False

    def play(self, sequence_name, jitter=False):
        if settings_store.is_muted():
            return

        sounds = _core.get("sounds", {})
        snd = sounds.get(sequence_name)

        self.jitter = jitter

        if not snd:
            self.current_sequence = _DEFAULT_SEQUENCES.get(sequence_name, [])
            self.next_sequence = None
        else:
            self.current_sequence = snd.get("sequence", _DEFAULT_SEQUENCES.get(sequence_name, []))
            self.next_sequence = snd.get("follow")

        self.sequence_index = 0
        self.playing = True
        self._start_current_note()

    def _start_current_note(self):
        if not self.current_sequence or self.sequence_index >= len(self.current_sequence):
            self.stop()
            if self.next_sequence:
                self.play(self.next_sequence)
            return

        pair = self.current_sequence[self.sequence_index]
        try:
            freq, dur = pair
            freq, dur = int(freq), int(dur)

            if self.jitter and freq > 0:
                 freq += random.randint(-20, 20)

            if freq > 0:
                buzzer.freq(freq)
                buzzer.duty_u16(32768)
            else:
                buzzer.duty_u16(0)

            self.note_start_time = ticks_ms()
            self.current_duration = dur

        except Exception:
            self.sequence_index += 1
            self._start_current_note()


    def tick(self):
        if not self.playing:
            return

        now = ticks_ms()
        if ticks_diff(now, self.note_start_time) >= self.current_duration:
            self.sequence_index += 1
            self._start_current_note()

    def stop(self):
        self.playing = False
        buzzer.duty_u16(0)

audio_mgr = AudioManager()

def tick_audio():
    audio_mgr.tick()

def startup_shush():
    audio_mgr.stop()

def happy_sound():
    audio_mgr.play("happy_sound")

def angry_sound():
    audio_mgr.play("angry_sound")

def shook_sound():
    audio_mgr.play("shook_sound", jitter=True)

def headpat_sound():
    audio_mgr.play("headpat_sound")

def click_sound():
    audio_mgr.play("click_sound")

def startup_sequence():
    audio_mgr.play("startup_sequence")

def curious_scared_sound():
    audio_mgr.play("curious_scared_sound")

def eepy_sound():
    audio_mgr.play("eepy_sound")

def buzzer_beeping():
    audio_mgr.play("buzzer_beeping")


# Legacy fallback for custom apps
def play_tone(freq, duration):
    if settings_store.is_muted():
        sleep_ms(duration)
        return
    if freq > 0:
        buzzer.freq(freq)
        buzzer.duty_u16(32768)
    sleep_ms(duration)
    buzzer.duty_u16(0)
