#!/usr/bin/env python3
"""Verify the cloud queue fix: clouds spawn one-per-frame, not all at once."""
import asyncio
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
pygame.display.set_mode((800, 600))

_original_asyncio_run = asyncio.run
asyncio.run = lambda *a, **kw: None
_original_platform = sys.platform
sys.platform = 'emscripten'
import main
sys.platform = _original_platform
asyncio.run = _original_asyncio_run


def test_cloud_queue():
    """Simulate level 4 transition and verify clouds spawn one-per-frame."""
    game = main.Game()

    # Force level 4
    game.level = 4
    game.clouds.empty()

    # Call spawn_level - should queue 2 clouds, not create them directly
    game.spawn_level()

    print(f"Pending cloud spawns: {game._pending_cloud_spawns}")
    print(f"Clouds in group: {len(game.clouds)}")

    assert game._pending_cloud_spawns == 2, f"Expected 2 pending, got {game._pending_cloud_spawns}"
    assert len(game.clouds) == 0, f"Expected 0 clouds immediately, got {len(game.clouds)}"

    # Simulate frames - one cloud should spawn per frame
    for frame in range(5):
        # Run the cloud spawning logic (copied from game loop)
        if game._pending_cloud_spawns > 0:
            game._pending_cloud_spawns -= 1
            game.clouds.add(main.GasCloud())
        print(f"Frame {frame}: pending={game._pending_cloud_spawns}, clouds={len(game.clouds)}")

    assert game._pending_cloud_spawns == 0, f"Expected 0 pending after 5 frames, got {game._pending_cloud_spawns}"
    assert len(game.clouds) == 2, f"Expected 2 clouds after 5 frames, got {len(game.clouds)}"

    print("\nCloud queue test PASSED!")


def test_level5_transition():
    """Simulate level 5 transition (should add 1 more cloud to existing 2)."""
    game = main.Game()
    game.level = 5
    game.clouds.empty()

    # Pre-populate with 2 clouds from level 4
    for _ in range(2):
        game.clouds.add(main.GasCloud())

    game.spawn_level()

    print(f"\nLevel 5 transition:")
    print(f"Pending: {game._pending_cloud_spawns}, Clouds: {len(game.clouds)}")

    # Should queue 1 more cloud (3 desired - 2 existing = 1)
    assert game._pending_cloud_spawns == 1, f"Expected 1 pending, got {game._pending_cloud_spawns}"
    assert len(game.clouds) == 2, f"Expected 2 clouds (existing), got {len(game.clouds)}"

    # Spawn it
    if game._pending_cloud_spawns > 0:
        game._pending_cloud_spawns -= 1
        game.clouds.add(main.GasCloud())

    assert len(game.clouds) == 3, f"Expected 3 clouds, got {len(game.clouds)}"
    print("Level 5 transition test PASSED!")


def test_level1_no_clouds():
    """Level 1 should not queue any clouds."""
    game = main.Game()
    game.level = 1
    game.clouds.empty()

    game.spawn_level()

    assert game._pending_cloud_spawns == 0, f"Expected 0 pending for level 1, got {game._pending_cloud_spawns}"
    assert len(game.clouds) == 0, f"Expected 0 clouds for level 1, got {len(game.clouds)}"
    print("\nLevel 1 (no clouds) test PASSED!")


def main_cmd():
    print("=" * 60)
    print("Cloud Queue Fix Verification")
    print("=" * 60)
    test_cloud_queue()
    test_level5_transition()
    test_level1_no_clouds()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main_cmd()
