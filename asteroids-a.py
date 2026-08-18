import pygame
import math
import random
import wave
import struct
import io
import os
import json

# --- 1. Initialization ---
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Asteroids - Enhanced UIX")

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 100, 100)
ORANGE = (255, 165, 0)
GRAY = (150, 150, 150)
GREEN = (120, 255, 120)
YELLOW = (255, 220, 120)

FPS = 60
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)
small_font = pygame.font.Font(None, 24)
board_font = pygame.font.SysFont("consolas", 24)

STARTING_LIVES = 3
EXTRA_LIFE_EVERY = 10000
MAX_LEADERBOARD = 10
SCORES_FILE = os.path.join(os.path.dirname(__file__), "asteroids_scores.json")


# --- 2. Procedural Sound Engine ---
class SoundManager:
    @staticmethod
    def create_sound(freq, duration, volume=0.3, sound_type='sine'):
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        buf = io.BytesIO()

        with wave.open(buf, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)

            for i in range(n_samples):
                t = i / sample_rate
                envelope = max(0, 1 - (t / duration))

                if sound_type == 'sine':
                    val = math.sin(2 * math.pi * freq * t)
                elif sound_type == 'square':
                    val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
                elif sound_type == 'noise':
                    val = random.uniform(-1, 1)
                elif sound_type == 'pew':
                    current_freq = freq - (freq * 0.8 * (t / duration))
                    val = math.sin(2 * math.pi * current_freq * t)
                elif sound_type == 'rise':
                    current_freq = freq * (1 + 0.8 * (t / duration))
                    val = math.sin(2 * math.pi * current_freq * t)
                else:
                    val = 0

                sample = int(val * envelope * volume * 32767)
                wf.writeframes(struct.pack('h', sample))

        buf.seek(0)
        return pygame.mixer.Sound(buf)

    def __init__(self):
        self.muted = False
        self.snd_shoot = self.create_sound(880, 0.15, 0.2, 'pew')
        self.snd_explode = self.create_sound(100, 0.4, 0.35, 'noise')
        self.snd_thrust = self.create_sound(60, 0.08, 0.08, 'square')
        self.snd_bonus = self.create_sound(900, 0.22, 0.2, 'rise')

    def play(self, sound):
        if not self.muted:
            sound.play()

    def toggle_mute(self):
        self.muted = not self.muted


# --- 3. Game Classes ---
class Particle(pygame.sprite.Sprite):
    def __init__(self, pos, vel, color, life, size=2):
        super().__init__()
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(vel)
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size

    def update(self):
        self.pos += self.vel
        self.vel *= 0.96
        self.life -= 1
        if self.life <= 0:
            self.kill()

    def draw(self, surface, offset):
        alpha_ratio = max(0, self.life / self.max_life)
        color = tuple(int(c * alpha_ratio) for c in self.color)
        pygame.draw.circle(
            surface,
            color,
            (int(self.pos.x + offset.x), int(self.pos.y + offset.y)),
            self.size
        )


class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()

        self.ship_points_local = [
            pygame.math.Vector2(0, -15),   # apex / cannon
            pygame.math.Vector2(-10, 10),  # rear left
            pygame.math.Vector2(10, 10)    # rear right
        ]

        self.cannon_local = self.ship_points_local[0]
        self.exhaust_local = (self.ship_points_local[1] + self.ship_points_local[2]) / 2

        self.pos = pygame.math.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.vel = pygame.math.Vector2(0, 0)
        self.angle = 0
        self.rot_speed = 5
        self.thrust_power = 0.15
        self.friction = 0.99
        self.radius = 12

        self.is_thrusting = False
        self.alive = True
        self.respawn_timer = 0
        self.invulnerable_timer = 0

    def rotate_local_point(self, point):
        rad = math.radians(self.angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        return pygame.math.Vector2(
            point.x * cos_a - point.y * sin_a,
            point.x * sin_a + point.y * cos_a
        )

    def local_to_world(self, point):
        return self.pos + self.rotate_local_point(point)

    def get_cannon_world_pos(self):
        return self.local_to_world(self.cannon_local)

    def get_exhaust_world_pos(self):
        return self.local_to_world(self.exhaust_local)

    def get_forward_direction(self):
        return (self.get_cannon_world_pos() - self.pos).normalize()

    def update(self, particles, sounds):
        if not self.alive:
            self.respawn_timer -= 1
            return

        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT]:
            self.angle += self.rot_speed
        if keys[pygame.K_RIGHT]:
            self.angle -= self.rot_speed
        self.angle %= 360

        forward = self.get_forward_direction()
        self.is_thrusting = keys[pygame.K_UP]

        if self.is_thrusting:
            self.vel += forward * self.thrust_power

            if random.random() > 0.25:
                exhaust_pos = self.get_exhaust_world_pos()
                perp = pygame.math.Vector2(-forward.y, forward.x)
                spread = perp * random.uniform(-0.8, 0.8)
                p_vel = -forward * random.uniform(2, 5) + spread + self.vel * 0.2
                particles.add(
                    Particle(exhaust_pos, p_vel, ORANGE, random.randint(10, 20), 2)
                )

            if random.random() > 0.85:
                sounds.play(sounds.snd_thrust)

        self.vel *= self.friction
        self.pos += self.vel

        if self.pos.x > SCREEN_WIDTH:
            self.pos.x = 0
        elif self.pos.x < 0:
            self.pos.x = SCREEN_WIDTH

        if self.pos.y > SCREEN_HEIGHT:
            self.pos.y = 0
        elif self.pos.y < 0:
            self.pos.y = SCREEN_HEIGHT

        if self.invulnerable_timer > 0:
            self.invulnerable_timer -= 1

    def draw(self, surface, offset):
        if not self.alive:
            return

        if self.invulnerable_timer > 0 and (self.invulnerable_timer // 4) % 2 == 0:
            return

        points = []
        for p in self.ship_points_local:
            wp = self.local_to_world(p)
            points.append((wp.x + offset.x, wp.y + offset.y))

        pygame.draw.polygon(surface, WHITE, points, 2)

    def explode(self, particles, sounds):
        self.alive = False
        self.respawn_timer = 90
        sounds.play(sounds.snd_explode)

        for _ in range(30):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1, 5)
            vel = pygame.math.Vector2(math.cos(angle) * speed, math.sin(angle) * speed)
            particles.add(Particle(self.pos, vel, WHITE, random.randint(30, 60), 2))

    def respawn(self):
        self.pos = pygame.math.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.vel = pygame.math.Vector2(0, 0)
        self.angle = 0
        self.alive = True
        self.invulnerable_timer = 120


class Asteroid(pygame.sprite.Sprite):
    def __init__(self, size, position=None):
        super().__init__()
        self.size = size
        self.radius = {'large': 40, 'medium': 20, 'small': 10}[size]

        self.shape = []
        num_points = random.randint(7, 10)
        for i in range(num_points):
            angle = (360 / num_points) * i
            r = self.radius + random.randint(-int(self.radius * 0.3), int(self.radius * 0.3))
            rad = math.radians(angle)
            self.shape.append((r * math.cos(rad), r * math.sin(rad)))

        if position:
            self.pos = pygame.math.Vector2(position)
        else:
            self.pos = self._get_safe_spawn_position()

        angle = random.uniform(0, 360)
        speed = random.uniform(1, 2) if size == 'large' else random.uniform(2, 4)
        self.vel = pygame.math.Vector2(
            math.cos(math.radians(angle)) * speed,
            math.sin(math.radians(angle)) * speed
        )

        self.rot_angle = 0
        self.rot_speed = random.uniform(-2, 2)

    def _get_safe_spawn_position(self):
        center = pygame.math.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        while True:
            side = random.choice(['top', 'bottom', 'left', 'right'])
            if side == 'top':
                pos = pygame.math.Vector2(random.randint(0, SCREEN_WIDTH), -50)
            elif side == 'bottom':
                pos = pygame.math.Vector2(random.randint(0, SCREEN_WIDTH), SCREEN_HEIGHT + 50)
            elif side == 'left':
                pos = pygame.math.Vector2(-50, random.randint(0, SCREEN_HEIGHT))
            else:
                pos = pygame.math.Vector2(SCREEN_WIDTH + 50, random.randint(0, SCREEN_HEIGHT))

            if pos.distance_to(center) > 200:
                return pos

    def update(self):
        self.pos += self.vel
        self.rot_angle += self.rot_speed

        buffer = self.radius + 10
        if self.pos.x > SCREEN_WIDTH + buffer:
            self.pos.x = -buffer
        elif self.pos.x < -buffer:
            self.pos.x = SCREEN_WIDTH + buffer

        if self.pos.y > SCREEN_HEIGHT + buffer:
            self.pos.y = -buffer
        elif self.pos.y < -buffer:
            self.pos.y = SCREEN_HEIGHT + buffer

    def draw(self, surface, offset):
        rad = math.radians(self.rot_angle)
        points = []
        for x, y in self.shape:
            rx = x * math.cos(rad) - y * math.sin(rad)
            ry = x * math.sin(rad) + y * math.cos(rad)
            points.append((self.pos.x + rx + offset.x, self.pos.y + ry + offset.y))
        pygame.draw.polygon(surface, GRAY, points, 2)


class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, angle):
        super().__init__()
        rad = math.radians(angle)
        self.pos = pygame.math.Vector2(pos)
        self.vel = pygame.math.Vector2(math.sin(rad), -math.cos(rad)) * 12
        self.radius = 2
        self.life = 50

    def update(self):
        self.pos += self.vel
        self.life -= 1

        if self.life <= 0:
            self.kill()

        if self.pos.x > SCREEN_WIDTH:
            self.pos.x = 0
        elif self.pos.x < 0:
            self.pos.x = SCREEN_WIDTH

        if self.pos.y > SCREEN_HEIGHT:
            self.pos.y = 0
        elif self.pos.y < 0:
            self.pos.y = SCREEN_HEIGHT

    def draw(self, surface, offset):
        pygame.draw.circle(
            surface,
            WHITE,
            (int(self.pos.x + offset.x), int(self.pos.y + offset.y)),
            self.radius
        )


# --- 4. Main Game Engine ---
class Game:
    def __init__(self):
        self.sounds = SoundManager()
        self.reset()

    def reset(self):
        self.all_sprites = pygame.sprite.Group()
        self.asteroids = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()

        self.player = Player()
        self.all_sprites.add(self.player)

        self.score = 0
        self.lives = STARTING_LIVES
        self.next_extra_life_at = EXTRA_LIFE_EVERY
        self.extra_life_flash_timer = 0

        self.game_over = False
        self.pending_game_over = False
        self.wave = 1

        self.shake_amount = 0
        self.shake_offset = pygame.math.Vector2(0, 0)

        self.shoot_cooldown = 0

        self.leaderboard = self.load_scores()
        self.name_input = ""
        self.score_saved = False
        self.last_saved_entry = None

        self.spawn_asteroids(4, 'large')

    # ---------- Leaderboard ----------
    def load_scores(self):
        if not os.path.exists(SCORES_FILE):
            return []

        try:
            with open(SCORES_FILE, "r", encoding="utf-8") as f:
                scores = json.load(f)
            if not isinstance(scores, list):
                return []
            cleaned = []
            for item in scores:
                name = str(item.get("name", "ANON"))[:10]
                score = int(item.get("score", 0))
                cleaned.append({"name": name, "score": score})
            cleaned.sort(key=lambda x: x["score"], reverse=True)
            return cleaned[:MAX_LEADERBOARD]
        except Exception:
            return []

    def save_scores(self):
        try:
            with open(SCORES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.leaderboard[:MAX_LEADERBOARD], f, indent=2)
        except Exception:
            pass

    def sanitize_name(self, name):
        cleaned = "".join(ch for ch in name.upper() if ch.isalnum())
        return (cleaned[:10] or "ANON")

    def score_qualifies(self):
        if self.score <= 0:
            return False
        if len(self.leaderboard) < MAX_LEADERBOARD:
            return True
        return self.score > self.leaderboard[-1]["score"]

    def needs_name_entry(self):
        return self.game_over and not self.score_saved and self.score_qualifies()

    def submit_score(self, name):
        if self.score_saved:
            return

        entry = {"name": self.sanitize_name(name), "score": self.score}
        self.leaderboard.append(entry)
        self.leaderboard.sort(key=lambda x: x["score"], reverse=True)
        self.leaderboard = self.leaderboard[:MAX_LEADERBOARD]
        self.save_scores()

        self.score_saved = True
        self.last_saved_entry = entry
        self.leaderboard = self.load_scores()

    def finalize_score_if_needed(self):
        if self.needs_name_entry():
            self.submit_score(self.name_input)

    # ---------- Game Flow ----------
    def spawn_asteroids(self, num, size):
        for _ in range(num):
            ast = Asteroid(size)
            self.all_sprites.add(ast)
            self.asteroids.add(ast)

    def spawn_next_wave(self):
        self.wave += 1
        self.spawn_asteroids(min(3 + self.wave, 10), 'large')

    def add_score(self, points):
        self.score += points

        while self.score >= self.next_extra_life_at:
            self.lives += 1
            self.next_extra_life_at += EXTRA_LIFE_EVERY
            self.extra_life_flash_timer = 120
            self.sounds.play(self.sounds.snd_bonus)

    def split_asteroid(self, asteroid):
        self.add_score({'large': 20, 'medium': 50, 'small': 100}[asteroid.size])
        self.sounds.play(self.sounds.snd_explode)
        self.shake_amount = 5 if asteroid.size == 'large' else 2

        for _ in range(15 if asteroid.size == 'large' else 8):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1, 4)
            vel = pygame.math.Vector2(
                math.cos(angle) * speed,
                math.sin(angle) * speed
            ) + asteroid.vel
            self.particles.add(
                Particle(asteroid.pos, vel, GRAY, random.randint(20, 40), 2)
            )

        new_size = {'large': 'medium', 'medium': 'small'}.get(asteroid.size)
        if new_size:
            for _ in range(2):
                new_ast = Asteroid(new_size, asteroid.pos)
                new_ast.vel += pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
                self.all_sprites.add(new_ast)
                self.asteroids.add(new_ast)

        asteroid.kill()

    def trigger_shake(self):
        if self.shake_amount > 0:
            self.shake_offset = pygame.math.Vector2(
                random.uniform(-self.shake_amount, self.shake_amount),
                random.uniform(-self.shake_amount, self.shake_amount)
            )
            self.shake_amount *= 0.85
            if self.shake_amount < 0.5:
                self.shake_amount = 0
                self.shake_offset = pygame.math.Vector2(0, 0)

    def enter_game_over(self):
        self.game_over = True
        if not self.score_qualifies():
            self.score_saved = True

    def handle_player_death(self):
        self.lives -= 1
        self.player.explode(self.particles, self.sounds)
        self.shake_amount = 15

        if self.lives <= 0:
            self.pending_game_over = True

    def update_gameplay(self):
        keys = pygame.key.get_pressed()

        if keys[pygame.K_SPACE] and self.shoot_cooldown <= 0 and self.player.alive:
            if len(self.bullets) < 5:
                bullet = Bullet(self.player.get_cannon_world_pos(), self.player.angle)
                self.all_sprites.add(bullet)
                self.bullets.add(bullet)
                self.sounds.play(self.sounds.snd_shoot)
                self.shoot_cooldown = 15

        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1

        self.player.update(self.particles, self.sounds)
        self.asteroids.update()
        self.bullets.update()
        self.particles.update()
        self.trigger_shake()

        if self.extra_life_flash_timer > 0:
            self.extra_life_flash_timer -= 1

        # Bullet vs asteroid
        for bullet in list(self.bullets):
            for asteroid in list(self.asteroids):
                if bullet.pos.distance_to(asteroid.pos) < asteroid.radius + bullet.radius:
                    self.split_asteroid(asteroid)
                    bullet.kill()
                    break

        # Player vs asteroid
        if self.player.alive and self.player.invulnerable_timer <= 0:
            for asteroid in self.asteroids:
                if self.player.pos.distance_to(asteroid.pos) < asteroid.radius + self.player.radius:
                    self.handle_player_death()
                    break

        # Respawn or game over
        if not self.player.alive and self.player.respawn_timer <= 0:
            if self.pending_game_over:
                self.enter_game_over()
            else:
                self.player.respawn()

        # Next wave
        if not self.game_over and len(self.asteroids) == 0 and self.player.alive:
            self.spawn_next_wave()

    # ---------- Input ----------
    def handle_game_over_input(self, event):
        if self.needs_name_entry():
            if event.key == pygame.K_RETURN:
                self.submit_score(self.name_input)
            elif event.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
            else:
                ch = event.unicode.upper()
                if ch.isalnum() and len(self.name_input) < 10:
                    self.name_input += ch
        else:
            if event.key == pygame.K_r:
                self.reset()

    # ---------- Drawing ----------
    def draw_ui(self):
        score_text = font.render(f"SCORE: {self.score}", True, WHITE)
        lives_text = font.render(f"LIVES: {self.lives}", True, WHITE)
        mute_text = small_font.render(f"M: {'UNMUTE' if self.sounds.muted else 'MUTE'}", True, WHITE)
        quit_text = small_font.render("ESC: QUIT", True, WHITE)

        screen.blit(score_text, (20, 15))
        screen.blit(lives_text, (20, 45))
        screen.blit(mute_text, (SCREEN_WIDTH - mute_text.get_width() - 20, 15))
        screen.blit(quit_text, (SCREEN_WIDTH - quit_text.get_width() - 20, 40))

        if self.extra_life_flash_timer > 0:
            bonus = font.render("BONUS SHIP!", True, GREEN)
            screen.blit(
                bonus,
                (SCREEN_WIDTH // 2 - bonus.get_width() // 2, 20)
            )

    def draw_leaderboard(self):
        title = font.render("TOP 10 LEADERBOARD", True, YELLOW)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 250))

        start_y = 290
        shown = self.leaderboard[:MAX_LEADERBOARD]

        if not shown:
            line = board_font.render("No scores yet.", True, WHITE)
            screen.blit(line, (SCREEN_WIDTH // 2 - line.get_width() // 2, start_y))
            return

        for i, entry in enumerate(shown, start=1):
            color = WHITE
            if self.last_saved_entry and entry["name"] == self.last_saved_entry["name"] and entry["score"] == self.last_saved_entry["score"]:
                color = GREEN

            line = f"{i:>2}. {entry['name']:<10} {entry['score']:>7}"
            surf = board_font.render(line, True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, start_y + (i - 1) * 26))

    def draw_game_over(self):
        go_text = font.render("GAME OVER", True, RED)
        score_text = font.render(f"FINAL SCORE: {self.score}", True, WHITE)

        screen.blit(go_text, (SCREEN_WIDTH // 2 - go_text.get_width() // 2, 60))
        screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, 100))

        if self.needs_name_entry():
            prompt = small_font.render("New Top 10 Score! Enter name and press ENTER:", True, WHITE)
            name = self.name_input if self.name_input else "_"
            name_text = font.render(name, True, GREEN)

            screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, 150))
            screen.blit(name_text, (SCREEN_WIDTH // 2 - name_text.get_width() // 2, 180))

            hint = small_font.render("After saving: R restart, ESC quit", True, WHITE)
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 220))
        else:
            hint = small_font.render("Press R to Restart or ESC to Quit", True, WHITE)
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 180))

        self.draw_leaderboard()

    def draw(self):
        screen.fill(BLACK)
        offset = self.shake_offset

        for sprite in self.all_sprites:
            sprite.draw(screen, offset)
        for particle in self.particles:
            particle.draw(screen, offset)

        self.draw_ui()

        if self.game_over:
            self.draw_game_over()

        pygame.display.flip()

    # ---------- Main Loop ----------
    def run(self):
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.finalize_score_if_needed()
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.finalize_score_if_needed()
                        running = False

                    elif event.key == pygame.K_m and not self.needs_name_entry():
                        self.sounds.toggle_mute()

                    elif self.game_over:
                        self.handle_game_over_input(event)

            if not self.game_over:
                self.update_gameplay()
            else:
                self.particles.update()
                self.trigger_shake()

            self.draw()
            clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    game = Game()
    game.run()