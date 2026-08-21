#!/usr/bin/env python3
"""
Level-4 transition benchmark - measures the exact moment GasClouds spawn.

The freeze happens in WASM when level 4+ completes and GasClouds are created
mid-frame. This benchmark:
1. Measures GasCloud init time (surface creation + draw calls)
2. Measures the variance (GC pauses show up as outliers)
3. Tests cumulative effect of creating multiple clouds in one frame
4. Measures blit cost of drawing clouds to the screen

Usage:
    python benchmark_level4.py [--clouds 5] [--iterations 50]
"""
import asyncio
import math
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
pygame.display.set_mode((800, 600))

# Import main without triggering asyncio.run(main())
_original_asyncio_run = asyncio.run
asyncio.run = lambda *a, **kw: None
_original_platform = sys.platform
sys.platform = 'emscripten'
import main
sys.platform = _original_platform
asyncio.run = _original_asyncio_run

import asyncio


def measure_single_cloud(sw, sh):
    """Measure time to create one GasCloud at the given screen size."""
    orig_sw, orig_sh = main.SCREEN_WIDTH, main.SCREEN_HEIGHT
    main.SCREEN_WIDTH, main.SCREEN_HEIGHT = sw, sh
    start = time.perf_counter()
    cloud = main.GasCloud()
    elapsed = (time.perf_counter() - start) * 1000
    main.SCREEN_WIDTH, main.SCREEN_HEIGHT = orig_sw, orig_sh
    return elapsed, cloud


def measure_blit_cost(cloud, screen_size, num_blit=1000):
    """Measure time to blit a cloud surface N times (simulates drawing)."""
    screen = pygame.Surface(screen_size, pygame.SRCALPHA)
    start = time.perf_counter()
    for _ in range(num_blit):
        screen.blit(cloud.dark_surface, (100, 100))
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed / num_blit


def measure_surface_creation(size):
    """Measure time to create a single SRCALPHA surface."""
    start = time.perf_counter()
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed


def measure_draw_calls(size, num_calls):
    """Measure time to draw N circles on a surface."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    import random
    start = time.perf_counter()
    for _ in range(num_calls):
        x = random.randint(0, size)
        y = random.randint(0, size)
        r = random.randint(5, 30)
        pygame.draw.circle(surf, (10, 10, 30, 200), (x, y), r)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed


def analyze(samples):
    """Compute statistics."""
    if not samples:
        return {}
    samples = sorted(samples)
    n = len(samples)
    avg = sum(samples) / n
    return {
        "n": n, "avg": avg, "min": samples[0], "max": samples[-1],
        "p50": samples[n // 2], "p95": samples[int(n * 0.95)],
        "p99": samples[int(n * 0.99)],
    }


def main_cmd():
    import argparse
    parser = argparse.ArgumentParser(description="Level-4 transition benchmark")
    parser.add_argument("--clouds", type=int, default=5, help="Number of clouds to create in one burst")
    parser.add_argument("--iterations", type=int, default=50, help="Number of iterations")
    args = parser.parse_args()

    git_head = os.popen("git rev-parse --short HEAD").read().strip()
    print("=" * 60)
    print(f"Git HEAD: {git_head}")
    print(f"GasCloud surface cap: 256px")
    print("=" * 60)

    # Test 1: Surface creation cost
    print("\n[1] SRCALPHA surface creation time (isolated)")
    for size in [128, 256, 512, 800]:
        times = [measure_surface_creation(size) for _ in range(100)]
        s = analyze(times)
        print(f"  {size}x{size}: avg={s['avg']:.3f}ms  p95={s['p95']:.3f}ms  max={s['max']:.3f}ms")

    # Test 2: Draw call cost
    print("\n[2] Draw call cost on 256x256 surface (isolated)")
    for num in [20, 60, 100, 200, 300, 500]:
        times = [measure_draw_calls(256, num) for _ in range(50)]
        s = analyze(times)
        per_call = s['avg'] / num * 1000
        print(f"  {num:3d} calls: total={s['avg']:.3f}ms  per_call={per_call:.2f}µs  max={s['max']:.3f}ms")

    # Test 3: Single cloud creation at various screen sizes
    print("\n[3] Single GasCloud init time (surface + draw calls)")
    for sw, sh in [(375, 812), (800, 600), (1024, 768), (1920, 1080)]:
        times = []
        for _ in range(args.iterations):
            t, _ = measure_single_cloud(sw, sh)
            times.append(t)
        s = analyze(times)
        print(f"  {sw}x{sh}: avg={s['avg']:.2f}ms  p50={s['p50']:.2f}ms  p95={s['p95']:.2f}ms  max={s['max']:.2f}ms")

    # Test 4: Burst creation (simulates level transition: N clouds in one frame)
    print(f"\n[4] Burst creation: {args.clouds} clouds in one frame (iPhone 375x812)")
    burst_times = []
    for _ in range(args.iterations):
        start = time.perf_counter()
        clouds = []
        for _ in range(args.clouds):
            _, cloud = measure_single_cloud(375, 812)
            clouds.append(cloud)
        elapsed = (time.perf_counter() - start) * 1000
        burst_times.append(elapsed)
    s = analyze(burst_times)
    print(f"  Total: avg={s['avg']:.2f}ms  p50={s['p50']:.2f}ms  p95={s['p95']:.2f}ms  max={s['max']:.2f}ms")
    print(f"  Per cloud: {s['avg']/args.clouds:.2f}ms")
    print(f"  Frame budget @60fps: 16.67ms")
    print(f"  Budget after burst: {16.67 - s['avg']:.2f}ms remaining")

    # Test 5: Outlier analysis (GC pauses show up as high p99/max)
    print(f"\n[5] Outlier analysis (single cloud, 200 iterations)")
    times = []
    for _ in range(200):
        t, _ = measure_single_cloud(375, 812)
        times.append(t)
    s = analyze(times)
    print(f"  avg={s['avg']:.2f}ms  p50={s['p50']:.2f}ms  p95={s['p95']:.2f}ms  p99={s['p99']:.2f}ms  max={s['max']:.2f}ms")
    outliers = [t for t in times if t > s['avg'] * 3]
    print(f"  Outliers (>3x avg): {len(outliers)} ({100*len(outliers)/len(times):.1f}%)")
    if outliers:
        print(f"  Outlier values: {['%.2f' % t for t in sorted(outliers)[:10]]}")

    # Test 6: Blit cost (drawing clouds every frame)
    print(f"\n[6] Blit cost: drawing cloud to screen 1000 times")
    _, cloud = measure_single_cloud(375, 812)
    for screen_size in [(375, 812), (800, 600), (1024, 768)]:
        per_blit = measure_blit_cost(cloud, screen_size, 1000)
        print(f"  {screen_size[0]}x{screen_size[1]}: {per_blit*1000:.2f}µs per blit")

    print("\n" + "=" * 60)
    print("WASM estimate: multiply times by 5-10x for browser main thread")
    print("=" * 60)


if __name__ == "__main__":
    main_cmd()
