import pygame
import math
import random
import struct
import io
import json
import sys
import asyncio

IS_WASM = sys.platform in ("emscripten", "wasi") or "pygbag" in sys.modules
# --- 0. Resolution Selection Menu (with auto-timeout) ---
def show_resolution_menu():
    pygame.init()
    info = pygame.display.Info()
    default_w, default_h = 1024, 768
    options = [
        ("1", (1024, 768)),
        ("2", (1280, 720)),
        ("3", (1366, 768)),
        ("4", (1600, 900)),
        ("5", (1920, 1080)),
    ]
    native = None
    if info.current_w >= 1280 and info.current_h >= 720:
        native = (info.current_w, info.current_h)
        options.append(("6", native))

    menu_screen = pygame.display.set_mode((default_w, default_h))
    pygame.display.set_caption("Asteroids - Select Resolution")
    font_big = pygame.font.SysFont("impact", 48)
    font_small = pygame.font.SysFont("couriernew", 24)
    clock = pygame.time.Clock()

    selection = None
    timer = 0
    TIMEOUT = 8 * 60

    while selection is None:
        menu_screen.fill((5, 5, 15))
        title = font_big.render("SELECT SCREEN RESOLUTION", True, (0, 255, 255))
        menu_screen.blit(title, (default_w//2 - title.get_width()//2, 50))

        y = 160
        for key, (w, h) in options:
            label = f"[{key}] {w} x {h}"
            if key == "6":
                label += " (native)"
            txt = font_small.render(label, True, (200, 200, 255))
            menu_screen.blit(txt, (default_w//2 - txt.get_width()//2, y))
            y += 50

        quit_txt = font_small.render("[Q] Quit", True, (255, 100, 100))
        menu_screen.blit(quit_txt, (default_w//2 - quit_txt.get_width()//2, y + 40))

        if timer < TIMEOUT:
            remaining = (TIMEOUT - timer) // 60
            info_txt = font_small.render(f"Auto-select in {remaining}s", True, (100, 100, 200))
            menu_screen.blit(info_txt, (default_w//2 - info_txt.get_width()//2, y + 100))
        else:
            info_txt = font_small.render("Auto-selecting native...", True, (100, 200, 100))
            menu_screen.blit(info_txt, (default_w//2 - info_txt.get_width()//2, y + 100))

        pygame.display.flip()

        timer += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()
                for key, (w, h) in options:
                    if event.unicode.lower() == key.lower():
                        selection = (w, h)
                        break
                if selection is None:
                    timer = 0
        if timer >= TIMEOUT and native is not None:
            selection = native
            break
        clock.tick(60)

    pygame.quit()
    return selection

# ------------------------------------------------------------
# DISPLAY / RESOLUTION
# ------------------------------------------------------------

# Logical resolution used by the game itself.
#
# All game coordinates, physics, projection, sprites and UI
# continue to use SCREEN_WIDTH / SCREEN_HEIGHT.
#
# WASM/browser presentation is handled separately.
WASM_WIDTH = 980
WASM_HEIGHT = 720

start_level = 1
custom_res = None

for arg in sys.argv:
    if arg.startswith('--level='):
        try:
            start_level = int(arg.split('=')[1])
            if start_level < 1:
                start_level = 1
        except Exception:
            pass

    elif arg.startswith('--res='):
        try:
            w, h = arg.split('=')[1].split('x')
            custom_res = (int(w), int(h))
        except Exception:
            pass


if IS_WASM:
    # --------------------------------------------------------
    # BROWSER / WASM
    #
    # NEVER use browser/native resolution here.
    #
    # This is the logical game framebuffer. The browser/pygbag
    # is responsible for presenting it at the appropriate CSS
    # size and device pixel ratio.
    # --------------------------------------------------------
    SCREEN_WIDTH = WASM_WIDTH
    SCREEN_HEIGHT = WASM_HEIGHT

elif custom_res is not None:
    # --------------------------------------------------------
    # DESKTOP -- explicit command-line resolution
    # --------------------------------------------------------
    SCREEN_WIDTH, SCREEN_HEIGHT = custom_res

else:
    # --------------------------------------------------------
    # DESKTOP -- retain existing automatic/native resolution
    # selection.
    # --------------------------------------------------------
    chosen_res = show_resolution_menu()
    SCREEN_WIDTH, SCREEN_HEIGHT = chosen_res


pygame.init()
pygame.mixer.init(
    frequency=44100,
    size=-16,
    channels=1,
    buffer=512
)

# Create the game framebuffer.
#
# IMPORTANT:
# SCREEN_WIDTH / SCREEN_HEIGHT are logical coordinates.
# Do not multiply these by devicePixelRatio.
screen = pygame.display.set_mode(
    (SCREEN_WIDTH, SCREEN_HEIGHT)
)

pygame.display.set_caption("Asteroids - 3D Holographic UIX")

BLACK = (0, 0, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
NEON_GREEN = (57, 255, 20)
ORANGE = (255, 165, 0)
DARK_MAGENTA = (100, 0, 100)
DARK_CYAN = (0, 100, 100)
WHITE = (220, 220, 240)
DARK_GRAY = (30, 30, 50)
GOLD = (255, 215, 0)
YELLOW = (255, 255, 0)
RED = (255, 50, 50)
PURPLE = (200, 50, 255)
GREEN = (50, 255, 50)

FPS = 60
clock = pygame.time.Clock()
try:
    font = pygame.font.SysFont("impact", 36)
    small_font = pygame.font.SysFont("couriernew", 20, bold=True)
    title_font = pygame.font.SysFont("impact", 72)
except:
    font = pygame.font.Font(None, 36)
    small_font = pygame.font.Font(None, 24)
    title_font = pygame.font.Font(None, 72)

FOV = 450
CAM_Z = -400

def project_3d(x, y, z, offset_x=0, offset_y=0):
    cx, cy = SCREEN_WIDTH / 2 + offset_x, SCREEN_HEIGHT / 2 + offset_y
    dx, dy, dz = x - cx, y - cy, z - CAM_Z
    if dz <= 0: dz = 0.1
    scale = FOV / dz
    px = cx + dx * scale
    py = cy + dy * scale
    return px, py

def get_projected_scale(z):
    dz = z - CAM_Z
    if dz <= 0: dz = 0.1
    return FOV / dz

def point_in_polygon(px, py, polygon):
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

def polygons_intersect(poly1, poly2):
    def get_axes(polygon):
        axes = []
        for i in range(len(polygon)):
            p1 = pygame.math.Vector2(polygon[i])
            p2 = pygame.math.Vector2(polygon[(i + 1) % len(polygon)])
            edge = p2 - p1
            normal = pygame.math.Vector2(-edge.y, edge.x)
            if normal.length() > 0:
                normal.normalize_ip()
            axes.append(normal)
        return axes

    def project_polygon(axis, polygon):
        min_proj = float('inf')
        max_proj = -float('inf')
        for point in polygon:
            proj = pygame.math.Vector2(point).dot(axis)
            min_proj = min(min_proj, proj)
            max_proj = max(max_proj, proj)
        return min_proj, max_proj

    def overlap(proj1, proj2):
        return not (proj1[1] < proj2[0] or proj2[1] < proj1[0])

    axes = get_axes(poly1) + get_axes(poly2)
    for axis in axes:
        if not overlap(project_polygon(axis, poly1), project_polygon(axis, poly2)):
            return False
    return True

def circle_polygon_intersection(circle_center, radius, polygon):
    center = pygame.math.Vector2(circle_center)
    if point_in_polygon(center.x, center.y, polygon):
        return True
    for i in range(len(polygon)):
        p1 = pygame.math.Vector2(polygon[i])
        p2 = pygame.math.Vector2(polygon[(i + 1) % len(polygon)])
        edge = p2 - p1
        edge_length = edge.length()
        if edge_length == 0:
            continue
        t = max(0, min(1, (center - p1).dot(edge) / (edge_length ** 2)))
        closest = p1 + edge * t
        if center.distance_to(closest) < radius:
            return True
    return False

def line_intersects_polygon(line_start, line_end, polygon):
    def line_intersection(p1, p2, p3, p4):
        x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if denom == 0: return None
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y2) - (y2 - y1) * (x1 - x3)) / denom
        if 0 <= t <= 1 and 0 <= u <= 1:
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        return None

    for i in range(len(polygon)):
        if line_intersection(line_start, line_end, polygon[i], polygon[(i + 1) % len(polygon)]):
            return True
    return False

def resolve_asteroid_collision(a1, a2):
    dist_vec = a2.pos - a1.pos
    distance = dist_vec.length()
    if distance == 0:
        a2.pos.x += 1
        return
    n = dist_vec / distance
    overlap = (a1.radius + a2.radius) - distance
    if overlap <= 0: return
    total_mass = a1.radius**2 + a2.radius**2
    if total_mass == 0: return
    a1.pos -= n * (overlap * (a2.radius**2 / total_mass))
    a2.pos += n * (overlap * (a1.radius**2 / total_mass))
    v1, v2 = a1.vel.dot(n), a2.vel.dot(n)
    m1, m2 = a1.radius**2, a2.radius**2
    a1.vel += n * (((m1 - m2) * v1 + 2 * m2 * v2) / (m1 + m2) - v1)
    a2.vel += n * (((m2 - m1) * v2 + 2 * m1 * v1) / (m1 + m2) - v2)

class DummySound:
    def play(self, *args, **kwargs): pass
    def stop(self, *args, **kwargs): pass
    def set_volume(self, *args, **kwargs): pass

class SoundManager:
    muted = False
    @staticmethod
    def create_sound(freq, duration, volume=0.3, type='sine'):
        try:
            sample_rate = 44100
            n_samples = int(sample_rate * duration)
            frames = bytearray()
            for i in range(n_samples):
                t = i / sample_rate
                envelope = max(0, 1 - (t / duration))
                if type == 'sine': val = math.sin(2 * math.pi * freq * t)
                elif type == 'square': val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
                elif type == 'noise': val = random.uniform(-1, 1)
                elif type == 'pew': val = math.sin(2 * math.pi * (freq - (freq * 0.8 * (t / duration))) * t)
                elif type == 'sawtooth': val = 2 * (t * freq - math.floor(t * freq + 0.5))
                elif type == 'clang': val = 0.5 * math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(2 * math.pi * freq * 1.3 * t)
                else: val = 0
                frames += struct.pack('<h', int(val * envelope * volume * 32767))
            data_size = len(frames)
            header = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36 + data_size, b'WAVE', b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16, b'data', data_size)
            raw_wav = bytes(header + frames)
            try:
                return pygame.mixer.Sound(buffer=raw_wav)
            except Exception:
                return pygame.mixer.Sound(raw_wav)
        except Exception:
            return DummySound()
    def __init__(self):
        self.snd_shoot = self.create_sound(880, 0.15, 0.15, 'pew')
        self.snd_explode = self.create_sound(100, 0.4, 0.3, 'noise')
        self.snd_thrust = self.create_sound(60, 0.1, 0.1, 'square')
        self.snd_life = self.create_sound(1200, 0.2, 0.3, 'square')
        self.snd_hit = self.create_sound(200, 0.1, 0.2, 'sawtooth')
        self.snd_powerup = self.create_sound(1500, 0.3, 0.4, 'square')
        self.snd_saucer = self.create_sound(600, 0.1, 0.2, 'sawtooth')
        self.snd_collision = self.create_sound(300, 0.15, 0.2, 'clang')
        self.snd_boss_pulse = self.create_sound(40, 0.3, 0.4, 'sawtooth')

    def play(self, sound):
        if not SoundManager.muted and sound:
            try:
                sound.play()
            except Exception:
                pass

class Particle(pygame.sprite.Sprite):
    def __init__(self, pos, vel, color, life, size=2, z_vel=0, z=0, projected=True):
        super().__init__()
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(vel)
        self.z = z
        self.z_vel = z_vel
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.glow_size = size * 3
        self.projected = projected

    def update(self):
        self.pos += self.vel
        self.z += self.z_vel
        self.vel *= 0.96
        self.life -= 1
        if self.life <= 0: self.kill()

    def draw(self, surface, offset):
        alpha = max(0, self.life / self.max_life)
        if self.projected:
            px, py = project_3d(self.pos.x, self.pos.y, self.z, offset.x, offset.y)
            scale = min(5.0, FOV / max(0.1, (self.z - CAM_Z)))
            proj_size = max(1, int(self.size * scale))
            glow = min(20, max(2, int(self.glow_size * scale)))
        else:
            px, py = self.pos.x + offset.x, self.pos.y + offset.y
            proj_size, glow = self.size, self.glow_size
        color = tuple(int(c * alpha) for c in self.color)
        if glow > proj_size and glow <= 50:
            glow_surface = pygame.Surface((glow * 2, glow * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, (*color, int(50 * alpha)), (glow, glow), glow)
            surface.blit(glow_surface, (int(px - glow), int(py - glow)))
        pygame.draw.circle(surface, color, (int(px), int(py)), proj_size)

class Player(pygame.sprite.Sprite):
    CANNON_DISTANCE = 20
    MAX_SHIELD = 3
    def __init__(self):
        super().__init__()
        self.pos = pygame.math.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.vel = pygame.math.Vector2(0, 0)
        self.angle = 0
        self.rot_speed = 5
        self.thrust_power = 0.18
        self.friction = 0.98
        self.radius = 12
        self.is_thrusting = False
        self.alive = True
        self.respawn_timer = 0
        self.invincible_timer = 0
        self.shield_hits = 0
        self.rapid_fire_timer = 0
        self.score_multiplier_timer = 0
        self.score_multiplier = 1

    def update(self, particles, sounds, use_keys=True):
        if not self.alive:
            self.respawn_timer -= 1
            return
        if self.invincible_timer > 0: self.invincible_timer -= 1
        if self.rapid_fire_timer > 0: self.rapid_fire_timer -= 1
        if self.score_multiplier_timer > 0:
            self.score_multiplier_timer -= 1
            if self.score_multiplier_timer <= 0: self.score_multiplier = 1

        rad = math.radians(self.angle)
        direction = pygame.math.Vector2(math.sin(rad), -math.cos(rad))
        if self.is_thrusting:
            self.vel += direction * self.thrust_power
            if random.random() > 0.3:
                rear_world = pygame.math.Vector2(0, 15).rotate(self.angle) + self.pos
                p_vel = -direction * random.uniform(2, 5) + pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
                particles.add(Particle(rear_world, p_vel, ORANGE, random.randint(10, 20), 3, z_vel=random.uniform(2, 8), z=-5, projected=False))
            if random.random() > 0.8: sounds.play(sounds.snd_thrust)
        self.vel *= self.friction
        self.pos += self.vel
        if self.pos.x > SCREEN_WIDTH: self.pos.x = 0
        elif self.pos.x < 0: self.pos.x = SCREEN_WIDTH
        if self.pos.y > SCREEN_HEIGHT: self.pos.y = 0
        elif self.pos.y < 0: self.pos.y = SCREEN_HEIGHT

    def respawn(self):
        self.alive = True
        self.pos = pygame.math.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.vel = pygame.math.Vector2(0, 0)
        self.angle = 0
        self.invincible_timer = 120
        self.shield_hits = 0
        self.rapid_fire_timer = 0
        self.score_multiplier = 1

    def get_collision_polygon(self):
        rad = math.radians(self.angle)
        points = []
        for x, y in [(0, -20), (-12, 15), (0, 8), (12, 15)]:
            rx = x * math.cos(rad) - y * math.sin(rad)
            ry = x * math.sin(rad) + y * math.cos(rad)
            points.append((self.pos.x + rx, self.pos.y + ry))
        return points

    def draw(self, surface, offset, is_hidden=False):
        if not self.alive: return
        points = self.get_collision_polygon()
        shifted = [(x + offset.x, y + offset.y) for x, y in points]
        cx, cy = self.pos + offset
        
        if is_hidden:
            for r, alpha in [(20, 15), (12, 30)]:
                glow = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*CYAN, alpha), (r, r), r)
                surface.blit(glow, (int(cx - r), int(cy - r)))
            pygame.draw.polygon(surface, (0, 40, 40), shifted)
            pygame.draw.polygon(surface, (0, 150, 150), shifted, 1)
        else:
            if self.invincible_timer > 0:
                pulse = math.sin(pygame.time.get_ticks() * 0.005) * 0.3 + 0.7
                halo_radius = int(40 * pulse)
                for r, alpha in [(halo_radius, 60), (halo_radius-10, 40), (halo_radius-20, 20)]:
                    if r > 0:
                        glow = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                        pygame.draw.circle(glow, (255, 215, 0, int(alpha * pulse)), (r, r), r)
                        surface.blit(glow, (int(cx - r), int(cy - r)))
            for r, alpha in [(20, 30), (12, 60)]:
                glow = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*CYAN, alpha), (r, r), r)
                surface.blit(glow, (int(cx - r), int(cy - r)))
            pygame.draw.polygon(surface, DARK_CYAN, shifted)
            pygame.draw.polygon(surface, CYAN, shifted, 2)
            
        if self.shield_hits > 0:
            for i in range(min(self.shield_hits, self.MAX_SHIELD)):
                pygame.draw.circle(surface, GREEN, (int(cx - 18 + i * 14), int(cy + 32)), 5, 2)
        if self.is_thrusting:
            epos = pygame.math.Vector2(0, 15).rotate(self.angle) + self.pos + offset
            for i in range(3):
                pygame.draw.circle(surface, (255, 100, 0, 100 - i*30), (int(epos.x), int(epos.y)), 8 - i*2)

    def explode(self, particles, sounds):
        self.alive = False
        self.respawn_timer = 120
        sounds.play(sounds.snd_explode)
        for _ in range(40):
            angle = random.uniform(0, math.pi * 2)
            vel = pygame.math.Vector2(math.cos(angle) * random.uniform(1, 6), math.sin(angle) * random.uniform(1, 6))
            particles.add(Particle(self.pos, vel, CYAN, random.randint(30, 60), 3, z_vel=random.uniform(-10, 10), projected=True))

class Asteroid(pygame.sprite.Sprite):
    def __init__(self, size, position=None, speed_scale=1.0):
        super().__init__()
        self.size = size
        self.radius = {'large': 50, 'medium': 25, 'small': 12}[size]
        self.shape = []
        num_points = random.randint(7, 10)
        for i in range(num_points):
            angle = (360 / num_points) * i
            r = self.radius + random.randint(-int(self.radius*0.4), int(self.radius*0.4))
            rad = math.radians(angle)
            self.shape.append((r * math.cos(rad), r * math.sin(rad)))
        if position:
            self.pos = pygame.math.Vector2(position)
        else:
            self.pos = self._get_safe_spawn_position()
        angle = random.uniform(0, 360)
        base_speed = random.uniform(1, 2) if size == 'large' else random.uniform(2, 4)
        self.vel = pygame.math.Vector2(math.cos(math.radians(angle)) * base_speed * speed_scale, math.sin(math.radians(angle)) * base_speed * speed_scale)
        self.rot_angle = 0
        self.rot_speed = random.uniform(-2, 2) * speed_scale
        self.base_z = random.uniform(-20, 20)
        self.depth_thickness = {'large': 60, 'medium': 40, 'small': 20}[size]

    def _get_safe_spawn_position(self):
        while True:
            side = random.choice(['top', 'bottom', 'left', 'right'])
            if side == 'top': pos = pygame.math.Vector2(random.randint(0, SCREEN_WIDTH), -50)
            elif side == 'bottom': pos = pygame.math.Vector2(random.randint(0, SCREEN_WIDTH), SCREEN_HEIGHT + 50)
            elif side == 'left': pos = pygame.math.Vector2(-50, random.randint(0, SCREEN_HEIGHT))
            else: pos = pygame.math.Vector2(SCREEN_WIDTH + 50, random.randint(0, SCREEN_HEIGHT))
            if pos.distance_to(pygame.math.Vector2(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)) > 250:
                return pos

    def update(self):
        self.pos += self.vel
        self.rot_angle += self.rot_speed
        buffer = self.radius + 20
        if self.pos.x > SCREEN_WIDTH + buffer: self.pos.x = -buffer
        elif self.pos.x < -buffer: self.pos.x = SCREEN_WIDTH + buffer
        if self.pos.y > SCREEN_HEIGHT + buffer: self.pos.y = -buffer
        elif self.pos.y < -buffer: self.pos.y = SCREEN_HEIGHT + buffer

    def get_collision_polygon(self, offset=pygame.math.Vector2(0,0)):
        rad = math.radians(self.rot_angle)
        points = []
        for x, y in self.shape:
            rx = x * math.cos(rad) - y * math.sin(rad)
            ry = x * math.sin(rad) + y * math.cos(rad)
            points.append((self.pos.x + rx, self.pos.y + ry))
        return points

    def collides_with_circle(self, center, radius, offset=pygame.math.Vector2(0,0)):
        if self.pos.distance_to(center) > self.radius + radius + 20: return False
        return circle_polygon_intersection(center, radius, self.get_collision_polygon(offset))

    def collides_with_line(self, start, end, offset=pygame.math.Vector2(0,0)):
        mid = (start + end) / 2
        if self.pos.distance_to(mid) > self.radius + start.distance_to(end) / 2 + 20: return False
        return line_intersects_polygon(start, end, self.get_collision_polygon(offset))

    def collides_with_polygon(self, other_polygon, offset=pygame.math.Vector2(0,0)):
        centroid = sum((pygame.math.Vector2(p) for p in other_polygon), pygame.math.Vector2(0, 0)) / len(other_polygon)
        if self.pos.distance_to(centroid) > self.radius * 2 + 50: return False
        return polygons_intersect(self.get_collision_polygon(offset), other_polygon)

    def draw(self, surface, offset):
        rad = math.radians(self.rot_angle)
        points = [(self.pos.x + x * math.cos(rad) - y * math.sin(rad), self.pos.y + x * math.sin(rad) + y * math.cos(rad)) for x, y in self.shape]
        top_proj = [project_3d(p[0], p[1], self.base_z, offset.x, offset.y) for p in points]
        bot_proj = [project_3d(p[0], p[1], self.base_z + self.depth_thickness, offset.x, offset.y) for p in points]
        pygame.draw.polygon(surface, DARK_MAGENTA, bot_proj)
        for i in range(len(points)):
            j = (i + 1) % len(points)
            brightness = 0.6 + 0.4 * math.sin(i * 0.7)
            pygame.draw.polygon(surface, tuple(int(c * brightness) for c in MAGENTA), [top_proj[i], top_proj[j], bot_proj[j], bot_proj[i]])
        pygame.draw.polygon(surface, (200, 0, 200), top_proj)
        pygame.draw.polygon(surface, MAGENTA, top_proj, 1)
        pygame.draw.polygon(surface, DARK_MAGENTA, bot_proj, 1)
        for i in range(len(points)):
            pygame.draw.line(surface, MAGENTA, top_proj[i], bot_proj[i], 1)

class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, angle):
        super().__init__()
        rad = math.radians(angle)
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(math.sin(rad), -math.cos(rad)) * 15
        self.radius = 2
        self.life = 50
        self.trail = []

    def update(self):
        self.trail.append(pygame.math.Vector2(self.pos))
        if len(self.trail) > 8: self.trail.pop(0)
        self.pos += self.vel
        self.life -= 1
        if self.life <= 0: self.kill()
        if self.pos.x > SCREEN_WIDTH: self.pos.x = 0
        elif self.pos.x < 0: self.pos.x = SCREEN_WIDTH
        if self.pos.y > SCREEN_HEIGHT: self.pos.y = 0
        elif self.pos.y < 0: self.pos.y = SCREEN_HEIGHT

    def draw(self, surface, offset):
        for i, pos in enumerate(self.trail):
            alpha = (i / len(self.trail)) * 0.5
            pygame.draw.circle(surface, tuple(int(c * alpha) for c in NEON_GREEN), (int(pos.x + offset.x), int(pos.y + offset.y)), max(1, int(2 * alpha)))
        px, py = self.pos.x + offset.x, self.pos.y + offset.y
        for glow_r, alpha in [(12, 30), (8, 60), (4, 120)]:
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*NEON_GREEN, alpha), (glow_r, glow_r), glow_r)
            surface.blit(glow_surf, (int(px - glow_r), int(py - glow_r)))
        pygame.draw.circle(surface, WHITE, (int(px), int(py)), 3)

class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, pos, target_pos):
        super().__init__()
        self.pos = pygame.math.Vector2(pos)
        self.vel = (pygame.math.Vector2(target_pos) - self.pos).normalize() * 8
        self.radius = 3
        self.life = 100
        self.trail = []

    def update(self):
        self.trail.append(pygame.math.Vector2(self.pos))
        if len(self.trail) > 6: self.trail.pop(0)
        self.pos += self.vel
        self.life -= 1
        if self.life <= 0 or self.pos.x > SCREEN_WIDTH + 20 or self.pos.x < -20 or self.pos.y > SCREEN_HEIGHT + 20 or self.pos.y < -20:
            self.kill()

    def draw(self, surface, offset):
        for i, pos in enumerate(self.trail):
            alpha = (i / len(self.trail)) * 0.4
            pygame.draw.circle(surface, tuple(int(c * alpha) for c in ORANGE), (int(pos.x + offset.x), int(pos.y + offset.y)), max(1, int(3 * alpha)))
        px, py = self.pos.x + offset.x, self.pos.y + offset.y
        for glow_r, alpha in [(10, 30), (6, 60)]:
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*ORANGE, alpha), (glow_r, glow_r), glow_r)
            surface.blit(glow_surf, (int(px - glow_r), int(py - glow_r)))
        pygame.draw.circle(surface, YELLOW, (int(px), int(py)), 4)

class BossBullet(EnemyBullet):
    def __init__(self, pos, vel):
        super().__init__(pos, pos + vel)
        self.vel = pygame.math.Vector2(vel)
        self.radius = 8
        self.life = 150
        
    def draw(self, surface, offset):
        px, py = self.pos.x + offset.x, self.pos.y + offset.y
        glow_surf = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*RED, 100), (15, 15), 15)
        surface.blit(glow_surf, (int(px - 15), int(py - 15)))
        pygame.draw.circle(surface, RED, (int(px), int(py)), self.radius)
        pygame.draw.circle(surface, YELLOW, (int(px), int(py)), self.radius - 3)

class FlyingSaucer(pygame.sprite.Sprite):
    def __init__(self, player_pos, flank_id=0, total_saucers=1):
        super().__init__()
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top': self.pos = pygame.math.Vector2(random.randint(50, SCREEN_WIDTH-50), -30)
        elif side == 'bottom': self.pos = pygame.math.Vector2(random.randint(50, SCREEN_WIDTH-50), SCREEN_HEIGHT+30)
        elif side == 'left': self.pos = pygame.math.Vector2(-30, random.randint(50, SCREEN_HEIGHT-50))
        else: self.pos = pygame.math.Vector2(SCREEN_WIDTH+30, random.randint(50, SCREEN_HEIGHT-50))

        self.vel = pygame.math.Vector2(0, 0)
        self.angle = 0
        self.radius = 22
        self.max_speed = 3.5 + random.uniform(0, 1.0)
        
        self.disc_points = []
        for i in range(16):
            rad = math.radians((360 / 16) * i)
            r = self.radius * random.uniform(0.95, 1.05)
            self.disc_points.append((r * math.cos(rad), r * math.sin(rad)))

        self.shoot_timer = random.randint(30, 60)
        self.flank_id = flank_id
        self.total_saucers = total_saucers
        self.target = player_pos

    def update(self, player_pos, all_saucers, player_hidden=False, asteroids=None, clouds=None):
        saucer_hidden = False
        if clouds:
            for cloud in clouds:
                if self.pos.distance_to(cloud.pos) < (cloud.size // 2) + 20:
                    saucer_hidden = True
                    break

        avoid_vel = pygame.math.Vector2(0, 0)
        if asteroids:
            for asteroid in asteroids:
                ast_hidden = False
                if clouds:
                    for cloud in clouds:
                        if asteroid.pos.distance_to(cloud.pos) < (cloud.size // 2) + 20:
                            ast_hidden = True
                            break
                if saucer_hidden or ast_hidden:
                    continue
                dist_to_ast = self.pos.distance_to(asteroid.pos)
                avoid_radius = self.radius + asteroid.radius + 80
                if dist_to_ast < avoid_radius and dist_to_ast > 0:
                    away_dir = (self.pos - asteroid.pos).normalize()
                    strength = (avoid_radius - dist_to_ast) / avoid_radius
                    avoid_vel += away_dir * strength * self.max_speed * 1.5

        if player_hidden:
            if random.random() < 0.02:
                wander_angle = random.uniform(0, math.pi * 2)
                self.vel = pygame.math.Vector2(math.cos(wander_angle), math.sin(wander_angle)) * self.max_speed
            target_pos = self.pos + self.vel.normalize() * 200 if self.vel.length() > 0.1 else player_pos
            self.target = self.pos + pygame.math.Vector2(random.uniform(-1000, 1000), random.uniform(-1000, 1000))
        else:
            if len(all_saucers) > 1:
                angle_step = (2 * math.pi) / len(all_saucers)
                flank_angle = angle_step * self.flank_id
                offset_dist = 250
                target_offset = pygame.math.Vector2(math.cos(flank_angle) * offset_dist, math.sin(flank_angle) * offset_dist)
                target_pos = player_pos + target_offset
            else:
                target_pos = player_pos
            self.target = player_pos

        to_target = target_pos - self.pos
        dist = to_target.length()
        desired_vel = pygame.math.Vector2(0, 0)
        if dist > 0:
            desired_vel = to_target.normalize() * self.max_speed
        desired_vel += avoid_vel
        if desired_vel.length() > self.max_speed:
            desired_vel = desired_vel.normalize() * self.max_speed
        self.vel = self.vel * 0.92 + desired_vel * 0.08
        if self.vel.length() > self.max_speed:
            self.vel = self.vel.normalize() * self.max_speed
        self.pos += self.vel
        if self.vel.length() > 0.1:
            target_angle = math.degrees(math.atan2(self.vel.y, self.vel.x)) + 90
            diff = (target_angle - self.angle) % 360
            if diff > 180: diff -= 360
            self.angle += diff * 0.15

    def shoot(self, enemy_bullets):
        bullet = EnemyBullet(self.pos, self.target)
        enemy_bullets.add(bullet)
        return bullet

    def get_collision_polygon(self, offset=pygame.math.Vector2(0,0)):
        rad = math.radians(self.angle)
        points = []
        for x, y in self.disc_points:
            rx = x * math.cos(rad) - y * math.sin(rad)
            ry = x * math.sin(rad) + y * math.cos(rad)
            points.append((self.pos.x + rx, self.pos.y + ry))
        return points

    def draw(self, surface, offset):
        pos_shifted = self.pos + offset
        pygame.draw.ellipse(surface, (80, 60, 20), (pos_shifted.x - self.radius, pos_shifted.y - self.radius*0.5, self.radius*2, self.radius))
        pygame.draw.ellipse(surface, GOLD, (pos_shifted.x - self.radius, pos_shifted.y - self.radius*0.5, self.radius*2, self.radius), 2)
        dome_center = pos_shifted + pygame.math.Vector2(0, -self.radius*0.2)
        dome_radius = self.radius * 0.45
        pygame.draw.circle(surface, (180, 150, 50), (int(dome_center.x), int(dome_center.y)), int(dome_radius))
        pygame.draw.circle(surface, (255, 230, 150), (int(dome_center.x), int(dome_center.y)), int(dome_radius), 2)
        beacon_pos = dome_center + pygame.math.Vector2(0, -dome_radius*0.3)
        for r, alpha in [(6, 60), (3, 120)]:
            glow = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 255, 200, alpha), (r, r), r)
            surface.blit(glow, (int(beacon_pos.x - r), int(beacon_pos.y - r)))

class BossSaucer(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.radius = 220
        self.hp = 50
        self.max_hp = 50
        self.alive = True
        self.angle = 0
        self.max_speed = 3.0
        
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top': self.pos = pygame.math.Vector2(SCREEN_WIDTH/2, -self.radius)
        elif side == 'bottom': self.pos = pygame.math.Vector2(SCREEN_WIDTH/2, SCREEN_HEIGHT + self.radius)
        elif side == 'left': self.pos = pygame.math.Vector2(-self.radius, SCREEN_HEIGHT/2)
        else: self.pos = pygame.math.Vector2(SCREEN_WIDTH + self.radius, SCREEN_HEIGHT/2)
        
        self.vel = pygame.math.Vector2(0, 0)
        self.target_pos = pygame.math.Vector2(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
        self.entering = True
        self.invulnerable_timer = 180
        
        self.disc_points = []
        for i in range(32):
            rad = math.radians((360 / 32) * i)
            r = self.radius * random.uniform(0.95, 1.05)
            self.disc_points.append((r * math.cos(rad), r * math.sin(rad)))
            
        self.attack_timer = 0
        self.target = self.target_pos
        self.pulse_timer = 60
        self.singularity_timer = 0
        self.is_singularity_active = False

    def update(self, player_pos, player_hidden=False):
        self.target = player_pos
        if self.invulnerable_timer > 0:
            self.invulnerable_timer -= 1
        if self.entering:
            to_center = self.target_pos - self.pos
            if to_center.length() < 15:
                self.entering = False
                self.pos = self.target_pos
                self.vel = pygame.math.Vector2(0, 0)
            else:
                self.pos += to_center.normalize() * 10
                self.angle += 5
                return None
        to_target = self.target - self.pos
        dist = to_target.length()
        desired_dist = 350
        if dist > desired_dist + 50:
            desired_vel = to_target.normalize() * self.max_speed
        elif dist < desired_dist - 50:
            desired_vel = -to_target.normalize() * self.max_speed
        else:
            perp = pygame.math.Vector2(-to_target.y, to_target.x).normalize()
            wobble = math.sin(self.attack_timer * 0.03) * 2
            desired_vel = perp * (self.max_speed + wobble)
        self.vel = self.vel * 0.95 + desired_vel * 0.05
        self.pos += self.vel
        if self.vel.length() > 0.1:
            target_angle = math.degrees(math.atan2(self.vel.y, self.vel.x)) + 90
            diff = (target_angle - self.angle) % 360
            if diff > 180: diff -= 360
            self.angle += diff * 0.1
        self.attack_timer += 1
        if player_hidden and self.attack_timer % 70 == 0:
            return "ring"
        if self.hp < self.max_hp / 2:
            if self.attack_timer % 35 == 0: return "spread"
            if self.attack_timer % 120 == 0: return "ring"
            if self.attack_timer % 250 == 0: return "singularity"
        else:
            if self.attack_timer % 70 == 0: return "spread"
            if self.attack_timer % 180 == 0: return "ring"
            if self.attack_timer % 400 == 0: return "singularity"
        return None

    def take_damage(self, amount, particles, sounds):
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False
            sounds.play(sounds.snd_explode)
            for _ in range(100):
                angle = random.uniform(0, math.pi * 2)
                vel = pygame.math.Vector2(math.cos(angle) * random.uniform(2, 10), math.sin(angle) * random.uniform(2, 10))
                particles.add(Particle(self.pos, vel, RED, random.randint(40, 80), 5, z_vel=random.uniform(-10, 10), projected=True))
            self.kill()

    def get_collision_polygon(self, offset=pygame.math.Vector2(0,0)):
        rad = math.radians(self.angle)
        points = []
        for x, y in self.disc_points:
            rx = x * math.cos(rad) - y * math.sin(rad)
            ry = x * math.sin(rad) + y * math.cos(rad)
            points.append((self.pos.x + rx, self.pos.y + ry))
        return points

    def draw(self, surface, offset):
        pos_shifted = self.pos + offset
        if not self.entering:
            for i in range(3):
                ring_radius = self.radius * (1.5 + i * 0.8)
                ring_surf = pygame.Surface((int(ring_radius*2), int(ring_radius*0.4)), pygame.SRCALPHA)
                color = (100, 0, 150, 50 - i*15) if not self.is_singularity_active else (255, 50, 0, 100 - i*30)
                pygame.draw.ellipse(ring_surf, color, (0, 0, int(ring_radius*2), int(ring_radius*0.4)), 3)
                rotated = pygame.transform.rotate(ring_surf, self.attack_timer * (2 + i))
                rect = rotated.get_rect(center=(pos_shifted.x, pos_shifted.y))
                surface.blit(rotated, rect)
        eh_radius = self.radius * 0.7
        eh_surf = pygame.Surface((int(eh_radius*2), int(eh_radius*2)), pygame.SRCALPHA)
        pulse = math.sin(self.attack_timer * 0.1) * 0.3 + 0.7
        pygame.draw.circle(eh_surf, (20, 0, 40, int(150 * pulse)), (int(eh_radius), int(eh_radius)), int(eh_radius))
        pygame.draw.circle(eh_surf, (100, 0, 150, int(200 * pulse)), (int(eh_radius), int(eh_radius)), int(eh_radius), 3)
        surface.blit(eh_surf, (int(pos_shifted.x - eh_radius), int(pos_shifted.y - eh_radius)))
        pygame.draw.ellipse(surface, (150, 20, 20), (pos_shifted.x - self.radius, pos_shifted.y - self.radius*0.5, self.radius*2, self.radius))
        pygame.draw.ellipse(surface, RED, (pos_shifted.x - self.radius, pos_shifted.y - self.radius*0.5, self.radius*2, self.radius), 4)
        dome_center = pos_shifted + pygame.math.Vector2(0, -self.radius*0.2)
        dome_radius = self.radius * 0.45
        pygame.draw.circle(surface, (200, 50, 50), (int(dome_center.x), int(dome_center.y)), int(dome_radius))
        pygame.draw.circle(surface, (255, 100, 100), (int(dome_center.x), int(dome_center.y)), int(dome_radius), 4)
        pulse_core = math.sin(pygame.time.get_ticks() * 0.005) * 0.3 + 0.7
        core_radius = int(self.radius * 0.2 * pulse_core)
        glow = pygame.Surface((core_radius*4, core_radius*4), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 0, 0, int(150 * pulse_core)), (core_radius*2, core_radius*2), core_radius*2)
        surface.blit(glow, (int(dome_center.x - core_radius*2), int(dome_center.y - core_radius*2)))
        ring_radius = self.radius * 1.2
        ring_surf = pygame.Surface((int(ring_radius*2), int(ring_radius*0.6)), pygame.SRCALPHA)
        pygame.draw.ellipse(ring_surf, (*CYAN, 100), (0, 0, int(ring_radius*2), int(ring_radius*0.6)), 2)
        surface.blit(ring_surf, (int(pos_shifted.x - ring_radius), int(pos_shifted.y - ring_radius*0.3)))
        bar_width = 400
        bar_height = 20
        bar_x = pos_shifted.x - bar_width / 2
        bar_y = pos_shifted.y - self.radius - 50
        pygame.draw.rect(surface, DARK_GRAY, (bar_x, bar_y, bar_width, bar_height))
        hp_ratio = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surface, RED, (bar_x, bar_y, bar_width * hp_ratio, bar_height))
        pygame.draw.rect(surface, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)
        if self.invulnerable_timer > 0 or self.entering:
            shield_radius = self.radius * 1.2
            shield_surf = pygame.Surface((int(shield_radius*2), int(shield_radius*2)), pygame.SRCALPHA)
            pygame.draw.circle(shield_surf, (255, 255, 255, 100), (int(shield_radius), int(shield_radius)), int(shield_radius), 4)
            surface.blit(shield_surf, (int(pos_shifted.x - shield_radius), int(pos_shifted.y - shield_radius)))

class Powerup(pygame.sprite.Sprite):
    INVINCIBILITY, EXTRA_LIFE, RAPID_FIRE, SHIELD, SCORE_MULTIPLIER, EXPLOSIVE = 0, 1, 2, 3, 4, 5
    COLORS = {0: (0, 150, 255), 1: (255, 50, 50), 2: (255, 200, 0), 3: (50, 255, 50), 4: (200, 50, 255), 5: (255, 100, 0)}
    def __init__(self, pos, ptype=None):
        super().__init__()
        self.pos = pygame.math.Vector2(pos)
        self.radius = 15
        self.angle = 0
        self.rot_speed = 3
        self.base_z = 0
        self.depth_thickness = 20
        self.life_timer = 1200
        self.type = ptype if ptype is not None else random.choice(list(Powerup.COLORS.keys()))
        self.color = Powerup.COLORS[self.type]
        self.dim_color = tuple(c//2 for c in self.color)
        self.shape = []
        for i in range(10):
            rad = math.radians((360 / 10) * i)
            r = self.radius * (0.6 if i % 2 == 0 else 1.4)
            self.shape.append((r * math.cos(rad), r * math.sin(rad)))

    def update(self):
        self.angle += self.rot_speed
        self.life_timer -= 1
        if self.life_timer <= 0: self.kill()

    def get_collision_polygon(self, offset=pygame.math.Vector2(0,0)):
        rad = math.radians(self.angle)
        return [(self.pos.x + x * math.cos(rad) - y * math.sin(rad) + offset.x, self.pos.y + x * math.sin(rad) + y * math.cos(rad) + offset.y) for x, y in self.shape]

    def draw(self, surface, offset):
        points = self.get_collision_polygon(offset)
        px, py = self.pos + offset
        for r, alpha in [(30, 30), (20, 60)]:
            glow_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*self.color, alpha), (r, r), r)
            surface.blit(glow_surf, (int(px - r), int(py - r)))
        pygame.draw.polygon(surface, self.dim_color, points)
        pygame.draw.polygon(surface, self.color, points, 2)
        pygame.draw.circle(surface, WHITE, (int(px), int(py)), 3)

class GasCloud(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        base_size = min(SCREEN_WIDTH, SCREEN_HEIGHT) * random.uniform(0.5, 1.1)
        self.size = int(base_size)
        self.pos = pygame.math.Vector2(random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT))
        self.vel = pygame.math.Vector2(random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15))
        center = self.size // 2
        max_radius = self.size // 2

        self.dark_surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        core_max_r = int(max_radius * 0.75)
        for _ in range(60):
            r = random.randint(int(core_max_r * 0.3), core_max_r)
            max_dist = int(max_radius * 0.9) - r
            if max_dist > 0:
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, max_dist)
                pygame.draw.circle(self.dark_surface, (random.randint(5, 30), random.randint(5, 30), random.randint(15, 50), random.randint(180, 255)), (center + int(dist * math.cos(angle)), center + int(dist * math.sin(angle))), r)
        for _ in range(15):
            r = random.randint(int(max_radius * 0.1), int(max_radius * 0.3))
            max_dist = int(max_radius * 0.6) - r
            if max_dist > 0:
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, max_dist)
                pygame.draw.circle(self.dark_surface, (0, 0, 10, 255), (center + int(dist * math.cos(angle)), center + int(dist * math.sin(angle))), r)

        self.lit_surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        for _ in range(60):
            r = random.randint(int(core_max_r * 0.3), core_max_r)
            max_dist = int(max_radius * 0.9) - r
            if max_dist > 0:
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, max_dist)
                pygame.draw.circle(self.lit_surface, (random.randint(40, 80), random.randint(50, 90), random.randint(80, 120), random.randint(60, 120)), (center + int(dist * math.cos(angle)), center + int(dist * math.sin(angle))), r)
        for _ in range(10):
            r = random.randint(int(max_radius * 0.1), int(max_radius * 0.25))
            max_dist = int(max_radius * 0.5) - r
            if max_dist > 0:
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, max_dist)
                pygame.draw.circle(self.lit_surface, (150, 180, 255, 50), (center + int(dist * math.cos(angle)), center + int(dist * math.sin(angle))), r)
        for _ in range(50):
            r = random.randint(int(max_radius * 0.15), int(max_radius * 0.35))
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(int(max_radius * 0.65), int(max_radius * 0.92))
            x, y = center + int(dist * math.cos(angle)), center + int(dist * math.sin(angle))
            pygame.draw.circle(self.dark_surface, (10, 15, 30, random.randint(40, 100)), (x, y), r)
            pygame.draw.circle(self.lit_surface, (60, 80, 120, random.randint(20, 50)), (x, y), r)
        for _ in range(300):
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(0, max_radius * 0.85)
            pygame.draw.circle(self.dark_surface, (15, 15, 40, random.randint(100, 180)), (center + int(dist * math.cos(angle)), center + int(dist * math.sin(angle))), random.randint(2, 8))

        self.flash_timer = 0
        self.flash_state = 0
        self.lightning_segments = []

    def update(self):
        self.pos += self.vel
        margin = self.size
        if self.pos.x < -margin: self.pos.x = SCREEN_WIDTH + margin
        elif self.pos.x > SCREEN_WIDTH + margin: self.pos.x = -margin
        if self.pos.y < -margin: self.pos.y = SCREEN_HEIGHT + margin
        elif self.pos.y > SCREEN_HEIGHT + margin: self.pos.y = -margin
        if self.flash_state == 0:
            if random.random() < 0.005:
                self.flash_state = 1
                self.flash_timer = random.randint(5, 15)
                self.generate_lightning()
        elif self.flash_state == 1:
            self.flash_timer -= 1
            if self.flash_timer <= 0: self.flash_state = 2; self.flash_timer = random.randint(2, 6)
        elif self.flash_state == 2:
            self.flash_timer -= 1
            if self.flash_timer <= 0:
                self.flash_state = 3
                self.flash_timer = random.randint(10, 25)
                if random.random() < 0.4:
                    self.flash_state = 1
                    self.flash_timer = random.randint(3, 8)
                    self.generate_lightning()
        elif self.flash_state == 3:
            self.flash_timer -= 1
            if self.flash_timer <= 0: self.flash_state = 0; self.lightning_segments = []

    def generate_lightning(self):
        self.lightning_segments = []
        cx = self.size // 2 + random.randint(-self.size//4, self.size//4)
        cy = self.size // 2 + random.randint(-self.size//4, self.size//4)
        for _ in range(random.randint(1, 3)):
            curr_x, curr_y = float(cx), float(cy)
            angle = random.uniform(0, math.pi * 2)
            length = random.randint(int(self.size * 0.3), int(self.size * 0.7))
            segments = [(int(curr_x), int(curr_y))]
            for _ in range(random.randint(6, 15)):
                step = length // random.randint(6, 15)
                curr_x += math.cos(angle) * step + random.uniform(-20, 20)
                curr_y += math.sin(angle) * step + random.uniform(-20, 20)
                segments.append((int(curr_x), int(curr_y)))
                angle += random.uniform(-0.6, 0.6)
                if random.random() < 0.3:
                    branch_angle = angle + random.choice([-0.8, 0.8])
                    bx, by = curr_x, curr_y
                    branch_segments = [(int(bx), int(by))]
                    for _ in range(random.randint(2, 5)):
                        bx += math.cos(branch_angle) * (step * 0.7) + random.uniform(-10, 10)
                        by += math.sin(branch_angle) * (step * 0.7) + random.uniform(-10, 10)
                        branch_segments.append((int(bx), int(by)))
                        branch_angle += random.uniform(-0.5, 0.5)
                    self.lightning_segments.append(branch_segments)
            self.lightning_segments.append(segments)

    def draw(self, surface, offset):
        x = int(self.pos.x + offset.x - self.size // 2)
        y = int(self.pos.y + offset.y - self.size // 2)
        if self.flash_state == 0:
            surface.blit(self.dark_surface, (x, y))
        else:
            surface.blit(self.lit_surface, (x, y))
            if self.lightning_segments:
                for segments in self.lightning_segments:
                    if len(segments) > 1:
                        shifted = [(sx + x, sy + y) for sx, sy in segments]
                        pygame.draw.lines(surface, (100, 150, 255), False, shifted, 6)
                        pygame.draw.lines(surface, (200, 230, 255), False, shifted, 3)
                        pygame.draw.lines(surface, (255, 255, 255), False, shifted, 1)

class Game:
    def __init__(self):
        self.all_sprites = pygame.sprite.Group()
        self.asteroids = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()
        self.saucers = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.clouds = pygame.sprite.Group()
        self.sounds = SoundManager()

        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        for js in self.joysticks: js.init()
        self.controller_connected = bool(self.joysticks)
        self.controller = self.joysticks[0] if self.joysticks else None
        self.left_stick_x = self.left_stick_y = self.right_stick_x = self.right_stick_y = 0.0
        self.left_trigger = self.right_trigger = 0.0
        self.controller_buttons = {}

        self.player = Player()
        self.all_sprites.add(self.player)
        self.score = 0
        self.lives = 3
        self.next_extra_life = 1000
        self.level = start_level
        self.level_up_timer = 0
        self.game_over = False
        self.shake_amount = 0
        self.shake_offset = pygame.math.Vector2(0, 0)
        self.time_ticker = 0
        self.quit_flag = False
        self.high_scores = self.load_scores()
        self.entering_initials = False
        self.initials = ""
        self.demo_mode = False
        self.demo_timeout = 10 * 60
        self.last_input_time = pygame.time.get_ticks()
        self.stars = [{'x': random.randint(0, SCREEN_WIDTH), 'y': random.randint(0, SCREEN_HEIGHT), 'z': random.uniform(100, 500), 'brightness': random.randint(50, 200)} for _ in range(int(100 * (SCREEN_WIDTH * SCREEN_HEIGHT) / (1024 * 768)))]
        self.saucer_timer = random.randint(180, 300)
        self.powerup_timer = random.randint(900, 2400)
        self.boss_fight = False
        self.boss = None
        self.game_state = 'PLAYING'
        self.credits_timer = 0
        self.spawn_level()

    def rumble(self, low=0.5, high=0.5, duration=200):
        if self.controller_connected and self.controller:
            try: self.controller.rumble(low, high, duration)
            except: pass

    def spawn_level(self):
        for ast in list(self.asteroids): ast.kill()
        count = min(30, max(2, int((4 + (self.level - 1) * 2) * ((SCREEN_WIDTH * SCREEN_HEIGHT) / (1024 * 768)))))
        for _ in range(count):
            ast = Asteroid('large', speed_scale=1.0 + (self.level - 1) * 0.15)
            self.all_sprites.add(ast)
            self.asteroids.add(ast)
        if self.level >= 4:
            desired = min(2 + (self.level - 4), 5)
            if len(self.clouds) < desired:
                for _ in range(desired - len(self.clouds)):
                    self.clouds.add(GasCloud())

    def load_scores(self):
        scores = []
        if IS_WASM:
            try:
                import platform
                if hasattr(platform, "window") and hasattr(platform.window, "localStorage"):
                    raw = platform.window.localStorage.getItem("asteroids_3d_high_scores")
                    if raw:
                        scores = json.loads(str(raw))
            except Exception:
                pass
            if not scores:
                try:
                    import js
                    raw = js.localStorage.getItem("asteroids_3d_high_scores")
                    if raw:
                        scores = json.loads(str(raw))
                except Exception:
                    pass

        if not scores:
            try:
                with open('leaderboard_3d.json', 'r') as f:
                    scores = json.load(f)
            except Exception:
                scores = []
        return scores

    def save_score(self, name, score):
        self.high_scores.append({"name": name, "score": score})
        self.high_scores = sorted(self.high_scores, key=lambda x: x['score'], reverse=True)[:10]
        try:
            with open('leaderboard_3d.json', 'w') as f:
                json.dump(self.high_scores, f)
        except Exception:
            pass

        if IS_WASM:
            payload = json.dumps(self.high_scores)
            try:
                import platform
                if hasattr(platform, "window") and hasattr(platform.window, "localStorage"):
                    platform.window.localStorage.setItem("asteroids_3d_high_scores", payload)
            except Exception:
                pass
            try:
                import js
                js.localStorage.setItem("asteroids_3d_high_scores", payload)
            except Exception:
                pass

    def split_asteroid(self, asteroid):
        if asteroid not in self.asteroids: return
        base_score = {'large': 20, 'medium': 50, 'small': 100}[asteroid.size]
        self.score += base_score * self.player.score_multiplier
        while self.score >= self.next_extra_life:
            if self.lives < 5: self.lives += 1
            self.next_extra_life += 1000
            self.sounds.play(self.sounds.snd_life)
        self.sounds.play(self.sounds.snd_explode)
        self.rumble(0.7, 0.5, 300)
        self.shake_amount = 10 if asteroid.size == 'large' else 4
        for _ in range(20 if asteroid.size == 'large' else 10):
            vel = pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 5), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 5)) + asteroid.vel
            self.particles.add(Particle(asteroid.pos, vel, MAGENTA, random.randint(20, 40), 3, z_vel=random.uniform(-5, 10), projected=True))
        new_size = {'large': 'medium', 'medium': 'small'}.get(asteroid.size)
        if new_size:
            for _ in range(2):
                new_ast = Asteroid(new_size, asteroid.pos, speed_scale=1.0 + (self.level-1)*0.15)
                new_ast.vel += pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
                self.all_sprites.add(new_ast)
                self.asteroids.add(new_ast)
        asteroid.kill()
       

    def clear_asteroid(self, asteroid):
        if asteroid not in self.asteroids: return
        self.score += {'large': 20, 'medium': 50, 'small': 100}[asteroid.size] * self.player.score_multiplier
        while self.score >= self.next_extra_life:
            if self.lives < 5: self.lives += 1
            self.next_extra_life += 1000
            self.sounds.play(self.sounds.snd_life)
        self.sounds.play(self.sounds.snd_explode)
        self.rumble(0.5, 0.3, 200)
        self.shake_amount = 6
        for _ in range(15):
            vel = pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 4), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 4)) + asteroid.vel
            self.particles.add(Particle(asteroid.pos, vel, ORANGE, random.randint(20, 40), 3, z_vel=random.uniform(-5, 10), projected=True))
        asteroid.kill()
    
    def spawn_saucer(self, count=1):
        for i in range(count):
            saucer = FlyingSaucer(self.player.pos, flank_id=i, total_saucers=count)
            self.all_sprites.add(saucer)
            self.saucers.add(saucer)
        self.sounds.play(self.sounds.snd_saucer)

    def spawn_powerup(self):
        pos = None
        for _ in range(20):
            x, y = random.randint(100, SCREEN_WIDTH - 100), random.randint(100, SCREEN_HEIGHT - 100)
            if pygame.math.Vector2(x, y).distance_to(self.player.pos) > 200:
                pos = (x, y)
                break
        self.powerups.add(Powerup(pos if pos else (SCREEN_WIDTH/2, SCREEN_HEIGHT/2)))
        self.all_sprites.add(self.powerups.sprites()[-1])

    def draw_stars(self, surface, offset):
        for star in self.stars:
            px, py = project_3d((star['x'] + offset.x * (star['z'] / 200)) % SCREEN_WIDTH, (star['y'] + offset.y * (star['z'] / 200)) % SCREEN_HEIGHT, star['z'], offset.x, offset.y)
            scale = min(2.0, get_projected_scale(star['z']))
            brightness = int(star['brightness'] * min(1.0, scale * 0.5))
            pygame.draw.circle(surface, (brightness, brightness, int(brightness * 1.2)), (int(px), int(py)), max(1, int(2 * scale)))

    def draw_3d_grid(self, offset):
        grid_offset = (self.time_ticker * 2) % 100
        for y in range(-200, SCREEN_HEIGHT + 400, 100):
            pygame.draw.line(screen, (0, 40, 60), project_3d(-200, y + grid_offset, 150, offset.x, offset.y), project_3d(SCREEN_WIDTH + 200, y + grid_offset, 150, offset.x, offset.y), 1)
        for x in range(-200, SCREEN_WIDTH + 400, 100):
            pygame.draw.line(screen, (0, 40, 60), project_3d(x, -200, 150, offset.x, offset.y), project_3d(x, SCREEN_HEIGHT + 400, 150, offset.x, offset.y), 1)
        horizon_y = project_3d(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, 150, offset.x, offset.y)[1]
        glow_surf = pygame.Surface((SCREEN_WIDTH, 100), pygame.SRCALPHA)
        for i in range(100):
            pygame.draw.line(glow_surf, (0, 100, 150, int(20 * (1 - i / 100))), (0, i), (SCREEN_WIDTH, i))
        screen.blit(glow_surf, (0, int(horizon_y - 50)))

    def draw_holographic_text(self, text, fnt, color, x, y, depth_offset=2):
        screen.blit(fnt.render(text, True, (color[0]//3, color[1]//3, color[2]//3)), (x + depth_offset, y + depth_offset))
        screen.blit(fnt.render(text, True, color), (x, y))

    def auto_pilot(self):
        if not self.player.alive: return False
        self.player.is_thrusting = False
        if self.boss_fight and self.boss and self.boss.alive and not self.boss.entering:
            dist_to_boss = self.player.pos.distance_to(self.boss.pos)
            if dist_to_boss < self.boss.radius * 3.5:
                away_dir = (self.player.pos - self.boss.pos)
                if away_dir.length() > 0: away_dir.normalize_ip()
                else: away_dir = pygame.math.Vector2(1, 0)
                target_angle = math.degrees(math.atan2(away_dir.x, -away_dir.y)) % 360
                angle_diff = (target_angle - self.player.angle) % 360
                if angle_diff > 180: angle_diff -= 360
                if abs(angle_diff) > 5: self.player.angle += self.player.rot_speed if angle_diff > 0 else -self.player.rot_speed
                self.player.angle %= 360
                self.player.is_thrusting = True
                return False
        targets = list(self.asteroids) + list(self.saucers) + list(self.powerups)
        if self.boss_fight and self.boss and self.boss.alive:
            targets.append(self.boss)
        if not targets: return False
        target = min(targets, key=lambda e: self.player.pos.distance_to(e.pos))
        is_powerup = isinstance(target, Powerup)
        target_angle = math.degrees(math.atan2(target.pos.x - self.player.pos.x, -(target.pos.y - self.player.pos.y))) % 360
        angle_diff = (target_angle - self.player.angle) % 360
        if angle_diff > 180: angle_diff -= 360
        if abs(angle_diff) > 5: self.player.angle += self.player.rot_speed if angle_diff > 0 else -self.player.rot_speed
        self.player.angle %= 360
        if abs(angle_diff) < 60: self.player.is_thrusting = True
        return not is_powerup and abs(angle_diff) < 30 and self.player.pos.distance_to(target.pos) < 800 and len(self.bullets) < 5

    async def run(self):
        running = True
        shoot_cooldown = 0
        player_hidden = False
        while running:
            self.time_ticker += 1
            if self.level_up_timer > 0: self.level_up_timer -= 1

            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                elif event.type == pygame.JOYDEVICEADDED:
                    js = pygame.joystick.Joystick(event.device_index)
                    js.init()
                    self.joysticks.append(js)
                    self.controller_connected = True
                    self.controller = self.joysticks[0]
                elif event.type == pygame.JOYDEVICEREMOVED:
                    self.joysticks = [js for js in self.joysticks if js.get_instance_id() != event.instance_id]
                    self.controller_connected = bool(self.joysticks)
                    self.controller = self.joysticks[0] if self.joysticks else None
                elif event.type == pygame.JOYAXISMOTION:
                    if event.axis == 0: self.left_stick_x = event.value
                    elif event.axis == 1: self.left_stick_y = event.value
                    elif event.axis == 3: self.right_stick_x = event.value
                    elif event.axis == 4: self.right_stick_y = event.value
                    elif event.axis == 2: self.left_trigger = (event.value + 1) / 2
                    elif event.axis == 5: self.right_trigger = (event.value + 1) / 2
                elif event.type == pygame.JOYBUTTONDOWN:
                    self.controller_buttons[event.button] = True
                    if event.button == 7: SoundManager.muted = not SoundManager.muted
                    elif event.button == 6: self.quit_flag = True
                elif event.type == pygame.JOYBUTTONUP:
                    self.controller_buttons[event.button] = False
                elif event.type == pygame.KEYDOWN:
                    self.last_input_time = pygame.time.get_ticks()
                    self.demo_mode = False
                    if event.key == pygame.K_m and not self.entering_initials: SoundManager.muted = not SoundManager.muted
                    if event.key == pygame.K_q: self.quit_flag = True
                    if self.entering_initials:
                        if event.key == pygame.K_RETURN and len(self.initials) > 0:
                            self.save_score(self.initials, self.score)
                            self.entering_initials = False
                        elif event.key == pygame.K_BACKSPACE: self.initials = self.initials[:-1]
                        elif event.unicode.isalpha() and len(self.initials) < 3: self.initials += event.unicode.upper()
                    else:
                        if event.key == pygame.K_r and (self.game_over or self.game_state == 'CREDITS'):
                            self.__init__()
                            self.spawn_level()

            if self.quit_flag: break

            if self.game_state == 'PLAYING':
                if not self.game_over:
                    if pygame.time.get_ticks() - self.last_input_time > self.demo_timeout * (1000 // FPS):
                        self.demo_mode = True
                    else:
                        self.demo_mode = False

                    should_shoot = False
                    use_controller = self.controller_connected and self.joysticks

                    if self.demo_mode:
                        if self.auto_pilot() and shoot_cooldown <= 0: should_shoot = True
                        self.player.update(self.particles, self.sounds, use_keys=False)
                    else:
                        if use_controller:
                            if abs(self.left_stick_x) > 0.2: self.player.angle += self.player.rot_speed * self.left_stick_x * 0.5
                            self.player.is_thrusting = abs(self.left_stick_y) > 0.2 and self.left_stick_y < -0.2
                            if self.right_trigger > 0.5 and shoot_cooldown <= 0 and self.player.alive: should_shoot = True
                        else:
                            keys = pygame.key.get_pressed()
                            if keys[pygame.K_LEFT]: self.player.angle += self.player.rot_speed
                            if keys[pygame.K_RIGHT]: self.player.angle -= self.player.rot_speed
                            self.player.is_thrusting = keys[pygame.K_UP]
                            if keys[pygame.K_SPACE] and shoot_cooldown <= 0 and self.player.alive: should_shoot = True
                        self.player.update(self.particles, self.sounds, use_keys=False)

                    if should_shoot and len(self.bullets) < 5:
                        rad = math.radians(self.player.angle)
                        direction = pygame.math.Vector2(math.sin(rad), -math.cos(rad))
                        bullet = Bullet(self.player.pos + direction * Player.CANNON_DISTANCE, self.player.angle)
                        self.all_sprites.add(bullet)
                        self.bullets.add(bullet)
                        self.sounds.play(self.sounds.snd_shoot)
                        self.rumble(0.3, 0.1, 100)
                        shoot_cooldown = 6 if self.player.rapid_fire_timer > 0 else 12
                    if shoot_cooldown > 0: shoot_cooldown -= 1

                    self.asteroids.update()
                    self.bullets.update()
                    self.particles.update()
                    
                    player_hidden = False
                    if self.player.alive:
                        for cloud in self.clouds:
                            if self.player.pos.distance_to(cloud.pos) < (cloud.size // 2) + 20:
                                player_hidden = True
                                break

                    self.saucers.update(self.player.pos, list(self.saucers), player_hidden, list(self.asteroids), list(self.clouds))
                    self.enemy_bullets.update()
                    self.powerups.update()
                    self.clouds.update()
                    
                    if self.boss_fight and self.boss and self.boss.alive:
                        self.boss.pulse_timer -= 1
                        if self.boss.pulse_timer <= 0:
                            self.sounds.play(self.sounds.snd_boss_pulse)
                            hp_ratio = self.boss.hp / self.boss.max_hp
                            self.boss.pulse_timer = max(10, int(50 * hp_ratio))
                        if self.boss.is_singularity_active:
                            self.boss.singularity_timer -= 1
                            if self.boss.singularity_timer <= 0:
                                self.boss.is_singularity_active = False
                                for i in range(36):
                                    angle = (math.pi * 2 / 36) * i
                                    vel = pygame.math.Vector2(math.cos(angle) * 5, math.sin(angle) * 5)
                                    self.enemy_bullets.add(BossBullet(self.boss.pos, vel))
                                self.sounds.play(self.sounds.snd_explode)
                                self.shake_amount = max(self.shake_amount, 15)
                        action = self.boss.update(self.player.pos, player_hidden)
                        if action == "spread":
                            base_angle = math.atan2(self.player.pos.y - self.boss.pos.y, self.player.pos.x - self.boss.pos.x)
                            for i in range(-2, 3):
                                angle = base_angle + i * 0.2
                                vel = pygame.math.Vector2(math.cos(angle) * 6, math.sin(angle) * 6)
                                self.enemy_bullets.add(BossBullet(self.boss.pos, vel))
                            self.sounds.play(self.sounds.snd_shoot)
                        elif action == "ring":
                            for i in range(24):
                                angle = (math.pi * 2 / 24) * i
                                vel = pygame.math.Vector2(math.cos(angle) * 4, math.sin(angle) * 4)
                                self.enemy_bullets.add(BossBullet(self.boss.pos, vel))
                            self.sounds.play(self.sounds.snd_explode)
                        elif action == "singularity":
                            self.boss.is_singularity_active = True
                            self.boss.singularity_timer = 120
                            self.sounds.play(self.sounds.snd_boss_pulse)
                        if not self.boss.entering:
                            gravity_radius = self.boss.radius * 4.5
                            event_horizon = self.boss.radius * 0.7
                            grav_mult = 3.0 if self.boss.is_singularity_active else 1.0
                            if self.player.alive:
                                dist_vec = self.boss.pos - self.player.pos
                                dist = dist_vec.length()
                                if dist < gravity_radius:
                                    if dist < event_horizon:
                                        if self.player.invincible_timer <= 0 and self.player.shield_hits <= 0:
                                            self.player.explode(self.particles, self.sounds)
                                            self.lives -= 1
                                            self.shake_amount = 30
                                    else:
                                        pull = 400 / (dist ** 1.2) * grav_mult
                                        self.player.vel += dist_vec.normalize() * pull * 0.05
                            for ast in list(self.asteroids):
                                dist_vec = self.boss.pos - ast.pos
                                dist = dist_vec.length()
                                if dist < gravity_radius:
                                    if dist < event_horizon:
                                        self.clear_asteroid(ast)
                                    else:
                                        pull = 200 / (dist ** 1.2) * grav_mult
                                        ast.vel += dist_vec.normalize() * pull * 0.1
                            for bul in list(self.bullets):
                                dist_vec = self.boss.pos - bul.pos
                                dist = dist_vec.length()
                                if dist < gravity_radius:
                                    if dist < event_horizon:
                                        bul.kill()
                                    else:
                                        pull = 300 / (dist ** 1.2) * grav_mult
                                        bul.vel += dist_vec.normalize() * pull * 0.15
                                        if bul.vel.length() > 15: bul.vel = bul.vel.normalize() * 15
                            for ebul in list(self.enemy_bullets):
                                if isinstance(ebul, BossBullet): continue
                                dist_vec = self.boss.pos - ebul.pos
                                dist = dist_vec.length()
                                if dist < gravity_radius:
                                    if dist < event_horizon: ebul.kill()
                                    else:
                                        pull = 300 / (dist ** 1.2) * grav_mult
                                        ebul.vel += dist_vec.normalize() * pull * 0.15
                                        if ebul.vel.length() > 10: ebul.vel = ebul.vel.normalize() * 10
                            for sauc in list(self.saucers):
                                dist_vec = self.boss.pos - sauc.pos
                                dist = dist_vec.length()
                                if dist < gravity_radius:
                                    if dist < event_horizon: sauc.kill()
                                    else:
                                        pull = 200 / (dist ** 1.2) * grav_mult
                                        sauc.vel += dist_vec.normalize() * pull * 0.1

                    ast_list = list(self.asteroids)
                    for i in range(len(ast_list)):
                        for j in range(i + 1, len(ast_list)):
                            if ast_list[i] not in self.asteroids or ast_list[j] not in self.asteroids: continue
                            if ast_list[i].pos.distance_to(ast_list[j].pos) < ast_list[i].radius + ast_list[j].radius:
                                resolve_asteroid_collision(ast_list[i], ast_list[j])
                                self.sounds.play(self.sounds.snd_collision)

                    self.saucer_timer -= 1
                    if self.saucer_timer <= 0 and len(self.saucers) == 0 and not self.boss_fight:
                        if self.level < 5: saucer_count = 1
                        else: saucer_count = min(1 + (self.level - 4), 10)
                        self.spawn_saucer(saucer_count)
                        self.saucer_timer = int((300 + random.randint(0, 300)) * (0.6 if len(self.asteroids) < 3 else 1.0))

                    self.powerup_timer -= 1
                    if self.powerup_timer <= 0 and len(self.powerups) == 0 and not self.boss_fight:
                        self.spawn_powerup()
                        self.powerup_timer = random.randint(900, 2400)

                    for saucer in list(self.saucers):
                        if saucer not in self.saucers: continue
                        saucer.shoot_timer -= 1
                        if saucer.shoot_timer <= 0:
                            if random.random() < 0.6:
                                saucer.shoot(self.enemy_bullets)
                                self.sounds.play(self.sounds.snd_shoot)
                            saucer.shoot_timer = random.randint(20, 50)

                    if self.shake_amount > 0:
                        self.shake_offset = pygame.math.Vector2(random.uniform(-self.shake_amount, self.shake_amount), random.uniform(-self.shake_amount, self.shake_amount))
                        self.shake_amount *= 0.85
                        if self.shake_amount < 0.5: self.shake_amount = 0
                    else:
                        self.shake_offset = pygame.math.Vector2(0, 0)

                    if len(self.asteroids) == 0 and self.player.alive and not self.boss_fight:
                        if self.level == 10:
                            self.boss_fight = True
                            self.boss = BossSaucer()
                            self.all_sprites.add(self.boss)
                            self.saucer_timer = 99999
                            for s in list(self.saucers): s.kill()
                            for eb in list(self.enemy_bullets): eb.kill()
                        else:
                            self.level += 1
                            self.level_up_timer = 60
                            self.spawn_level()

                    # --- COLLISION: Bullets pass freely through GasClouds (no collision) ---
                    # Bullets vs Enemy Bullets (Interception)
                    for bullet in list(self.bullets):
                        if bullet not in self.bullets: continue
                        for ebullet in list(self.enemy_bullets):
                            if ebullet not in self.enemy_bullets: continue
                            if bullet.pos.distance_to(ebullet.pos) < bullet.radius + ebullet.radius + 4:
                                self.score += 10 * self.player.score_multiplier
                                self.sounds.play(self.sounds.snd_hit)
                                for _ in range(10):
                                    self.particles.add(Particle(ebullet.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 4), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 4)), WHITE, random.randint(10, 20), 2, projected=True))
                                bullet.kill()
                                ebullet.kill()
                                break

                    # Enemy bullets vs Saucers (Friendly Fire)
                    for ebullet in list(self.enemy_bullets):
                        if ebullet not in self.enemy_bullets: continue
                        if isinstance(ebullet, BossBullet): continue
                        for saucer in list(self.saucers):
                            if saucer not in self.saucers: continue
                            if ebullet.life < 90 and saucer.pos.distance_to(ebullet.pos) < saucer.radius + ebullet.radius + 5:
                                if circle_polygon_intersection(ebullet.pos, ebullet.radius, saucer.get_collision_polygon(self.shake_offset)):
                                    self.score += 200 * self.player.score_multiplier
                                    self.shake_amount = max(self.shake_amount, 8)
                                    self.sounds.play(self.sounds.snd_explode)
                                    for _ in range(30):
                                        self.particles.add(Particle(saucer.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 5), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 5)), GOLD, random.randint(20, 40), 3, z_vel=random.uniform(-5, 10), projected=True))
                                   
                                    saucer.kill()
                                    ebullet.kill()
                                    break

                    # Bullets vs Asteroids
                    for bullet in list(self.bullets):
                        if bullet not in self.bullets: continue
                        for asteroid in list(self.asteroids):
                            if asteroid not in self.asteroids: continue
                            if asteroid.collides_with_line(bullet.pos - bullet.vel * 1.5, bullet.pos, self.shake_offset) or asteroid.collides_with_circle(bullet.pos, bullet.radius, self.shake_offset):
                                self.split_asteroid(asteroid)
                                if bullet in self.bullets: bullet.kill()
                                break

                    # Bullets vs Boss
                    if self.boss_fight and self.boss and self.boss.alive:
                        for bullet in list(self.bullets):
                            if bullet not in self.bullets: continue
                            if self.boss.pos.distance_to(bullet.pos) < self.boss.radius + 10 and circle_polygon_intersection(bullet.pos, bullet.radius, self.boss.get_collision_polygon(self.shake_offset)):
                                if self.boss.invulnerable_timer > 0 or self.boss.entering:
                                    bullet.kill()
                                    for _ in range(3):
                                        self.particles.add(Particle(bullet.pos, pygame.math.Vector2(random.uniform(-2,2), random.uniform(-2,2)), WHITE, 10, 2, projected=True))
                                else:
                                    self.boss.take_damage(5.5, self.particles, self.sounds)
                                    self.shake_amount = max(self.shake_amount, 10)
                                    bullet.kill()
                                    for _ in range(5):
                                        self.particles.add(Particle(bullet.pos, pygame.math.Vector2(random.uniform(-2,2), random.uniform(-2,2)), YELLOW, 15, 2, projected=True))

                    # Enemy bullets vs Asteroids
                    for ebullet in list(self.enemy_bullets):
                        if ebullet not in self.enemy_bullets: continue
                        for asteroid in list(self.asteroids):
                            if asteroid not in self.asteroids: continue
                            if asteroid.collides_with_circle(ebullet.pos, ebullet.radius, self.shake_offset):
                                ebullet.kill()
                                self.rumble(0.2, 0.2, 100)
                                for _ in range(8):
                                    self.particles.add(Particle(ebullet.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 3), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 3)), ORANGE, random.randint(10, 20), 2, projected=True))
                                break

                    # Bullets vs Saucer
                    for bullet in list(self.bullets):
                        if bullet not in self.bullets: continue
                        for saucer in list(self.saucers):
                            if saucer not in self.saucers: continue
                            if saucer.pos.distance_to(bullet.pos) < saucer.radius + 10 and circle_polygon_intersection(bullet.pos, bullet.radius, saucer.get_collision_polygon(self.shake_offset)):
                                self.score += 200 * self.player.score_multiplier
                                self.shake_amount = max(self.shake_amount, 8)
                                self.sounds.play(self.sounds.snd_explode)
                                self.rumble(0.6, 0.4, 250)
                                for _ in range(30):
                                    self.particles.add(Particle(saucer.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 5), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 5)), GOLD, random.randint(20, 40), 3, z_vel=random.uniform(-5, 10), projected=True))
                               
                                saucer.kill()
                                if bullet in self.bullets: bullet.kill()
                                break

                    # Saucer vs Asteroid
                    for saucer in list(self.saucers):
                        if saucer not in self.saucers: continue
                        for asteroid in list(self.asteroids):
                            if asteroid not in self.asteroids: continue
                            if saucer.pos.distance_to(asteroid.pos) < saucer.radius + asteroid.radius:
                                self.sounds.play(self.sounds.snd_explode)
                                self.shake_amount = max(self.shake_amount, 10)
                                self.rumble(0.6, 0.4, 250)
                                for _ in range(30):
                                    self.particles.add(Particle(saucer.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 5), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 5)), GOLD, random.randint(20, 40), 3, z_vel=random.uniform(-5, 10), projected=True))
                                
                                saucer.kill()
                                self.split_asteroid(asteroid)
                                break

                    # Boss body vs Player
                    if self.boss_fight and self.boss and self.boss.alive and self.player.alive:
                        if self.boss.pos.distance_to(self.player.pos) < self.boss.radius + self.player.radius:
                            if self.player.invincible_timer <= 0 and self.player.shield_hits <= 0:
                                self.player.explode(self.particles, self.sounds)
                                self.lives -= 1

                    # Enemy bullets vs Player
                    if self.player.alive:
                        player_poly = self.player.get_collision_polygon()
                        for ebullet in list(self.enemy_bullets):
                            if ebullet not in self.enemy_bullets: continue
                            if circle_polygon_intersection(ebullet.pos, ebullet.radius, player_poly):
                                if self.player.shield_hits > 0:
                                    self.player.shield_hits -= 1
                                    self.sounds.play(self.sounds.snd_hit)
                                    self.rumble(0.4, 0.3, 150)
                                    ebullet.kill()
                                    for _ in range(10):
                                        self.particles.add(Particle(ebullet.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 3), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 3)), GREEN, random.randint(10, 20), 2, projected=True))
                                    continue
                                if self.player.invincible_timer <= 0:
                                    self.player.explode(self.particles, self.sounds)
                                    self.rumble(1.0, 0.8, 500)
                                    self.shake_amount = 25
                                    self.lives -= 1
                                    ebullet.kill()
                                    break

                    # Player vs Powerup
                    if self.player.alive:
                        for powerup in list(self.powerups):
                            if powerup not in self.powerups: continue
                            if self.player.pos.distance_to(powerup.pos) < self.player.radius + powerup.radius + 5:
                                ptype = powerup.type
                                if ptype == Powerup.INVINCIBILITY: self.player.invincible_timer = 900
                                elif ptype == Powerup.EXTRA_LIFE and self.lives < 5: self.lives += 1
                                elif ptype == Powerup.RAPID_FIRE: self.player.rapid_fire_timer = 900
                                elif ptype == Powerup.SHIELD: self.player.shield_hits = min(self.player.shield_hits + 1, Player.MAX_SHIELD)
                                elif ptype == Powerup.SCORE_MULTIPLIER: self.player.score_multiplier = 2; self.player.score_multiplier_timer = 1200
                                elif ptype == Powerup.EXPLOSIVE:
                                    for ast in list(self.asteroids): self.clear_asteroid(ast)
                                    self.shake_amount = 20
                                    for _ in range(60):
                                        self.particles.add(Particle(self.player.pos + pygame.math.Vector2(random.randint(-100, 100), random.randint(-100, 100)), pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(2, 8), math.sin(random.uniform(0, math.pi*2)) * random.uniform(2, 8)), ORANGE, random.randint(30, 60), 4, z_vel=random.uniform(-10, 10), projected=True))
                                powerup.kill()
                                self.sounds.play(self.sounds.snd_powerup)
                                self.rumble(0.5, 0.5, 150)
                                for _ in range(20):
                                    self.particles.add(Particle(powerup.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 4), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 4)), powerup.color, random.randint(20, 40), 2, z_vel=random.uniform(-5, 5), projected=True))

                    # Player vs Asteroids
                    if self.player.alive and self.player.invincible_timer <= 0:
                        player_poly = self.player.get_collision_polygon()
                        for asteroid in list(self.asteroids):
                            if asteroid not in self.asteroids: continue
                            if self.player.pos.distance_to(asteroid.pos) < asteroid.radius + self.player.radius + 10 and asteroid.collides_with_polygon(player_poly, self.shake_offset):
                                if self.player.shield_hits > 0:
                                    self.player.shield_hits -= 1
                                    self.sounds.play(self.sounds.snd_hit)
                                    self.rumble(0.4, 0.3, 150)
                                    for _ in range(15):
                                        self.particles.add(Particle(asteroid.pos, pygame.math.Vector2(math.cos(random.uniform(0, math.pi*2)) * random.uniform(1, 3), math.sin(random.uniform(0, math.pi*2)) * random.uniform(1, 3)), GREEN, random.randint(10, 20), 2, projected=True))
                                    asteroid.pos += (asteroid.pos - self.player.pos).normalize() * 30
                                    continue
                                self.player.explode(self.particles, self.sounds)
                                self.rumble(1.0, 0.8, 500)
                                self.shake_amount = 25
                                self.lives -= 1
                                break

                    if not self.player.alive and self.player.respawn_timer <= 0:
                        if self.lives > 0: self.player.respawn()
                        else:
                            self.game_over = True
                            if self.score > 0 and (len(self.high_scores) < 10 or self.score > self.high_scores[-1]['score']):
                                self.entering_initials = True
                                
                    if self.boss_fight and self.boss and not self.boss.alive:
                        self.game_state = 'CREDITS'
                        self.credits_timer = 600
                        self.boss_fight = False
                        self.boss = None
                        
            elif self.game_state == 'CREDITS':
                self.particles.update()
                self.credits_timer -= 1
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r] or self.credits_timer <= 0:
                    self.__init__()
                    self.spawn_level()
                    self.game_state = 'PLAYING'

            # --- DRAWING ---
            screen.fill(BLACK)
            self.draw_stars(screen, self.shake_offset)
            self.draw_3d_grid(self.shake_offset)

            if self.game_state == 'PLAYING':
                render_list = []
                for p in self.particles: render_list.append(('particle', p.z, p))
                for b in self.bullets: render_list.append(('bullet', 0, b))
                for b in self.enemy_bullets: render_list.append(('enemy_bullet', 0, b))
                for a in self.asteroids: render_list.append(('asteroid', a.base_z + a.depth_thickness / 2, a))
                for s in self.saucers: render_list.append(('saucer', 0, s))
                for p in self.powerups: render_list.append(('powerup', p.base_z + p.depth_thickness / 2, p))
                if self.boss_fight and self.boss and self.boss.alive: render_list.append(('boss', 0, self.boss))
                if self.player.alive: render_list.append(('player', 5, self.player, player_hidden))

                render_list.sort(key=lambda x: x[1], reverse=True)
                for item in render_list:
                    if item[0] == 'player':
                        item[2].draw(screen, self.shake_offset, item[3])
                    else:
                        item[2].draw(screen, self.shake_offset)

                for cloud in self.clouds: cloud.draw(screen, self.shake_offset)

                for y in range(0, SCREEN_HEIGHT, 4): pygame.draw.line(screen, (0, 0, 0), (0, y), (SCREEN_WIDTH, y), 1)
                vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                for i in range(100):
                    pygame.draw.rect(vignette, (0, 0, 5, int(30 * (i / 100))), (i, i, SCREEN_WIDTH - 2*i, SCREEN_HEIGHT - 2*i), 1)
                screen.blit(vignette, (0, 0))

                self.draw_holographic_text(f"SCORE :: {self.score}", font, CYAN, 20, 20)
                self.draw_holographic_text(f"LEVEL :: {self.level}", small_font, NEON_GREEN, 20, 60)
                for i in range(self.lives):
                    pygame.draw.polygon(screen, CYAN, [(30 + i * 30, 90), (22 + i * 30, 110), (30 + i * 30, 105), (38 + i * 30, 110)], 2)

                y_offset = 140
                if player_hidden:
                    self.draw_holographic_text("STEALTH ACTIVE", small_font, DARK_CYAN, 20, y_offset); y_offset += 25
                if self.player.invincible_timer > 0: self.draw_holographic_text("INVINCIBLE", small_font, CYAN, 20, y_offset); y_offset += 25
                if self.player.shield_hits > 0: self.draw_holographic_text(f"SHIELD x{self.player.shield_hits}", small_font, GREEN, 20, y_offset); y_offset += 25
                if self.player.rapid_fire_timer > 0: self.draw_holographic_text("RAPID FIRE", small_font, YELLOW, 20, y_offset); y_offset += 25
                if self.player.score_multiplier_timer > 0: self.draw_holographic_text("2X SCORE", small_font, PURPLE, 20, y_offset)

                if self.demo_mode: self.draw_holographic_text("AI MODE", title_font, GOLD, SCREEN_WIDTH//2 - 100, 20)
                if self.level_up_timer > 0 and not self.boss_fight:
                    msg = f"LEVEL {self.level} COMPLETE!"
                    self.draw_holographic_text(msg, font, GOLD, SCREEN_WIDTH//2 - font.size(msg)[0]//2, SCREEN_HEIGHT//2 - 50)
                if self.boss_fight:
                    msg = "WARNING: LEVIATHAN APPROACHING"
                    if self.time_ticker % 60 < 30:
                        self.draw_holographic_text(msg, font, RED, SCREEN_WIDTH//2 - font.size(msg)[0]//2, 100)

                mute_status = "SYS_AUDIO :: MUTED" if SoundManager.muted else "SYS_AUDIO :: ONLINE"
                self.draw_holographic_text(mute_status, small_font, NEON_GREEN, SCREEN_WIDTH - 250, 20)
                self.draw_holographic_text("[M] MUTE [Q] QUIT", small_font, DARK_CYAN, SCREEN_WIDTH - 250, 45)
                ctrl_text = f"CTRL :: {self.joysticks[0].get_name()[:20]}" if self.controller_connected else "CTRL :: NONE"
                self.draw_holographic_text(ctrl_text, small_font, NEON_GREEN if self.controller_connected else DARK_CYAN, SCREEN_WIDTH - 250, 70)

                if self.game_over:
                    s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                    s.fill((0, 0, 10, 150))
                    screen.blit(s, (0,0))
                    go_text = "SYSTEM FAILURE"
                    self.draw_holographic_text(go_text, title_font, MAGENTA, SCREEN_WIDTH//2 - title_font.size(go_text)[0]//2, SCREEN_HEIGHT//4)
                    if self.entering_initials:
                        self.draw_holographic_text("NEW HIGH SCORE", font, NEON_GREEN, SCREEN_WIDTH//2 - 120, SCREEN_HEIGHT//2 - 40)
                        self.draw_holographic_text(f"ENTER ID: {self.initials}_", font, CYAN, SCREEN_WIDTH//2 - 120, SCREEN_HEIGHT//2)
                    else:
                        self.draw_holographic_text("--- TOP SCORES ---", font, CYAN, SCREEN_WIDTH//2 - 130, SCREEN_HEIGHT//2 - 40)
                        for i, entry in enumerate(self.high_scores[:10]):
                            self.draw_holographic_text(f"{i+1:02d}. {entry['name']} ..... {entry['score']:06d}", small_font, NEON_GREEN, SCREEN_WIDTH//2 - 120, SCREEN_HEIGHT//2 + i*25)
                        self.draw_holographic_text(">> PRESS 'R' TO REBOOT <<", font, ORANGE, SCREEN_WIDTH//2 - 160, SCREEN_HEIGHT - 100)
                        
            elif self.game_state == 'CREDITS':
                for p in self.particles: p.draw(screen, self.shake_offset)
                s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                s.fill((0, 0, 10, 200))
                screen.blit(s, (0,0))
                self.draw_holographic_text("SYSTEM PURGED", title_font, NEON_GREEN, SCREEN_WIDTH//2 - 200, 150)
                self.draw_holographic_text("THE GALAXY IS SAFE... FOR NOW", font, CYAN, SCREEN_WIDTH//2 - 220, 250)
                credits_text = ["ASTEROIDS 3D HOLOGRAPHIC UIX", "", "CONCEIVED & CREATED BY", "HUMAN & AI COLLABORATION", "", "TACTICAL STEALTH MECHANICS", "GAS CLOUD DETONATION ENGINE", "COOPERATIVE SAUCER AI", "", "THANKS FOR PLAYING"]
                y = 350
                for line in credits_text:
                    self.draw_holographic_text(line, small_font, WHITE, SCREEN_WIDTH//2 - len(line)*6, y)
                    y += 30
                if self.credits_timer % 60 < 30:
                    self.draw_holographic_text("PRESS 'R' TO REBOOT SYSTEM", font, GOLD, SCREEN_WIDTH//2 - 180, SCREEN_HEIGHT - 100)

            pygame.display.flip()
            clock.tick(FPS)
            await asyncio.sleep(0)  # Allow other tasks to run
async def main():
    global game
    game = Game()
    await game.run()

game = None
asyncio.run(main())