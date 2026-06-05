"""
Servo Motor Driving Game — pgzrun
==================================
Hardware Inputs:
  - Servo encoder position  →  steering angle (turning)
  - Force sensor value      →  normalized speed (throttle)

Haptic/Warning Interface:
  - on_obstacle_collision() is called whenever the car hits a road obstacle.
    Replace the body of that function with your haptic / motor-vibration logic.

Controls (keyboard fallback when no hardware is connected):
  LEFT / RIGHT arrows  →  steer
  UP arrow             →  accelerate
  R key                →  reset car position

Run with:
    pgzrun driving_game.py

Dependencies:
    pip install pgzero pygame
"""

import pgzrun
import pygame
import math
import random
import time
import serial

# ── Window ──────────────────────────────────────────────────────────────────
WIDTH  = 900
HEIGHT = 700
TITLE  = "Servo Driving Game"

# ── Hardware input stubs ─────────────────────────────────────────────────────
import threading

# Global state for hardware
hw_encoder = None
hw_force = None
initial_encoder = None
initial_force = None
tare_countdown = 150

try:
    # Adjust this port to match your system (e.g., /dev/ttyACM0 or /dev/ttyUSB0)
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
except Exception as e:
    print(f"Serial port not found or could not be opened: {e}")
    ser = None

def serial_worker():
    global hw_encoder, hw_force, initial_encoder, initial_force, tare_countdown
    while True:
        if ser and ser.in_waiting:
            try:
                # Read a line from the Pico
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                # Pico format: "Angle: <val> \t Force: <val>"
                if line.startswith('Angle:') and 'Force:' in line:
                    parts = line.split('\t')
                    angle_str = parts[0].replace('Angle:', '').strip()
                    force_str = parts[1].replace('Force:', '').strip()
                    raw_enc = float(angle_str)
                    raw_force = float(force_str)
                    
                    if tare_countdown > 0:
                        tare_countdown -= 1
                        continue  # Skip processing until hardware settles
                    
                    # Auto-calibrate: treat the first settled angle seen as "center"
                    if initial_encoder is None:
                        initial_encoder = raw_enc
                        
                    if initial_force is None:
                        initial_force = raw_force
                        
                    diff = raw_enc - initial_encoder
                    # Handle 0-360 wrap around
                    if diff > 180:
                        diff -= 360
                    elif diff < -180:
                        diff += 360
                        
                    hw_encoder = diff
                        
                    # Tare the force sensor and take absolute value in case pressing decreases it
                    tared_force = abs(raw_force - initial_force)
                    hw_force = tared_force
            except Exception:
                pass

if ser:
    threading.Thread(target=serial_worker, daemon=True).start()


def read_encoder_position() -> float:
    """
    Return the current servo encoder value relative to its starting position.
    """
    return hw_encoder


def read_force_sensor() -> float:
    """
    Return the current force sensor reading.
    """
    return hw_force


# ── Haptic / warning callback ────────────────────────────────────────────────
def on_obstacle_collision(car_speed: float, obstacle_type: str):
    """
    Called every time the player car hits a road obstacle.
    """
    if ser:
        ser.write(b"B\n")
    print(f"[HAPTIC WARNING] Hit '{obstacle_type}' at speed {car_speed:.1f} px/s")


# ── Constants ────────────────────────────────────────────────────────────────
MAX_SPEED          = 400   # pixels per second at maximum force
ENCODER_RANGE      = 180   # ± degrees → maps to ± MAX_STEER_ANGLE
MAX_STEER_ANGLE    = 30    # degrees of visual car rotation
FORCE_MAX_RAW      = 30000    # adjusted for normal load cell sensitivity
SCROLL_SPEED_BASE  = 3     # road stripe scroll speed multiplier
OBSTACLE_SPAWN_Y   = -60   # spawn above screen
OBSTACLE_INTERVAL  = 1.8   # seconds between obstacle spawns (decreases with speed)
ROAD_LEFT          = 180
ROAD_RIGHT         = 720

# Colours
C_SKY     = (135, 206, 235)
C_GRASS   = ( 34, 139,  34)
C_ROAD    = ( 50,  50,  50)
C_STRIPE  = (255, 255, 255)
C_CAR     = (220,  30,  30)
C_WHEEL   = ( 20,  20,  20)
C_CONE    = (255, 140,   0)
C_BARRIER = (200,  30,  30)
C_ROCK    = (130, 110,  90)
C_HUD     = (255, 255, 255)
C_HUD_BG  = (  0,   0,   0)
C_WARN    = (255,  60,  60)
C_GRAVEL  = (180, 160, 130)

# ── Game state ───────────────────────────────────────────────────────────────
class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        global initial_encoder, initial_force, tare_countdown
        initial_encoder = None
        initial_force = None
        tare_countdown = 150
        
        self.car_x        = WIDTH // 2
        self.car_y        = HEIGHT - 140
        self.steer_angle  = 0.0    # degrees
        self.speed        = 0.0    # pixels/sec
        self.distance     = 0      # total distance travelled (score)
        self.road_offset  = 0      # vertical scroll offset for road stripes
        self.obstacles    = []     # list of {"x", "y", "kind", "w", "h"}
        self.spawn_timer  = 0.0
        self.flash_timer  = 0.0    # warning flash duration
        self.off_road     = False
        self.collision    = False
        self.haptic_state = "C"

G = GameState()

# ── Obstacle helpers ─────────────────────────────────────────────────────────
OBSTACLE_KINDS = [
    {"kind": "cone",    "w": 22, "h": 30, "color": C_CONE},
    {"kind": "barrier", "w": 80, "h": 22, "color": C_BARRIER},
    {"kind": "rock",    "w": 34, "h": 26, "color": C_ROCK},
]

def spawn_obstacle():
    template = random.choice(OBSTACLE_KINDS)
    x = random.randint(ROAD_LEFT + template["w"]//2, ROAD_RIGHT - template["w"]//2)
    G.obstacles.append({
        "x": x, "y": OBSTACLE_SPAWN_Y,
        "kind": template["kind"],
        "w": template["w"], "h": template["h"],
        "color": template["color"],
    })

def car_rect():
    """Return (left, top, right, bottom) of the car hitbox."""
    cw, ch = 36, 60
    return (G.car_x - cw//2, G.car_y - ch//2,
            G.car_x + cw//2, G.car_y + ch//2)

def rects_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1

# ── Input normalisation ──────────────────────────────────────────────────────
def get_steer_and_speed(dt):
    """
    Returns (steer_angle_degrees, speed_px_per_sec).
    Uses hardware if available, otherwise keyboard.
    """
    enc = read_encoder_position()
    frc = read_force_sensor()

    # --- Steering ---
    if enc is not None:
        # Clamp and map encoder to steer angle
        enc_clamped = max(-ENCODER_RANGE, min(ENCODER_RANGE, enc))
        steer = (enc_clamped / ENCODER_RANGE) * MAX_STEER_ANGLE
    else:
        # Keyboard fallback
        steer = G.steer_angle
        if keyboard.left:
            steer = max(-MAX_STEER_ANGLE, steer - 120 * dt)
        elif keyboard.right:
            steer = min( MAX_STEER_ANGLE, steer + 120 * dt)
        else:
            steer *= (1 - 5 * dt)   # self-centering

    # --- Speed ---
    if frc is not None:
        # Add a deadzone (10% of max force) to ignore load cell drift/hysteresis when released
        deadzone = FORCE_MAX_RAW * 0.1
        if frc < deadzone:
            frc_clamped = 0
        else:
            frc_clamped = max(0, min(FORCE_MAX_RAW, frc))
            
        target_speed = (frc_clamped / FORCE_MAX_RAW) * MAX_SPEED
        
        # Accelerate instantly, but decelerate/coast smoothly to hide jitter
        if target_speed < G.speed:
            speed = G.speed + (target_speed - G.speed) * min(1.0, 5 * dt)
        else:
            speed = target_speed
    else:
        # Keyboard fallback: hold UP to accelerate
        target = MAX_SPEED * 0.6 if keyboard.up else 0
        speed = G.speed + (target - G.speed) * min(1.0, 4 * dt)

    MIN_SPEED = 5.0 / 0.12  # 5 km/h converted to pixels/sec
    speed = max(MIN_SPEED, speed)

    return steer, speed

# ── Update ───────────────────────────────────────────────────────────────────
def update(dt):
    G.steer_angle, G.speed = get_steer_and_speed(dt)

    # Move car horizontally based on steering
    lateral = math.sin(math.radians(G.steer_angle)) * G.speed * dt * 5.0
    G.car_x = max(60, min(WIDTH - 60, G.car_x + lateral))

    # Scroll road
    G.road_offset = (G.road_offset + G.speed * dt * SCROLL_SPEED_BASE) % 80

    # Accumulate distance
    G.distance += G.speed * dt

    # Spawn obstacles
    interval = max(0.5, OBSTACLE_INTERVAL - G.speed / MAX_SPEED * 0.8)
    G.spawn_timer += dt
    if G.spawn_timer >= interval:
        spawn_obstacle()
        G.spawn_timer = 0.0

    # Move obstacles downward
    obs_speed = G.speed * 1.4
    alive = []
    G.collision = False
    cl, ct, cr, cb = car_rect()

    for o in G.obstacles:
        o["y"] += obs_speed * dt
        if o["y"] > HEIGHT + 80:
            continue
        # Collision check
        ow, oh = o["w"], o["h"]
        if rects_overlap(cl, ct, cr, cb,
                         o["x"]-ow//2, o["y"]-oh//2,
                         o["x"]+ow//2, o["y"]+oh//2):
            G.collision = True
            G.flash_timer = 0.35
            on_obstacle_collision(G.speed, o["kind"])
            G.speed *= 0.35   # slow down on hit
        else:
            alive.append(o)

    if not G.collision:
        G.obstacles = alive
    else:
        G.obstacles = [o for o in alive]   # remove hit obstacle

    # Off-road detection
    G.off_road = G.car_x < ROAD_LEFT + 20 or G.car_x > ROAD_RIGHT - 20
    
    new_haptic_state = "C"
    if G.car_x < ROAD_LEFT + 20:
        new_haptic_state = "L"
        G.speed *= (1 - 2.5 * dt)   # friction on gravel
    elif G.car_x > ROAD_RIGHT - 20:
        new_haptic_state = "R"
        G.speed *= (1 - 2.5 * dt)   # friction on gravel
        
    if new_haptic_state != G.haptic_state:
        G.haptic_state = new_haptic_state
        if ser:
            ser.write(f"{G.haptic_state}\n".encode('utf-8'))

    # Flash timer
    if G.flash_timer > 0:
        G.flash_timer -= dt

    # Reset
    if keyboard.r:
        G.reset()

# ── Draw helpers ─────────────────────────────────────────────────────────────
def draw_road(screen):
    # Sky
    screen.draw.filled_rect(Rect(0, 0, WIDTH, HEIGHT // 2), C_SKY)
    # Grass
    screen.draw.filled_rect(Rect(0, HEIGHT // 2, WIDTH, HEIGHT // 2), C_GRASS)
    # Road surface
    screen.draw.filled_rect(Rect(ROAD_LEFT, 0, ROAD_RIGHT - ROAD_LEFT, HEIGHT), C_ROAD)
    # Gravel shoulders
    screen.draw.filled_rect(Rect(ROAD_LEFT - 30, 0, 30, HEIGHT), C_GRAVEL)
    screen.draw.filled_rect(Rect(ROAD_RIGHT,     0, 30, HEIGHT), C_GRAVEL)
    # Lane stripes (scrolling dashes)
    cx = WIDTH // 2
    stripe_h = 40
    for y_base in range(-80, HEIGHT + 80, 80):
        y = int(y_base + G.road_offset) % (HEIGHT + 160) - 80
        screen.draw.filled_rect(Rect(cx - 4, y, 8, stripe_h), C_STRIPE)
    # Road edges
    screen.draw.line((ROAD_LEFT,  0), (ROAD_LEFT,  HEIGHT), (255,255,100))
    screen.draw.line((ROAD_RIGHT, 0), (ROAD_RIGHT, HEIGHT), (255,255,100))


def draw_obstacles(screen):
    for o in G.obstacles:
        x, y, w, h = int(o["x"]), int(o["y"]), o["w"], o["h"]
        if o["kind"] == "cone":
            # Draw a simple triangle cone
            pts = [(x, y - h//2), (x - w//2, y + h//2), (x + w//2, y + h//2)]           
            pygame.draw.polygon(screen.surface, C_CONE, pts)
            pygame.draw.polygon(screen.surface, (255,255,255), pts, 1)
            screen.draw.filled_rect(Rect(x - w//2, y + h//2 - 5, w, 5), (255,255,255))
        elif o["kind"] == "barrier":
            screen.draw.filled_rect(Rect(x - w//2, y - h//2, w, h), C_BARRIER)
            # White stripes
            for i in range(0, w, 16):
                if (i // 16) % 2 == 0:
                    screen.draw.filled_rect(Rect(x - w//2 + i, y - h//2, 8, h), (255,255,255))
        else:  # rock
            pygame.draw.ellipse(screen.surface, C_ROCK, Rect(x - w//2, y - h//2, w, h))
            pygame.draw.ellipse(screen.surface, (80, 60, 40), Rect(x - w//2, y - h//2, w, h), 1)


def draw_car(screen):
    cx, cy = int(G.car_x), int(G.car_y)
    angle_rad = math.radians(G.steer_angle * 0.6)   # visual lean
    cw, ch = 36, 60

    # Body
    screen.draw.filled_rect(Rect(cx - cw//2, cy - ch//2, cw, ch), C_CAR)
    # Windshield
    screen.draw.filled_rect(Rect(cx - 12, cy - 22, 24, 16), (160, 220, 255))
    # Rear window
    screen.draw.filled_rect(Rect(cx - 10, cy + 10, 20, 12), (160, 220, 255))
    # Wheels
    ww, wh = 10, 18
    offsets = [(-cw//2 - 2, -18), (cw//2 - 8, -18),
               (-cw//2 - 2,  10), (cw//2 - 8,  10)]
    for wx, wy in offsets:
        screen.draw.filled_rect(Rect(cx + wx, cy + wy, ww, wh), C_WHEEL)
    # Steering indicator line
    lx = cx + int(math.sin(angle_rad) * 28)
    ly = cy - int(math.cos(angle_rad) * 28)
    screen.draw.line((cx, cy), (lx, ly), (255, 220, 0))


def draw_hud(screen):
    speed_kmh = int(G.speed * 0.12)
    dist_m    = int(G.distance * 0.05)
    steer_pct = int(G.steer_angle / MAX_STEER_ANGLE * 100)

    # Speed gauge background
    screen.draw.filled_rect(Rect(10, 10, 160, 90), (0, 0, 0, 180))
    screen.draw.text(f"SPEED", (20, 15), color=C_HUD, fontsize=18)
    screen.draw.text(f"{speed_kmh} km/h", (20, 36), color=(100, 255, 100), fontsize=28)
    screen.draw.text(f"DIST: {dist_m} m", (20, 72), color=C_HUD, fontsize=18)

    # Steering indicator
    screen.draw.filled_rect(Rect(10, 110, 160, 40), (0, 0, 0, 180))
    screen.draw.text(f"STEER: {steer_pct:+d}%", (20, 120), color=(255, 220, 100), fontsize=18)

    # Off-road warning
    if G.off_road:
        screen.draw.text("⚠ OFF ROAD", (WIDTH//2 - 80, 20),
                         color=(255, 220, 0), fontsize=26)

    # Collision flash
    if G.flash_timer > 0:
        alpha = int(G.flash_timer / 0.35 * 200)
        screen.draw.filled_rect(Rect(0, 0, WIDTH, HEIGHT), (255, 0, 0))
        screen.draw.text("IMPACT!", (WIDTH//2 - 55, HEIGHT//2 - 20),
                         color=(255,255,255), fontsize=48)

    # Hardware mode label
    hw_steer = read_encoder_position() is not None
    hw_force = read_force_sensor()     is not None
    label = ("HW" if hw_steer and hw_force else
             "HW steer / KB throttle" if hw_steer else
             "KB steer / HW throttle" if hw_force else
             "KEYBOARD MODE")
    screen.draw.text(label, (WIDTH - 200, HEIGHT - 24), color=(180,180,180), fontsize=16)

    # Controls hint
    screen.draw.text("R = reset", (WIDTH - 90, 10), color=(160,160,160), fontsize=15)


# ── pgzrun entry points ───────────────────────────────────────────────────────
def draw():
    screen.clear()
    draw_road(screen)
    draw_obstacles(screen)
    draw_car(screen)
    draw_hud(screen)


pgzrun.go()
