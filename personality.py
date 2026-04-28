import json
import random
from hal import ticks_ms, ticks_diff
import settings_store

DEFAULT_FACES = {
    "happy": ['(^_^)', '(^_^)', "('-')", "('-')", "('-')", '(^_^)'],
    "really_happy": ['(^o^)', '(^o^)', '(*^_^*)', '(*^_^*)', '(*^_^*)', '(^o^)'],
    "curious": ['(o_o)', '(o_o)', '(-_-?)', '(-_-?)', '(-_-?)', '(._.)', '(._.)', '(._.)', '(-_-?)', '(-_-?)', '(-_-?)', '(o_o)'],
    "concerned": ['(>_<)', '(>_<)', '(._.)', '(._.)', '(._.)', '(>_<)'],
    "sad": ['(T_T)', '(T_T)', '(;_;)'],
    "sleepy": ['(-_-)', '(-_-)', '(u_u)'],
    "mischief": ['(¬‿¬)', '(¬‿¬)', '(^_~)'],
    "surprised": ['(O_O)', '(O_O)', '(o_O)'],
    "angry": ['(>_<)', '(>_<)', '(>: [)'],
    "cool": ['(-_-)', '(-_-)', '(B-)'],
    "love": ['(^3^)', '(^3^)', '(^.^)'],
    "headpat": ['(^_^)', '(^_^)', '(^_^*)'],
    "shake": ['(@_@)', '(@_@)', '(x_x)', '(x_x)', '(x_x)', '(O_o)'],
    "dizzy": ['(@_@)'],
}

BLINK_DURATION = 140
SHAKE_DURATION = 2000
HEADPAT_DURATION = 1200
SWAY_PERIOD = 1800

class PersonalityCore:
    def __init__(self):
        self.faces = dict(DEFAULT_FACES)
        self.upside_down = False
        self.behaviors = []

        self.current_mood = "happy"

        # State
        self.last_blink_time = 0
        self.blinking = False
        self.next_blink_interval = self._get_blink_interval()

        self.mood_start_time = ticks_ms()
        self.mood_duration = 0 # 0 means infinite
        self.fallback_mood = "happy"

        self.reload()

    def _get_blink_interval(self):
        return random.randint(3000, 6000)

    def reload(self):
        core_type = settings_store.get_core_type()

        files_to_try = []
        if core_type == 'Custom':
            files_to_try.append('custom_core.json')
        files_to_try.append('default_core.json')

        data = {}
        for fname in files_to_try:
            try:
                with open(fname, 'r') as f:
                    data = json.load(f)
                    break
            except Exception:
                continue

        if not isinstance(data, dict):
            data = {}

        loaded_faces = data.get('faces', {})
        self.faces = dict(DEFAULT_FACES)
        self.faces.update(loaded_faces)
        self.upside_down = data.get('display', {}).get('upside_down', False)
        
        # Process triggers from sounds for backward compatibility 
        # or load advanced behaviors if defined
        self.behaviors = data.get('behaviors', [])
        sounds = data.get('sounds', {})
        for sound_key, sound_data in sounds.items():
            if "threshold" in sound_data and sound_key.endswith("_sound"):
                mood = sound_key.replace("_sound", "")
                self.behaviors.append({
                    "event": "happiness",
                    "condition": "<=",
                    "value": sound_data["threshold"],
                    "target_mood": mood,
                    "duration": 3000
                })

    def process_triggers(self, event_type, **kwargs):
        # Evaluate behaviors
        for b in self.behaviors:
            if b.get("event") == event_type:
                cond = b.get("condition", "none")
                val = b.get("value", 0)
                
                trigger = False
                if cond == "none":
                    trigger = True
                elif cond == "==" and kwargs.get("value", 0) == val:
                    trigger = True
                elif cond == "<=" and kwargs.get("value", 0) <= val:
                    trigger = True
                elif cond == ">=" and kwargs.get("value", 0) >= val:
                    trigger = True

                if trigger:
                    mood = b.get("target_mood")
                    if mood:
                        self.set_mood(mood, b.get("duration", 2000))
                    return mood
        return None

    def set_mood(self, mood, duration_ms=0, fallback="happy"):
        self.current_mood = mood
        self.mood_start_time = ticks_ms()
        self.mood_duration = duration_ms
        self.fallback_mood = fallback

    def _translate_emoji_blink(self, face):
        if isinstance(face, list): return face
        return (face
                .replace('^', '-')
                .replace('o', '-')
                .replace('O', '-')
                .replace('x', '-')
                .replace('_', '-'))

    def tick(self, movement_force=0):
        now = ticks_ms()

        # Mood timeout
        if self.mood_duration > 0 and ticks_diff(now, self.mood_start_time) > self.mood_duration:
            self.set_mood(self.fallback_mood)

        # Blinking logic
        blinkable = self.current_mood not in ("shake", "headpat")
        if blinkable:
            if ticks_diff(now, self.last_blink_time) > self.next_blink_interval:
                self.blinking = True
                self.last_blink_time = now
                self.next_blink_interval = self._get_blink_interval()
            if self.blinking and ticks_diff(now, self.last_blink_time) > BLINK_DURATION:
                self.blinking = False
        else:
            self.blinking = False

        # Sway calculation driven by movement
        sway = 0
        if self.current_mood not in ("shake", "headpat", "dizzy"):
            period = SWAY_PERIOD
            try:
                from math import sin, pi
                t = (now % period) / period
                # Base sway plus movement driven sway
                intensity = 5 + min(15, movement_force / 2000)
                sway = int(intensity * sin(2 * pi * t))
            except Exception:
                pass

        seq = self.faces.get(self.current_mood, self.faces.get('curious', ['(._.)']))

        if self.current_mood == "shake":
            phase_len = 210
            frame = (ticks_diff(now, self.mood_start_time) // phase_len) % min(3, len(seq))
            face = seq[frame]
            offset_seq = [-11, 0, 10]
            x_offset = offset_seq[frame % len(offset_seq)]
        elif self.current_mood == "headpat":
            if len(seq) < 2:
                face = seq[0]
                x_offset = 0
            else:
                phase = (ticks_diff(now, self.mood_start_time) // 400) % 2
                face = seq[phase]
                x_offset = 2 if phase else -3
        else:
            # Default animation timing
            idx = (now // 2000) % len(seq)
            face = seq[idx]
            x_offset = sway

        if self.blinking:
            face = self._translate_emoji_blink(face)

        return face, x_offset

personality = PersonalityCore()
