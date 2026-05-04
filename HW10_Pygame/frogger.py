"""
Frogger-style game using Pygame Zero (pgzero)
Run with: pgzrun frogger.py
Install: pip install pgzero pygame
"""
 
import pgzrun
import random
import math
import struct
import wave
import os
import tempfile
import pygame
import serial

# Serial Port Handling:
ser = serial.Serial('/dev/ttyACM0', 115200)
 
# ── Sound generation ──────────────────────────────────────────────────────────
# We synthesize sounds procedurally so no audio files are needed.
 
SAMPLE_RATE = 44100
 
def _write_wav(path, samples):
    """Write a list of float samples (-1..1) to a 16-bit mono WAV file."""
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        packed = struct.pack(f"<{len(samples)}h",
                             *[max(-32767, min(32767, int(s * 32767))) for s in samples])
        wf.writeframes(packed)
 
def _make_jump_sound():
    """Short upward chirp — classic frog hop bleep."""
    duration = 0.10
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        progress = i / n
        # Frequency sweeps 300 Hz → 600 Hz
        freq = 300 + 300 * progress
        env  = math.sin(math.pi * progress)   # bell envelope
        samples.append(env * 0.6 * math.sin(2 * math.pi * freq * t))
    return samples
 
def _make_splat_sound():
    """Descending noise burst — squelchy splat."""
    duration = 0.45
    n = int(SAMPLE_RATE * duration)
    samples = []
    rng = random.Random(42)
    for i in range(n):
        t = i / SAMPLE_RATE
        progress = i / n
        env   = (1 - progress) ** 1.5          # fast decay
        noise = rng.uniform(-1, 1)
        # Low rumble underneath noise
        tone  = math.sin(2 * math.pi * (180 - 120 * progress) * t)
        samples.append(env * 0.7 * (0.6 * noise + 0.4 * tone))
    return samples
 
def _init_sounds():
    """Generate WAV files to a temp dir and load them as pygame Sound objects."""
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
    # pgzrun initialises pygame for us, but mixer may not be up yet at module
    # level — we defer actual loading to first use via a lazy wrapper below.
    tmp = tempfile.mkdtemp()
    jump_path  = os.path.join(tmp, "jump.wav")
    splat_path = os.path.join(tmp, "splat.wav")
    _write_wav(jump_path,  _make_jump_sound())
    _write_wav(splat_path, _make_splat_sound())
    return jump_path, splat_path
 
_JUMP_PATH, _SPLAT_PATH = _init_sounds()
 
# Lazy-loaded Sound objects (pygame.mixer must be initialised first)
_snd_jump  = None
_snd_splat = None
 
def _play_jump():
    global _snd_jump
    try:
        if _snd_jump is None:
            _snd_jump = pygame.mixer.Sound(_JUMP_PATH)
            _snd_jump.set_volume(0.55)
        _snd_jump.play()
    except Exception:
        pass
 
def _play_splat():
    global _snd_splat
    try:
        if _snd_splat is None:
            _snd_splat = pygame.mixer.Sound(_SPLAT_PATH)
            _snd_splat.set_volume(0.75)
        _snd_splat.play()
    except Exception:
        pass
 
# ── Window ────────────────────────────────────────────────────────────────────
WIDTH  = 600
HEIGHT = 700
TITLE  = "Frogger"
 
# ── Grid / Layout ─────────────────────────────────────────────────────────────
CELL       = 50          # pixels per grid cell
COLS       = WIDTH  // CELL   # 12
ROWS       = HEIGHT // CELL   # 14
 
ROAD_ROWS  = [3, 4, 5, 6]    # rows that have cars  (row 0 = top)
RIVER_ROWS = [7, 8, 9, 10]   # rows that have logs
SAFE_ROWS  = {0, 2, 6, 11, 13}  # grass / pavement
 
# ── Colors ────────────────────────────────────────────────────────────────────
C_BG        = (34,  139, 34)   # grass green
C_ROAD      = (60,   60, 60)   # dark grey
C_RIVER     = (30,  100, 200)  # blue
C_PAVEMENT  = (120, 120, 120)  # grey
C_FROG      = (50,  220, 50)   # bright green
C_EYE       = (255, 255, 255)
C_PUPIL     = (0,     0,   0)
C_CAR       = [(220,50,50),(255,165,0),(180,50,220),(255,220,0),(50,180,220)]
C_LOG       = (160, 100,  40)
C_LOG_RING  = (140,  80,  20)
C_LILY      = (0,   180,   0)
C_GOAL_FG   = (255, 215,   0)
C_HUD_BG    = (20,   20,  20)
C_HUD_TEXT  = (255, 255, 255)
C_DEAD      = (255,  50,  50)
C_WIN       = (255, 215,   0)
C_STRIPE    = (80,   80,  80)  # road lane stripe
 
# ── Lane config ───────────────────────────────────────────────────────────────
# Each lane: (direction, speed_cells_per_sec, [widths_in_cells], color_index)
LANE_CFG = {
    3: ( 1, 2.5, [2, 2, 3],    0),   # road – cars going right
    4: (-1, 3.0, [3, 2],       1),   # road – cars going left
    5: ( 1, 2.0, [2, 3, 2],    2),   # road – cars going right
    6: (-1, 3.5, [2, 2, 2, 3], 3),   # road – cars going left  (oops, row 6 is also safe_row → move to 5.5?)
    7: (-1, 1.5, [4, 5],       0),   # river – logs going left
    8: ( 1, 2.0, [3, 4],       0),   # river – logs going right
    9: (-1, 2.5, [5, 3],       0),   # river – logs going left
   10: ( 1, 1.8, [4, 3, 5],    0),   # river – logs going right
}
# Reassign road rows to avoid collision with safe_rows
ROAD_ROWS  = [3, 4, 5]
RIVER_ROWS = [7, 8, 9, 10]
LANE_CFG = {
    3:  ( 1, 2.5, [2, 2, 3],    0),
    4:  (-1, 3.0, [3, 2, 2],    1),
    5:  ( 1, 2.0, [2, 3, 2],    2),
    7:  (-1, 1.5, [4, 5],       0),
    8:  ( 1, 2.0, [3, 4],       0),
    9:  (-1, 2.5, [5, 3],       0),
   10:  ( 1, 1.8, [4, 3, 5],    0),
}
 
# ── Game state ────────────────────────────────────────────────────────────────
class Frog:
    def __init__(self):
        self.reset()
 
    def reset(self):
        self.col   = COLS // 2
        self.row   = ROWS - 1        # bottom row
        self.px    = self.col * CELL + CELL // 2
        self.py    = self.row * CELL + CELL // 2
        self.alive = True
        self.on_log = None           # reference to log the frog rides
 
    def move(self, dc, dr):
        nc, nr = self.col + dc, self.row + dr
        if 0 <= nc < COLS and 0 <= nr < ROWS:
            self.col, self.row = nc, nr
            self.px = self.col * CELL + CELL // 2
            self.py = self.row * CELL + CELL // 2
            self.on_log = None
 
    def center(self):
        return (self.px, self.py)
 
class Obstacle:
    """A car or log segment."""
    def __init__(self, row, x, w_cells, direction, speed, kind, color_idx=0):
        self.row   = row
        self.x     = float(x)          # left edge in pixels
        self.w     = w_cells * CELL
        self.h     = CELL - 8
        self.dir   = direction          # +1 right, -1 left
        self.speed = speed * CELL       # px/sec
        self.kind  = kind               # 'car' or 'log'
        self.color_idx = color_idx
 
    def update(self, dt):
        self.x += self.dir * self.speed * dt
        # Wrap around
        if self.dir > 0 and self.x > WIDTH:
            self.x = -self.w
        elif self.dir < 0 and self.x + self.w < 0:
            self.x = WIDTH
 
    def rect(self):
        y = self.row * CELL + 4
        return (int(self.x), y, self.w, self.h)
 
    def contains_px(self, px, py):
        """Check if pixel point (px,py) is inside this obstacle (for log riding)."""
        y = self.row * CELL
        return (self.x <= px <= self.x + self.w and
                y <= py <= y + CELL)
 
def build_obstacles():
    obs = []
    gap_cells = 3   # minimum gap between same-row obstacles
    for row, (direction, speed, widths, color_idx) in LANE_CFG.items():
        kind = 'log' if row in RIVER_ROWS else 'car'
        # Spread obstacles evenly
        total = sum(widths) + len(widths) * gap_cells
        scale = COLS / total
        x = 0.0
        for i, w in enumerate(widths):
            obs.append(Obstacle(row, x * CELL, w, direction, speed, kind, color_idx + i))
            x += w * scale + gap_cells * scale
    return obs
 
# ── Goal lily-pads ────────────────────────────────────────────────────────────
GOAL_ROW    = 1
NUM_GOALS   = 5
goal_cols   = [1, 3, 5, 7, 9]   # fixed columns for lily-pads
goals_filled = [False] * NUM_GOALS
 
# ── Global state ─────────────────────────────────────────────────────────────
frog        = Frog()
obstacles   = build_obstacles()
score       = 0
lives       = 3
level       = 1
game_state  = 'playing'   # 'playing' | 'dead' | 'win' | 'gameover'
dead_timer  = 0.0
move_cooldown = 0.0
 
# ── Input ─────────────────────────────────────────────────────────────────────
MOVE_DELAY = 0.12   # seconds between moves while key held
 
def on_key_down(key):
    global move_cooldown
    if game_state in ('dead', 'gameover'):
        if key == keys.RETURN:
            restart()
        return
    if game_state == 'win':
        if key == keys.RETURN:
            next_level()
        return
    handle_movement(key)
    handle_movement_pico()
    move_cooldown = MOVE_DELAY
 
# ── Handle Movement Functions ────────────────────────────────────────────────────────────────────
# Standard Function to Handle movement from the Keyboard:
def handle_movement(key):
    moved = False
    if   key == keys.W or key == keys.UP:    frog.move( 0, -1); moved = True
    elif key == keys.S or key == keys.DOWN:  frog.move( 0,  1); moved = True
    elif key == keys.A or key == keys.LEFT:  frog.move(-1,  0); moved = True
    elif key == keys.D or key == keys.RIGHT: frog.move( 1,  0); moved = True
    if moved:
        _play_jump()

# Pico2 W Movement Handler:
def handle_movement_pico():
    key = ''
    if ser.in_waiting > 0:
        key = ser.read(1)
        # extract the character key to interpret movement:
        key = key.decode('utf-8').lower()

    # Map Pico input to movement in frogger:
    if key == 'w':
        handle_movement(keys.W)
    elif key == 's':
        handle_movement(keys.S)
    elif key == 'a':
        handle_movement(keys.A)
    elif key == 'd':
        handle_movement(keys.D)
 
# ── Update ────────────────────────────────────────────────────────────────────
def update(dt):
    global game_state, dead_timer, score, lives, move_cooldown

    # If Pico Update Handler is active:
    handle_movement_pico() 
 
    if game_state == 'dead':
        dead_timer -= dt
        if dead_timer <= 0:
            if lives > 0:
                frog.reset()
                game_state = 'playing'
            else:
                game_state = 'gameover'
        return
 
    if game_state in ('win', 'gameover'):
        return
 
    # Move obstacles
    for ob in obstacles:
        ob.update(dt)
 
    # Continuous movement
    move_cooldown -= dt
 
    # ── Frog physics ──────────────────────────────────────────────────────────
    row = frog.row
 
    if row in RIVER_ROWS:
        # Must be on a log
        on_log = None
        for ob in obstacles:
            if ob.row == row and ob.kind == 'log' and ob.contains_px(frog.px, frog.py):
                on_log = ob
                break
        if on_log is None:
            die()
            return
        else:
            # Ride the log
            frog.px += on_log.dir * on_log.speed * dt
            frog.col = int(frog.px // CELL)
            # Fell off screen?
            if frog.px < 0 or frog.px > WIDTH:
                die()
                return
 
    elif row in ROAD_ROWS:
        # Check collision with cars
        for ob in obstacles:
            if ob.row == row and ob.kind == 'car':
                rx, ry, rw, rh = ob.rect()
                if rx <= frog.px <= rx + rw and ry <= frog.py <= ry + rh:
                    die()
                    return
 
    elif row == GOAL_ROW:
        # Check if frog landed on a lily-pad goal
        for i, gc in enumerate(goal_cols):
            if frog.col == gc and not goals_filled[i]:
                goals_filled[i] = True
                score += 100 * level
                frog.reset()
                if all(goals_filled):
                    game_state = 'win'
                return
        # Landed in water (not on a pad)
        die()
        return
 
def die():
    global game_state, dead_timer, lives
    frog.alive = False
    lives -= 1
    game_state = 'dead'
    dead_timer = 1.2
    _play_splat()
 
def restart():
    global frog, obstacles, score, lives, level, game_state, goals_filled
    frog           = Frog()
    obstacles      = build_obstacles()
    score          = 0
    lives          = 3
    level          = 1
    goals_filled   = [False] * NUM_GOALS
    game_state     = 'playing'
 
def next_level():
    global frog, obstacles, level, game_state, goals_filled
    level         += 1
    goals_filled   = [False] * NUM_GOALS
    frog.reset()
    # Speed up obstacles
    for ob in obstacles:
        ob.speed *= 1.15
    game_state = 'playing'
 
# ── Draw helpers ──────────────────────────────────────────────────────────────
def row_y(r):
    return r * CELL
 
def draw_background():
    screen.fill(C_BG)
 
    # Goal row – water strip with lily pads
    screen.draw.filled_rect(Rect(0, row_y(GOAL_ROW), WIDTH, CELL), C_RIVER)
    for gc in goal_cols:
        cx = gc * CELL + CELL // 2
        cy = row_y(GOAL_ROW) + CELL // 2
        screen.draw.filled_circle((cx, cy), CELL // 2 - 4, C_LILY)
        screen.draw.circle((cx, cy), CELL // 2 - 4, (0, 120, 0))
 
    # Safe middle strip
    screen.draw.filled_rect(Rect(0, row_y(2), WIDTH, CELL), C_PAVEMENT)
 
    # Road rows
    for r in ROAD_ROWS:
        screen.draw.filled_rect(Rect(0, row_y(r), WIDTH, CELL), C_ROAD)
        # Dashed centre line
        for x in range(0, WIDTH, 20):
            screen.draw.filled_rect(Rect(x, row_y(r) + CELL // 2 - 2, 10, 4), C_STRIPE)
 
    # Safe strip between road & river
    screen.draw.filled_rect(Rect(0, row_y(6), WIDTH, CELL), C_PAVEMENT)
 
    # River rows
    for r in RIVER_ROWS:
        screen.draw.filled_rect(Rect(0, row_y(r), WIDTH, CELL), C_RIVER)
 
    # Bottom pavement
    screen.draw.filled_rect(Rect(0, row_y(11), WIDTH, CELL * 3), C_PAVEMENT)
 
    # HUD bar at very bottom
    screen.draw.filled_rect(Rect(0, HEIGHT - CELL, WIDTH, CELL), C_HUD_BG)
 
def draw_obstacles():
    for ob in obstacles:
        x, y, w, h = ob.rect()
        if ob.kind == 'car':
            color = C_CAR[ob.color_idx % len(C_CAR)]
            screen.draw.filled_rect(Rect(x, y, w, h), color)
            # Windshield
            ww = min(w // 3, 20)
            screen.draw.filled_rect(Rect(x + w // 2 - ww // 2, y + 4, ww, h - 8), (200, 230, 255))
            # Wheels
            for wx in [x + 6, x + w - 14]:
                screen.draw.filled_circle((wx + 4, y + h), 5, (30, 30, 30))
        else:  # log
            screen.draw.filled_rect(Rect(x, y, w, h), C_LOG)
            # Wood rings
            for rx in range(x + w // 4, x + w, w // 3):
                screen.draw.filled_rect(Rect(rx - 3, y, 6, h), C_LOG_RING)
            # End caps
            screen.draw.filled_rect(Rect(x,         y, 6, h), C_LOG_RING)
            screen.draw.filled_rect(Rect(x + w - 6, y, 6, h), C_LOG_RING)
 
def draw_goals():
    for i, gc in enumerate(goal_cols):
        if goals_filled[i]:
            cx = gc * CELL + CELL // 2
            cy = row_y(GOAL_ROW) + CELL // 2
            screen.draw.filled_circle((cx, cy), CELL // 2 - 4, C_GOAL_FG)
            screen.draw.circle((cx, cy), CELL // 2 - 4, (200, 160, 0))
 
def draw_frog():
    cx, cy = frog.px, frog.py
    r = CELL // 2 - 5
    color = C_DEAD if not frog.alive else C_FROG
 
    # Body
    screen.draw.filled_circle((int(cx), int(cy)), r, color)
 
    # Eyes
    for ex in [-r // 2, r // 2]:
        screen.draw.filled_circle((int(cx + ex), int(cy - r // 2)), 5, C_EYE)
        screen.draw.filled_circle((int(cx + ex), int(cy - r // 2)), 2, C_PUPIL)
 
    # Legs
    for lx in [-r, r]:
        screen.draw.line((int(cx), int(cy + r // 2)),
                         (int(cx + lx), int(cy + r + 6)), color)
        screen.draw.line((int(cx + lx), int(cy + r + 6)),
                         (int(cx + lx + (4 if lx > 0 else -4)), int(cy + r + 12)), color)
 
def draw_hud():
    # Lives
    for i in range(lives):
        screen.draw.filled_circle((20 + i * 28, HEIGHT - CELL // 2), 10, C_FROG)
 
    # Score
    screen.draw.text(f"Score: {score}", (WIDTH // 2 - 50, HEIGHT - CELL + 8),
                     color=C_HUD_TEXT, fontsize=24)
 
    # Level
    screen.draw.text(f"Lvl {level}", (WIDTH - 70, HEIGHT - CELL + 8),
                     color=C_HUD_TEXT, fontsize=24)
 
def draw_overlay():
    if game_state == 'dead':
        screen.draw.text("SPLAT!", center=(WIDTH // 2, HEIGHT // 2 - 20),
                         color=C_DEAD, fontsize=60)
 
    elif game_state == 'gameover':
        screen.draw.filled_rect(Rect(WIDTH//4, HEIGHT//3, WIDTH//2, HEIGHT//4), (0,0,0))
        screen.draw.text("GAME OVER", center=(WIDTH // 2, HEIGHT // 2 - 30),
                         color=C_DEAD, fontsize=48)
        screen.draw.text(f"Final score: {score}", center=(WIDTH // 2, HEIGHT // 2 + 10),
                         color=C_HUD_TEXT, fontsize=28)
        screen.draw.text("ENTER to restart", center=(WIDTH // 2, HEIGHT // 2 + 42),
                         color=C_HUD_TEXT, fontsize=22)
 
    elif game_state == 'win':
        screen.draw.filled_rect(Rect(WIDTH//4, HEIGHT//3, WIDTH//2, HEIGHT//4), (0,0,0))
        screen.draw.text("YOU WIN!", center=(WIDTH // 2, HEIGHT // 2 - 30),
                         color=C_WIN, fontsize=48)
        screen.draw.text(f"Score: {score}", center=(WIDTH // 2, HEIGHT // 2 + 10),
                         color=C_HUD_TEXT, fontsize=28)
        screen.draw.text("ENTER for next level", center=(WIDTH // 2, HEIGHT // 2 + 42),
                         color=C_HUD_TEXT, fontsize=22)
 
# ── Main draw ─────────────────────────────────────────────────────────────────
def draw():
    draw_background()
    draw_goals()
    draw_obstacles()
    draw_frog()
    draw_hud()
    draw_overlay()
 
pgzrun.go()
