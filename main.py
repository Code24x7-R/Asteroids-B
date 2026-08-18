"""
Main entry point for Asteroids 3D Holographic UIX (WebAssembly & Desktop).
"""
import asyncio
import importlib

async def main():
    game_mod = importlib.import_module("asteroids-b")
    await game_mod.main()

if __name__ == "__main__":
    asyncio.run(main())
