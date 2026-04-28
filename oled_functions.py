from hal import sleep_ms
import settings_store

def _centered_x(oled, face_str, scale=2):
    w = len(face_str) * 8 * scale
    w_limit = oled.width if hasattr(oled, 'width') else 128
    return max((w_limit - w) // 2, 0)


def _draw_ascii(oled, text, x, y, scale=2, upside_down=False):
    """Draw scaled ASCII text on oled"""
    if not oled: return
    try:
        import framebuf
        char_width = 8 * len(text)
        char_height = 8
        temp_buf = bytearray(char_width * char_height // 8)
        temp_fb = framebuf.FrameBuffer(temp_buf, char_width, char_height, framebuf.MONO_VLSB)
        temp_fb.text(text, 0, 0, 1)
        for i in range(char_width):
            for j in range(char_height):
                if temp_fb.pixel(i, j):
                    if upside_down:
                        # Flip both x and y coordinates for 180 degree rotation
                        flip_x = oled.width - (x + i * scale + scale)
                        flip_y = oled.height - (y + j * scale + scale)
                        if hasattr(oled, 'fill_rect'): oled.fill_rect(flip_x, flip_y, scale, scale, 1)
                    else:
                        if hasattr(oled, 'fill_rect'): oled.fill_rect(x + i*scale, y + j*scale, scale, scale, 1)
    except Exception:
        # Fallback raw text rendering using font8x8 if available
        if upside_down:
            try:
                from font8x8 import FONT8X8
                for char_idx, char in enumerate(text):
                    if char in FONT8X8:
                        bitmap = FONT8X8[char]
                        cx = x + char_idx * 8 * scale
                        cy = y
                        for i in range(8):
                            for j in range(8):
                                if (bitmap[i] << j) & 0x80:
                                    # Rotated and Scaled
                                    # j is bit position (0-7), i is row (0-7)
                                    # Normal: cx + j*scale, cy + i*scale
                                    # Rotated: oled.width - (cx + j*scale + scale), oled.height - (cy + i*scale + scale)
                                    fx = oled.width - (cx + j * scale + scale)
                                    fy = oled.height - (cy + i * scale + scale)
                                    if hasattr(oled, 'fill_rect'):
                                        oled.fill_rect(fx, fy, scale, scale, 1)
            except ImportError:
                if hasattr(oled, 'text'):
                    oled.text(text, oled.width - (x + len(text)*8), oled.height - (y + 8), 1)
        else:
            if hasattr(oled, 'text'):
                oled.text(text, x, y, 1)

def fill_rect(oled, x, y, w, h, color, upside_down=False):
    if not oled: return
    if upside_down:
        fx = oled.width - (x + w)
        fy = oled.height - (y + h)
        if hasattr(oled, 'fill_rect'):
            oled.fill_rect(fx, fy, w, h, color)
    else:
        if hasattr(oled, 'fill_rect'):
            oled.fill_rect(x, y, w, h, color)

def _text(oled, text, x, y, upside_down=False, color=1):
    if not oled or not text: return
    try:
        if not upside_down: raise Exception("skip") # fast path
        import framebuf
        w = len(text) * 8
        h = 8
        buf = bytearray(w * h // 8)
        fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_VLSB)
        fb.text(text, 0, 0, 1)
        for i in range(w):
            for j in range(h):
                if fb.pixel(i, j):
                    fx = oled.width - (x + i + 1)
                    fy = oled.height - (y + j + 1)
                    if 0 <= fx < oled.width and 0 <= fy < oled.height:
                        if hasattr(oled, 'pixel'): oled.pixel(fx, fy, color)
    except Exception:
        if upside_down:
            # Fallback rotated rendering using font8x8 if available
            try:
                from font8x8 import FONT8X8
                for char_idx, char in enumerate(text):
                    if char in FONT8X8:
                        bitmap = FONT8X8[char]
                        cx = x + char_idx * 8
                        cy = y
                        for i in range(8):
                            for j in range(8):
                                if (bitmap[i] << j) & 0x80:
                                    fx = oled.width - (cx + j + 1)
                                    fy = oled.height - (cy + i + 1)
                                    if 0 <= fx < oled.width and 0 <= fy < oled.height:
                                        if hasattr(oled, 'pixel'): oled.pixel(fx, fy, color)
            except ImportError:
                if hasattr(oled, 'text'):
                    oled.text(text, oled.width - (x + len(text)*8), oled.height - (y + 8), color)
        else:
            if hasattr(oled, 'text'):
                oled.text(text, x, y, color)

def render_face(oled, face_str, x_offset, upside_down=False, debug_mode=False):
    if not oled: return
    oled.fill(0)

    base_x = _centered_x(oled, face_str)
    final_x = base_x + x_offset

    _draw_ascii(oled, face_str, final_x, 20, 2, upside_down)

    # --- Status overlay (DBG + mute) ---
    parts = []
    if debug_mode:
        parts.append("DBG")
    if settings_store.is_muted():
        parts.append("M")
    if parts:
        status = " ".join(parts)
        if upside_down:
            _text(oled, status, 0, oled.height - 8, True)
        else:
            _text(oled, status, oled.width - len(status)*8, 0, False)

    oled.show()


def update_oled(oled, mood="happy", value=None, upside_down=False, debug_mode=False, **kwargs):
    # Compatibility shim for text mode or legacy direct updates
    if mood == "text":
        if not oled: return
        line = kwargs.get("line")
        x = kwargs.get("x", 0)
        y = kwargs.get("y")

        if y is None:
            if line is not None:
                y = (line - 1) * 10
            else:
                y = 0
        
        text_to_display = str(value) if value is not None else ""
        color = kwargs.get("color", 1)
        _text(oled, text_to_display, x, y, upside_down, color)
        return

    # If a legacy script calls update_oled with a mood, route it through personality
    from personality import personality
    seq = personality.faces.get(mood, personality.faces.get('curious', ['(._.)']))
    face = seq[0] if seq else '(._.)'
    render_face(oled, face, 0, upside_down, debug_mode)
def reload_core():
    from personality import personality
    personality.reload()
