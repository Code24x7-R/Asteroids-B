#!/usr/bin/env python3
"""
Game loop benchmark - measures frame-timing of the real game loop.

Tests three things that matter for FPS:
1. Yield overhead: how much does each `await asyncio.sleep(0)` cost?
2. GasCloud init: time to construct N clouds (the level-4 bottleneck)
3. Full game loop: actual frame times running the real game

Usage:
    python benchmark_loop.py [--frames 600] [--warmup 60] [--csv]
"""
import asyncio
import csv
import math
import os
import sys
import time

# Headless pygame BEFORE importing main
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
pygame.display.set_mode((800, 600))

# Import main.py without triggering its module-level side effects:
# 1. show_resolution_menu() - loops forever waiting for user input
# 2. asyncio.run(main()) - runs the game loop forever
#
# Strategy: mock asyncio.run BEFORE importing main, so the module-level
# call is a no-op. Then manually create and control the Game.
_original_asyncio_run = asyncio.run
asyncio.run = lambda *a, **kw: None  # noqa: E731

# Force IS_WASM so the resolution menu is skipped
_original_platform = sys.platform
sys.platform = 'emscripten'

import main

# Restore
sys.platform = _original_platform
asyncio.run = _original_asyncio_run


# ---------------------------------------------------------------------------
# Test 1: Raw yield overhead
# ---------------------------------------------------------------------------
async def measure_yield_overhead(iterations=2000):
    """Measure how long N sequential `await asyncio.sleep(0)` calls take."""
    start = time.perf_counter()
    for _ in range(iterations):
        await asyncio.sleep(0)
    elapsed = time.perf_counter() - start
    per_yield_us = (elapsed / iterations) * 1_000_000
    return per_yield_us


# ---------------------------------------------------------------------------
# Test 2: GasCloud init time
# ---------------------------------------------------------------------------
def measure_gascloud_init(n=100):
    """Measure time to construct N GasCloud objects (iPhone size)."""
    orig_sw, orig_sh = main.SCREEN_WIDTH, main.SCREEN_HEIGHT
    main.SCREEN_WIDTH, main.SCREEN_HEIGHT = 375, 812

    times = []
    for _ in range(n):
        start = time.perf_counter()
        cloud = main.GasCloud()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    main.SCREEN_WIDTH, main.SCREEN_HEIGHT = orig_sw, orig_sh
    return times


# ---------------------------------------------------------------------------
# Test 3: Full game loop frame times
# ---------------------------------------------------------------------------
class MockClock:
    """Drop-in replacement for pygame.time.Clock that measures frame times."""
    def __init__(self, real_clock, max_frames, warmup):
        self._real = real_clock
        self._max_frames = max_frames
        self._warmup = warmup
        self.frame_times = []
        self.counter = 0
        self._last_ticks = pygame.time.get_ticks()
        self._done = False

    def tick(self, fps):
        """Same signature as Clock.tick but records timing and stops after N frames."""
        now = pygame.time.get_ticks()
        dt = now - self._last_ticks
        self._last_ticks = now
        self.counter += 1
        if self.counter > self._warmup and not self._done:
            self.frame_times.append(dt)
        if self.counter > self._max_frames + self._warmup:
            self._done = True
            raise StopAsyncIteration("benchmark complete")
        # Delegate to real clock for actual frame pacing
        return self._real.tick(fps)

    def tick_busy_loop(self, fps):
        return self._real.tick_busy_loop(fps)

    def get_time(self):
        return self._real.get_time()

    def get_rawtime(self):
        return self._real.get_rawtime()

    def get_fps(self):
        return self._real.get_fps()


def run_game_loop_benchmark(frames=600, warmup=60):
    """Run the real game loop and collect frame times."""
    game = main.Game()

    # Replace MODULE-LEVEL clock with our mock (game uses main.clock)
    original_clock = main.clock
    main.clock = MockClock(original_clock, frames, warmup)

    # Force demo mode so AI plays (deterministic workload)
    game.demo_mode = True
    game.demo_timeout = 999999
    game.last_input_time = -999999

    try:
        asyncio.run(game.run())
    except StopAsyncIteration:
        pass
    except Exception as e:
        print(f"  Game loop error: {e}", file=sys.stderr)

    # Restore
    result = main.clock.frame_times
    main.clock = original_clock
    return result


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def analyze(samples):
    """Compute statistics from a list of timing samples."""
    if not samples:
        return {}
    samples = sorted(samples)
    n = len(samples)
    avg = sum(samples) / n
    min_v = samples[0]
    max_v = samples[-1]
    p50 = samples[n // 2]
    p95 = samples[int(n * 0.95)]
    p99 = samples[int(n * 0.99)]
    variance = sum((x - avg) ** 2 for x in samples) / n
    std = math.sqrt(variance)
    return {
        "n": n, "avg": avg, "std": std,
        "min": min_v, "max": max_v,
        "p50": p50, "p95": p95, "p99": p99,
    }


def fmt_ms(stats):
    """Format millisecond stats."""
    if not stats:
        return "  (no data)"
    lines = [
        "  n={n}  avg={avg:.2f}ms  std={std:.2f}ms\n"
        "  min={min:.2f}ms  p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms  max={max:.2f}ms".format(**stats),
    ]
    if stats["avg"] > 0:
        lines.append("  avg FPS = {:.1f}".format(1000.0 / stats["avg"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main_cmd():
    import argparse
    parser = argparse.ArgumentParser(description="Game loop benchmark")
    parser.add_argument("--frames", type=int, default=600,
                        help="Number of game-loop frames to measure")
    parser.add_argument("--warmup", type=int, default=60,
                        help="Warmup frames before measuring")
    parser.add_argument("--csv", action="store_true",
                        help="Output raw frame times as CSV")
    args = parser.parse_args()

    git_head = os.popen("git rev-parse --short HEAD").read().strip()
    print("=" * 60)
    print(f"Git HEAD: {git_head}")
    print(f"FPS target: {main.FPS}  (frame budget: {1000/main.FPS:.1f}ms)")
    print("=" * 60)

    # -- Test 1: yield overhead --
    print("\n[1] Yield overhead (await asyncio.sleep(0))")
    per_yield_us = asyncio.run(measure_yield_overhead(2000))
    print(f"  {per_yield_us:.1f} µs per yield")
    print(f"  At 60 FPS with 2 yields/frame: {per_yield_us * 2 / 1000:.3f}ms overhead")
    print(f"  At 60 FPS with 3 yields/frame: {per_yield_us * 3 / 1000:.3f}ms overhead")

    # -- Test 2: GasCloud init --
    print("\n[2] GasCloud init time (100 clouds, iPhone 375x812)")
    gc_times = measure_gascloud_init(100)
    gc_stats = analyze(gc_times)
    print(fmt_ms(gc_stats))
    print(f"  Total for 2 clouds (level 4 spawn): {gc_stats['avg'] * 2:.1f}ms")

    # -- Test 3: full game loop --
    print(f"\n[3] Full game loop ({args.frames} frames, warmup {args.warmup})")
    print("  Running game...")
    frame_times = run_game_loop_benchmark(args.frames, args.warmup)

    if args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(["frame", "dt_ms"])
        for i, t in enumerate(frame_times):
            writer.writerow([i, f"{t:.3f}"])
        return

    loop_stats = analyze(frame_times)
    print(fmt_ms(loop_stats))

    # Slow frame analysis
    if loop_stats:
        slow_20 = sum(1 for t in frame_times if t > 20)
        slow_33 = sum(1 for t in frame_times if t > 33)
        print(f"\n  Frames > 20ms (sub-50fps): {slow_20}/{len(frame_times)} ({100*slow_20/len(frame_times):.1f}%)")
        print(f"  Frames > 33ms (sub-30fps): {slow_33}/{len(frame_times)} ({100*slow_33/len(frame_times):.1f}%)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main_cmd()
