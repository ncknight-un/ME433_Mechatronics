"""
Servo Motor Driving Game — pgzrun
==================================
Parses Raspberry Pi Pico serial output in the format:
    Output: <filtered_force_float> <encoder_degrees_int>

Example line: "Output: -3705096.00 242"

Encoder (AS5600):
  - Raw output is 0–360 degrees
  - Centered around a calibrated zero (auto-set on first read, or press C)
  - ENCODER_MAX_DEFLECT degrees of rotation → full steer lock

Force Sensor (HX711):
  - Raw 24-bit signed ADC values (large magnitude, e.g. -3_705_096)
  - First FORCE_CALIBRATION_N samples build a resting baseline
  - |value - baseline| is normalized to speed

Controls:
  C key  →  re-calibrate encoder center + force baseline
  R key  →  reset car and score
  Arrow keys → keyboard fallback when no hardware connected

Run with:
    pgzrun driving_game.py

Dependencies:
    pip install pgzero pygame pyserial
"""

import pgzrun
import math
import random
import threading
import serial
import serial.tools.list_ports

# ─────────────────────────────────────────────────────────────────────────────
# Serial / Hardware configuration  ← edit these to match your setup
# ─────────────────────────────────────────────────────────────────────────────
SERIAL_PORT   = None       # e.g. "COM3" or "/dev/ttyACM0"; None = auto-detect
SERIAL_BAUD   = 115200
SERIAL_PREFIX = "Output:"  # prefix the Pico prints on every data line

# Encoder calibration
ENCODER_MAX_DEFLECT = 90.0   # degrees from center → full steer lock
ENCODER_DEADZONE    = 5.0    # degrees of dead-band around center

# Force sensor calibration
FORCE_CALIBRATION_N = 20         # samples averaged for resting baseline
FORCE_MAX_DELTA     = 500_000       # |raw - baseline| that equals MAX_SPEED
                                  # tune this to how hard you press the sensor

# ─────────────────────────────────────────────────────────────────────────────
# Game constants
# ─────────────────────────────────────────────────────────────────────────────
WIDTH           = 900
HEIGHT          = 700
TITLE           = "Servo Driving Game"
MAX_SPEED       = 1500
MAX_STEER_ANGLE = 45
ROAD_LEFT       = 180
ROAD_RIGHT      = 720

C_SKY     = (135, 206, 235)
C_GRASS   = ( 34, 139,  34)
C_ROAD    = ( 50,  50,  50)
C_STRIPE  = (255, 255, 255)
C_CAR     = (220,  30,  30)
C_WHEEL   = ( 20,  20,  20)
C_CONE    = (255, 140,   0)
C_BARRIER = (200,  30,  30)
C_ROCK    = (130, 110,  90)
C_GRAVEL  = (180, 160, 130)
C_HUD     = (255, 255, 255)

# ─────────────────────────────────────────────────────────────────────────────
# Shared sensor state  (written by serial thread, read by game loop)
# ─────────────────────────────────────────────────────────────────────────────
class SensorState:
    def __init__(self):
        self.lock            = threading.Lock()
        self.raw_force       = 0.0
        self.raw_encoder_deg = 0.0
        self.connected       = False
        self.last_line       = "waiting for data…"
        self.encoder_center  = None   # auto-set on first sample
        self.force_baseline  = None   # auto-set after N samples
        self._cal_buf        = []
        self._calibrated     = False

    def ingest(self, force: float, encoder_deg: float):
        with self.lock:
            self.raw_force       = force
            self.raw_encoder_deg = encoder_deg
            # Build force baseline from first N samples
            if not self._calibrated:
                self._cal_buf.append(force)
                if len(self._cal_buf) >= FORCE_CALIBRATION_N:
                    self.force_baseline = sum(self._cal_buf) / len(self._cal_buf)
                    self._calibrated    = True
                    print(f"[CAL] Force baseline: {self.force_baseline:.2f}")
            # Auto-center encoder on first reading
            if self.encoder_center is None:
                self.encoder_center = encoder_deg
                print(f"[CAL] Encoder center: {self.encoder_center:.1f}°")

    def recalibrate(self):
        with self.lock:
            self.encoder_center = self.raw_encoder_deg
            self.force_baseline = self.raw_force
            self._cal_buf.clear()
            self._calibrated    = True
            print(f"[CAL] Recalibrated — enc center: {self.encoder_center:.1f}°  "
                  f"force baseline: {self.force_baseline:.2f}")

    def get_normalized(self):
        """Returns (steer: -1..+1, speed: 0..1) or (None, None) if not ready."""
        with self.lock:
            if (not self.connected or not self._calibrated
                    or self.encoder_center is None
                    or self.force_baseline is None):
                return None, None

            # ── Steer ────────────────────────────────────────────────────────
            diff = self.raw_encoder_deg - self.encoder_center
            if diff >  180: diff -= 360   # handle 0°/360° wrap
            if diff < -180: diff += 360
            if abs(diff) < ENCODER_DEADZONE:
                diff = 0.0
            steer = max(-1.0, min(1.0, diff / ENCODER_MAX_DEFLECT))

            # ── Speed ─────────────────────────────────────────────────────────
            delta = abs(self.raw_force - self.force_baseline)
            speed = min(1.0, delta / FORCE_MAX_DELTA)

            return steer, speed

SENSOR = SensorState()

# ─────────────────────────────────────────────────────────────────────────────
# Serial reader thread
# ─────────────────────────────────────────────────────────────────────────────
def find_pico_port():
    for p in serial.tools.list_ports.comports():
        hwid = (p.hwid or "").lower()
        desc = (p.description or "").lower()
        if "2e8a" in hwid or "pico" in desc or "ttyacm" in p.device.lower():
            return p.device
    ports = serial.tools.list_ports.comports()
    return ports[0].device if ports else None

def serial_reader():
    port = SERIAL_PORT or find_pico_port()
    if not port:
        print("[SERIAL] No port found — keyboard mode active.")
        return
    print(f"[SERIAL] Opening {port} @ {SERIAL_BAUD} …")
    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=1)
        SENSOR.connected = True
        print("[SERIAL] Connected.")
    except Exception as e:
        print(f"[SERIAL] Could not open port: {e}")
        return
    while True:
        try:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            SENSOR.last_line = line
            if not line.startswith(SERIAL_PREFIX):
                continue
            parts = line[len(SERIAL_PREFIX):].split()
            if len(parts) < 2:
                continue
            force   = float(parts[0])
            enc_deg = float(parts[1])
            SENSOR.ingest(force, enc_deg)
        except Exception as e:
            print(f"[SERIAL] Error: {e}")
            SENSOR.connected = False
            break

threading.Thread(target=serial_reader, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# Haptic / warning callback  ← put your motor vibration code here
# ─────────────────────────────────────────────────────────────────────────────
def on_obstacle_collision(car_speed: float, obstacle_type: str):
    intensity = car_speed / MAX_SPEED
    print(f"[HAPTIC] '{obstacle_type}' hit | speed={car_speed:.1f} | intensity={intensity:.2f}")
    # TODO: motor.vibrate(intensity=intensity, duration_ms=200)

# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────
class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.car_x       = WIDTH // 2
        self.car_y       = HEIGHT - 140
        self.steer_angle = 0.0
        self.speed       = 0.0
        self.distance    = 0
        self.road_offset = 0
        self.obstacles   = []
        self.spawn_timer = 0.0
        self.flash_timer = 0.0
        self.off_road    = False

G = GameState()

OBSTACLE_KINDS = [
    {"kind": "cone",    "w": 22, "h": 30},
    {"kind": "barrier", "w": 80, "h": 22},
    {"kind": "rock",    "w": 34, "h": 26},
]

def car_rect():
    cw, ch = 36, 60
    return G.car_x-cw//2, G.car_y-ch//2, G.car_x+cw//2, G.car_y+ch//2

def rects_overlap(ax1,ay1,ax2,ay2,bx1,by1,bx2,by2):
    return ax1<bx2 and ax2>bx1 and ay1<by2 and ay2>by1

# ─────────────────────────────────────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────────────────────────────────────
def get_steer_and_speed(dt):
    sf, spf = SENSOR.get_normalized()
    if sf is not None:
        return sf * MAX_STEER_ANGLE, spf * MAX_SPEED
    # Keyboard fallback
    steer = G.steer_angle
    if keyboard.left:
        steer = max(-MAX_STEER_ANGLE, steer - 120*dt)
    elif keyboard.right:
        steer = min( MAX_STEER_ANGLE, steer + 120*dt)
    else:
        steer *= (1 - 5*dt)
    target = MAX_SPEED * 0.6 if keyboard.up else 0
    speed  = G.speed + (target - G.speed) * min(1.0, 4*dt)
    return steer, speed

# ─────────────────────────────────────────────────────────────────────────────
# Update / Draw
# ─────────────────────────────────────────────────────────────────────────────
_c_prev = False

def update(dt):
    global _c_prev
    c_now = keyboard.c
    if c_now and not _c_prev:
        SENSOR.recalibrate()
    _c_prev = c_now

    if keyboard.r:
        G.reset()
        return

    G.steer_angle, G.speed = get_steer_and_speed(dt)
    lateral = math.sin(math.radians(G.steer_angle)) * G.speed * 2.6 * dt
    G.car_x   = max(60, min(WIDTH-60, G.car_x + lateral))
    G.road_offset = (G.road_offset + G.speed * dt * 3) % 80
    G.distance   += G.speed * dt

    interval = max(0.18, 1.0 - G.speed / MAX_SPEED * 0.7)
    G.spawn_timer += dt
    if G.spawn_timer >= interval:
        t = random.choice(OBSTACLE_KINDS)
        x = random.randint(ROAD_LEFT + t["w"]//2, ROAD_RIGHT - t["w"]//2)
        G.obstacles.append({"x": x, "y": -60, **t})
        G.spawn_timer = 0.0

    cl, ct, cr, cb = car_rect()
    alive = []
    for o in G.obstacles:
        o["y"] += G.speed * 2.5 * dt
        if o["y"] > HEIGHT + 80:
            continue
        ow, oh = o["w"], o["h"]
        if rects_overlap(cl,ct,cr,cb, o["x"]-ow//2, o["y"]-oh//2,
                                       o["x"]+ow//2, o["y"]+oh//2):
            G.flash_timer = 0.35
            on_obstacle_collision(G.speed, o["kind"])
            G.speed -= 150
            G.speed = max(0, G.speed)
        else:
            alive.append(o)
    G.obstacles = alive

    G.off_road = G.car_x < ROAD_LEFT+20 or G.car_x > ROAD_RIGHT-20
    if G.off_road:
        G.speed *= (1 - 0.8*dt)
    if G.flash_timer > 0:
        G.flash_timer -= dt


def draw():
    screen.clear()

    # ── Road ──
    screen.draw.filled_rect(Rect(0,0,WIDTH,HEIGHT//2), C_SKY)
    screen.draw.filled_rect(Rect(0,HEIGHT//2,WIDTH,HEIGHT//2), C_GRASS)
    screen.draw.filled_rect(Rect(ROAD_LEFT,0,ROAD_RIGHT-ROAD_LEFT,HEIGHT), C_ROAD)
    screen.draw.filled_rect(Rect(ROAD_LEFT-30,0,30,HEIGHT), C_GRAVEL)
    screen.draw.filled_rect(Rect(ROAD_RIGHT,0,30,HEIGHT), C_GRAVEL)
    cx = WIDTH//2
    for yb in range(-80, HEIGHT+80, 80):
        y = int(yb + G.road_offset) % (HEIGHT+160) - 80
        screen.draw.filled_rect(Rect(cx-4, y, 8, 40), C_STRIPE)
    screen.draw.line((ROAD_LEFT,0),(ROAD_LEFT,HEIGHT),(255,255,100))
    screen.draw.line((ROAD_RIGHT,0),(ROAD_RIGHT,HEIGHT),(255,255,100))

    # ── Obstacles ──
    for o in G.obstacles:
        x,y,w,h = int(o["x"]),int(o["y"]),o["w"],o["h"]
        if o["kind"] == "cone":
            # Cone body
            screen.draw.filled_rect(
                Rect(x - w//2, y - h//2, w, h),
                C_CONE
            )

            # White reflective stripe
            screen.draw.filled_rect(
                Rect(x - w//2, y + h//6, w, 5),
                (255, 255, 255)
            )

            # Small cone base
            screen.draw.filled_rect(
                Rect(x - w//2 - 4, y + h//2 - 4, w + 8, 8),
                (180, 180, 180)
            )
        elif o["kind"] == "barrier":
            screen.draw.filled_rect(Rect(x-w//2,y-h//2,w,h), C_BARRIER)
            for i in range(0,w,16):
                if (i//16)%2==0:
                    screen.draw.filled_rect(Rect(x-w//2+i,y-h//2,8,h),(255,255,255))
        else:
            screen.draw.filled_circle(
                (x, y),
                min(w, h) // 2,
                C_ROCK
            )
            screen.draw.circle(
                (x, y),
                min(w, h) // 2,
                (80, 60, 40)
            )

    # ── Car ──
    cx2, cy = int(G.car_x), int(G.car_y)
    cw, ch = 36, 60
    screen.draw.filled_rect(Rect(cx2-cw//2,cy-ch//2,cw,ch), C_CAR)
    screen.draw.filled_rect(Rect(cx2-12,cy-22,24,16),(160,220,255))
    screen.draw.filled_rect(Rect(cx2-10,cy+10,20,12),(160,220,255))
    for wx,wy in [(-cw//2-2,-18),(cw//2-8,-18),(-cw//2-2,10),(cw//2-8,10)]:
        screen.draw.filled_rect(Rect(cx2+wx,cy+wy,10,18),C_WHEEL)
    ar = math.radians(G.steer_angle*0.6)
    screen.draw.line((cx2,cy),(cx2+int(math.sin(ar)*28),cy-int(math.cos(ar)*28)),(255,220,0))

    # ── HUD ──
    speed_kmh = int(G.speed * 0.12)
    dist_m    = int(G.distance * 0.05)
    sf, spf   = SENSOR.get_normalized()
    hw        = sf is not None

    screen.draw.filled_rect(Rect(10,10,170,95),(0,0,0))
    screen.draw.text("SPEED", (20,15), color=C_HUD, fontsize=18)
    screen.draw.text(f"{speed_kmh} km/h",(20,35),color=(100,255,100),fontsize=28)
    screen.draw.text(f"DIST: {dist_m} m",(20,72),color=C_HUD,fontsize=18)

    # Steer bar
    screen.draw.filled_rect(Rect(10,115,170,46),(0,0,0))
    screen.draw.text("STEER",(20,118),color=(255,220,100),fontsize=16)
    bx,by,bw,bh = 20,136,150,12
    screen.draw.filled_rect(Rect(bx,by,bw,bh),(60,60,60))
    mid = bx+bw//2
    fill = int((G.steer_angle/MAX_STEER_ANGLE)*(bw//2))
    if fill>=0:
        screen.draw.filled_rect(Rect(mid,by,fill,bh),(255,180,0))
    else:
        screen.draw.filled_rect(Rect(mid+fill,by,-fill,bh),(255,180,0))
    screen.draw.line((mid,by),(mid,by+bh),(255,255,255))

    # Force bar (hardware only)
    if hw:
        screen.draw.filled_rect(Rect(10,170,170,42),(0,0,0))
        screen.draw.text("FORCE",(20,173),color=(180,220,255),fontsize=16)
        screen.draw.filled_rect(Rect(20,191,150,12),(60,60,60))
        screen.draw.filled_rect(Rect(20,191,int((spf or 0)*150),12),(0,200,255))

    # Raw debug panel (bottom)
    with SENSOR.lock:
        rf  = SENSOR.raw_force
        re  = SENSOR.raw_encoder_deg
        bl  = SENSOR.force_baseline
        ctr = SENSOR.encoder_center
        ll  = SENSOR.last_line

    screen.draw.filled_rect(Rect(10,HEIGHT-96,350,88),(0,0,0))
    screen.draw.text(f"RAW force:   {rf:>14.2f}",       (16,HEIGHT-93),color=(160,160,160),fontsize=14)
    screen.draw.text(f"Baseline:    {bl if bl is not None else '(calibrating...)':>14}",
                                                          (16,HEIGHT-77),color=(160,160,160),fontsize=14)
    screen.draw.text(f"RAW encoder: {re:>8.1f}°   center: {ctr if ctr is not None else '?':>5}",
                                                          (16,HEIGHT-61),color=(160,160,160),fontsize=14)
    screen.draw.text(f"{ll[:48]}",                        (16,HEIGHT-45),color=(110,110,110),fontsize=13)
    screen.draw.text(f"Serial: {'CONNECTED' if SENSOR.connected else 'NOT CONNECTED'}",
                     (16,HEIGHT-29),
                     color=(100,255,100) if SENSOR.connected else (255,80,80),
                     fontsize=14)

    # Mode label (right-aligned manually)
    mode = "HARDWARE" if hw else ("NO SERIAL - KEYBOARD" if not SENSOR.connected else "CALIBRATING...")
    screen.draw.text(mode,          (WIDTH-200, 10), color=(100,255,100) if hw else (255,200,80), fontsize=16)
    screen.draw.text("C=recal  R=reset", (WIDTH-160, 30), color=(150,150,150), fontsize=14)

    if G.off_road:
        screen.draw.text("!! OFF ROAD",(WIDTH//2-70,22),color=(255,220,0),fontsize=26)

    if G.flash_timer > 0:
        screen.draw.filled_rect(Rect(0,0,WIDTH,HEIGHT),(255,0,0))
        screen.draw.text("IMPACT!",(WIDTH//2-55,HEIGHT//2-20),color=(255,255,255),fontsize=48)


pgzrun.go()
