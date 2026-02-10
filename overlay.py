import tkinter as tk
from PIL import Image, ImageTk
from pynput import mouse, keyboard
import threading
import time
import os

# ==============================================================================
#   USER CONFIGURATION SECTION
# ==============================================================================

# -- Visual Colors --
WINDOW_BG_COLOR = '#222222'       # Background color (Hex code)
TEXT_COLOR = '#FFFFFF'            # Text color
MOVEMENT_DOT_COLOR = '#34abeb'    # Dot Color (Green)
DOT_BORDER_COLOR = '#FFFFFF'      # Ring color

# -- Movement Dot Settings --
MOVEMENT_DOT_SIZE = 4             # Radius of the dot
MOVEMENT_SENSITIVITY = 4.0        # Sensitivity
MOVEMENT_DECAY = 0.2              # Smoothness (0.1 to 1.0)

# -- Timing --
VISUAL_PERSISTENCE_SECONDS = 2.0  # How long keys stay visible

# -- Window Layout --
WINDOW_WIDTH = 320                # Increased width to fit the new layout
WINDOW_HEIGHT = 100
WINDOW_X_OFFSET = 20
WINDOW_Y_OFFSET = 80
WINDOW_ALPHA = 0.90

# -- Fonts --
FONT_NAME = "Segoe UI"
FONT_SIZE = 10
FONT_WEIGHT = "bold"

# -- Mouse Image Settings --
MOUSE_IMAGE_SIZE = (60, 60)

# ==============================================================================
#   GLOBAL STATE MANAGEMENT
# ==============================================================================

held_keys = set()
held_mouse_buttons = set()
visual_expiry_times = {}

current_dx = 0
current_dy = 0
target_dx = 0
target_dy = 0
last_mouse_x = 0
last_mouse_y = 0
first_move_detected = False

gui_elements = {
    "root": None,
    "mouse_img_label": None,
    "mouse_text_label": None,
    "key_text_label": None,
    "movement_canvas": None,
    "movement_dot": None,
    "images": {}
}

MODIFIER_MAP = {
    keyboard.Key.ctrl_l: "Ctrl", keyboard.Key.ctrl_r: "Ctrl",
    keyboard.Key.shift_l: "Shift", keyboard.Key.shift_r: "Shift",
    keyboard.Key.alt_l: "Alt", keyboard.Key.alt_r: "Alt",
    keyboard.Key.cmd: "Cmd", keyboard.Key.cmd_r: "Cmd",
    keyboard.Key.space: "Space", keyboard.Key.enter: "Enter",
    keyboard.Key.backspace: "Backspace", keyboard.Key.tab: "Tab",
    keyboard.Key.esc: "Esc", keyboard.Key.caps_lock: "Caps"
}

# ==============================================================================
#   HELPER FUNCTIONS
# ==============================================================================

def load_images():
    image_names = {
        "neutral": "mouse_neutral.png", "lmb": "mouse_lmb.png", 
        "mmb": "mouse_mmb.png", "rmb": "mouse_rmb.png", 
        "lmb_mmb": "mouse_lmb_mmb.png", "lmb_rmb": "mouse_lmb_rmb.png",
        "mmb_rmb": "mouse_mmb_rmb.png", "lmb_mmb_rmb": "mouse_lmb_mmb_rmb.png",
        "scroll_up": "mouse_scroll_up.png", "scroll_down": "mouse_scroll_down.png",
    }
    script_dir = os.path.dirname(os.path.abspath(__file__))
    loaded_images = {}
    
    for key, filename in image_names.items():
        path = os.path.join(script_dir, filename)
        try:
            if os.path.exists(path):
                img = Image.open(path).resize(MOUSE_IMAGE_SIZE, Image.Resampling.LANCZOS)
                loaded_images[key] = ImageTk.PhotoImage(img)
            else:
                raise FileNotFoundError
        except:
            img = Image.new('RGBA', MOUSE_IMAGE_SIZE, (80, 80, 80, 100))
            loaded_images[key] = ImageTk.PhotoImage(img)
            
    if "neutral" not in loaded_images:
        loaded_images["neutral"] = ImageTk.PhotoImage(Image.new('RGBA', MOUSE_IMAGE_SIZE, (80, 80, 80, 100)))
    
    gui_elements["images"] = loaded_images

def is_visually_active(item_id, physically_held_set):
    if item_id in physically_held_set: return True
    if item_id in visual_expiry_times:
        if time.time() < visual_expiry_times[item_id]: return True
        else: del visual_expiry_times[item_id]
    return False

def update_movement_visualizer():
    global current_dx, current_dy, target_dx, target_dy
    
    if not gui_elements["movement_canvas"]: return

    # Smooth interpolation
    current_dx += (target_dx - current_dx) * MOVEMENT_DECAY
    current_dy += (target_dy - current_dy) * MOVEMENT_DECAY

    target_dx = 0
    target_dy = 0

    center = 30
    max_range = 25 
    
    disp_x = max(-max_range, min(max_range, current_dx * MOVEMENT_SENSITIVITY))
    disp_y = max(-max_range, min(max_range, current_dy * MOVEMENT_SENSITIVITY))

    r = MOVEMENT_DOT_SIZE
    x1 = (center + disp_x) - r
    y1 = (center + disp_y) - r
    x2 = (center + disp_x) + r
    y2 = (center + disp_y) + r
    
    gui_elements["movement_canvas"].coords(gui_elements["movement_dot"], x1, y1, x2, y2)

def update_overlay():
    if not gui_elements["root"]: return

    # --- Mouse Buttons ---
    show_left = is_visually_active('left', held_mouse_buttons)
    show_middle = is_visually_active('middle', held_mouse_buttons)
    show_right = is_visually_active('right', held_mouse_buttons)
    show_scroll_up = is_visually_active('scroll_up', held_mouse_buttons)
    show_scroll_down = is_visually_active('scroll_down', held_mouse_buttons)

    img_key = "neutral"
    if show_scroll_up: img_key = "scroll_up"
    elif show_scroll_down: img_key = "scroll_down"
    elif show_left and show_middle and show_right: img_key = "lmb_mmb_rmb"
    elif show_left and show_middle: img_key = "lmb_mmb"
    elif show_left and show_right: img_key = "lmb_rmb"
    elif show_middle and show_right: img_key = "mmb_rmb"
    elif show_left: img_key = "lmb"
    elif show_middle: img_key = "mmb"
    elif show_right: img_key = "rmb"
    
    gui_elements["mouse_img_label"].config(image=gui_elements["images"].get(img_key, gui_elements["images"]["neutral"]))

    # --- Text Labels ---
    m_text = []
    if show_left: m_text.append("LMB")
    if show_middle: m_text.append("MMB")
    if show_right: m_text.append("RMB")
    if show_scroll_up: m_text.append("Scroll ↑")
    if show_scroll_down: m_text.append("Scroll ↓")
    gui_elements["mouse_text_label"].config(text="Mouse: " + " ".join(m_text))

    # --- Keyboard Text ---
    all_candidates = set(held_keys) | set(visual_expiry_times.keys())
    active_keys = []
    for key in all_candidates:
        if is_visually_active(key, held_keys):
            k_str = str(key).upper().replace("'", "")
            if len(k_str) > 10: k_str = "..."
            if k_str not in active_keys: active_keys.append(k_str)
    
    active_keys.sort(key=lambda x: (len(x) < 2, x))
    gui_elements["key_text_label"].config(text="Keys: " + " + ".join(active_keys))

    # --- Update Dot ---
    update_movement_visualizer()
    gui_elements["root"].after(16, update_overlay)

# ==============================================================================
#   INPUT LISTENERS
# ==============================================================================

def on_move(x, y):
    global target_dx, target_dy, last_mouse_x, last_mouse_y, first_move_detected
    if not first_move_detected:
        last_mouse_x, last_mouse_y = x, y
        first_move_detected = True
        return
    dx = x - last_mouse_x
    dy = y - last_mouse_y
    last_mouse_x, last_mouse_y = x, y
    target_dx += dx
    target_dy += dy

def on_click(x, y, button, pressed):
    btn = button.name
    if pressed: held_mouse_buttons.add(btn)
    else:
        held_mouse_buttons.discard(btn)
        visual_expiry_times[btn] = time.time() + VISUAL_PERSISTENCE_SECONDS

def on_scroll(x, y, dx, dy):
    direction = 'scroll_up' if dy > 0 else 'scroll_down'
    visual_expiry_times[direction] = time.time() + VISUAL_PERSISTENCE_SECONDS

def on_key_press(key):
    if hasattr(key, 'name'): name = MODIFIER_MAP.get(key, key.name)
    elif hasattr(key, 'char'): name = key.char
    else: name = str(key)
    if name: held_keys.add(name)

def on_key_release(key):
    if hasattr(key, 'name'): name = MODIFIER_MAP.get(key, key.name)
    elif hasattr(key, 'char'): name = key.char
    else: name = str(key)
    if name:
        held_keys.discard(name)
        visual_expiry_times[name] = time.time() + VISUAL_PERSISTENCE_SECONDS

# ==============================================================================
#   GUI SETUP (MODIFIED LAYOUT)
# ==============================================================================

def setup_gui():
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.attributes('-alpha', WINDOW_ALPHA)
    root.config(bg=WINDOW_BG_COLOR, cursor="fleur")
    
    w, h = WINDOW_WIDTH, WINDOW_HEIGHT
    x = root.winfo_screenwidth() - w - WINDOW_X_OFFSET
    y = root.winfo_screenheight() - h - WINDOW_Y_OFFSET
    root.geometry(f"{w}x{h}+{x}+{y}")
    
    load_images()
    
    # --- Create 3 Columns ---
    # 1. Left: Text
    frame_text = tk.Frame(root, bg=WINDOW_BG_COLOR)
    frame_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5))
    
    # 2. Middle: Mouse Image (Now in the middle)
    frame_image = tk.Frame(root, bg=WINDOW_BG_COLOR)
    frame_image.pack(side=tk.LEFT, padx=5)

    # 3. Right: Movement Visualizer (Now on the far right)
    frame_dot = tk.Frame(root, bg=WINDOW_BG_COLOR)
    frame_dot.pack(side=tk.LEFT, padx=(5, 10))

    # --- Populate Frame 1 (Text) ---
    gui_elements["mouse_text_label"] = tk.Label(frame_text, text="Mouse:", font=(FONT_NAME, FONT_SIZE, FONT_WEIGHT), fg=TEXT_COLOR, bg=WINDOW_BG_COLOR, anchor='w')
    gui_elements["mouse_text_label"].pack(fill='x', pady=2)
    
    gui_elements["key_text_label"] = tk.Label(frame_text, text="Keys:", font=(FONT_NAME, FONT_SIZE, FONT_WEIGHT), fg=TEXT_COLOR, bg=WINDOW_BG_COLOR, anchor='w')
    gui_elements["key_text_label"].pack(fill='x', pady=2)

    # --- Populate Frame 2 (Mouse Image) ---
    gui_elements["mouse_img_label"] = tk.Label(frame_image, image=gui_elements["images"]["neutral"], bg=WINDOW_BG_COLOR)
    gui_elements["mouse_img_label"].pack()

    # --- Populate Frame 3 (Movement Dot) ---
    canvas_size = 60
    c = tk.Canvas(frame_dot, width=canvas_size, height=canvas_size, bg=WINDOW_BG_COLOR, highlightthickness=0)
    c.pack()
    
    # Static Ring
    pad = 2
    c.create_oval(pad, pad, canvas_size-pad, canvas_size-pad, outline=DOT_BORDER_COLOR, width=2)
    
    # Moving Dot
    center = canvas_size // 2
    r = MOVEMENT_DOT_SIZE
    dot = c.create_oval(center-r, center-r, center+r, center+r, fill=MOVEMENT_DOT_COLOR, outline="")
    
    gui_elements["movement_canvas"] = c
    gui_elements["movement_dot"] = dot
    gui_elements["root"] = root
    
    # Drag logic
    def start_move(e): root.x = e.x; root.y = e.y
    def do_move(e): root.geometry(f"+{root.winfo_x() + e.x - root.x}+{root.winfo_y() + e.y - root.y}")
    
    root.bind("<ButtonPress-1>", start_move)
    root.bind("<B1-Motion>", do_move)
    root.bind("<Button-3>", lambda e: root.quit()) 

    return root

# ==============================================================================
#   MAIN
# ==============================================================================

def main():
    root = setup_gui()
    m_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll, on_move=on_move)
    k_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    m_listener.start()
    k_listener.start()
    update_overlay()
    try:
        root.mainloop()
    finally:
        m_listener.stop()
        k_listener.stop()

if __name__ == "__main__":
    main()  # <--- It MUST say 'start_launcher()', NOT 'main()'