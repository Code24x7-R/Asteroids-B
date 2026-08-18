# 🌌 Asteroids: 3D Holographic

A modernized, tactically deep reimagining of the classic arcade game Asteroids, built entirely from scratch in Python and Pygame.
This version ditches standard sprites for a custom pseudo-3D wireframe projection engine, features 100% procedurally generated audio (no external sound files required), and introduces deep environmental mechanics like Gas Clouds, bullet interception, and a massive Level 10 Boss fight.

## ✨ Key Features

- **Pseudo-3D Holographic Engine:** Custom mathematical projection renders wireframe asteroids, ships, and particles with depth, lighting, and perspective scaling.
- **Procedural Audio Synthesis:** All sound effects (lasers, explosions, thrust, boss pulses) are generated on the fly using PCM wave math. Zero external assets required.
- **Tactical Stealth & Gas Clouds:** Hide inside massive, volatile Gas Clouds to break Saucer target-locks.
- **Chain-Reaction Detonation:** Destroying an asteroid or saucer inside a Gas Cloud ignites the gas, creating a massive screen-clearing shockwave.
- **Advanced Combat:** Shoot enemy bullets out of the air (Interception) or trick Saucers into destroying each other (Friendly Fire).
- **The Leviathan (Level 10 Boss):** A colossal dreadnought featuring a black-hole gravity well, an event horizon that crushes ships, and dynamic "Singularity" attack patterns.
- **AI Mode:** Step away from the keyboard, and the game's advanced Auto-Pilot will take over, navigating asteroid fields and fleeing boss gravity wells.
- **Persistent Leaderboards:** High scores are saved to `leaderboard_3d.json` (Desktop) and synced with `localStorage` (WebAssembly).
- **WebAssembly & Browser Playable:** Runs directly in any modern web browser via Pygbag/WASM with touch & gamepad support.
## 📦 Dependencies

This project is designed to be lightweight and relies on a single external library.
- Python 3.8+
- Pygame 2.0+ or Pygame-ce
- Pygbag (for WebAssembly builds: `pip install pygbag`)
## 🚀 Installation & Setup

1. Prerequisites
Ensure you have Python installed on your system. You can verify by running python --version or python3 --version in your terminal.
2. Install Pygame
Open your terminal or command prompt and install Pygame via pip:
```
pip install pygame
```
3. Run the Game
Save the main game code as main.py (or asteroids.py) and execute it:

```
python main.py
```
4. Resolution Selection
Upon launching, a menu will appear allowing you to select your screen resolution.
Press 1 through 6 to select a resolution.
If no input is detected after 8 seconds, the game will automatically boot into your monitor's native resolution.

## 🌐 WebAssembly (Play in Browser)

Asteroids 3D can be compiled to pure WebAssembly and hosted on GitHub Pages, itch.io, Netlify, or any static web host.

### 1. Build WebAssembly Distribution (Windows)
Run the PowerShell build script:
```powershell
.\make-wasm.ps1
```
To build and immediately launch a local preview server:
```powershell
.\make-wasm.ps1 -Serve
```

### 2. Build WebAssembly Distribution (Linux / macOS / CI)
```bash
./make-wasm.sh
```

### 3. Deploy Targets
- **GitHub Pages:** A pre-configured workflow (`.github/workflows/deploy-pages.yml`) automatically builds and publishes changes on push to `main`. Served at the custom domain [https://asteroids.mouseclick.au](https://asteroids.mouseclick.au) (HTTPS enforced; `CNAME` file is bundled with every deploy).
- **itch.io:** Upload the generated `dist/asteroids-3d-web.zip` archive directly as an HTML5 web game.
- **Static Hosting:** Drop all files from `dist/web/` onto any static hosting server or CDN.
## 🎮 Controls

Keyboard
```
Key	Action
Left / Right Arrow	Rotate Ship
Up Arrow	Thrust
Spacebar	Fire Cannon
M	Mute / Unmute Audio
Q	Quit Game
R	Reboot / Restart (On Game Over or Credits screen)
```
Gamepad / Controller (Xbox/PlayStation layout)
```
Button	Action
Left Stick	Rotate & Thrust (Push up to thrust)
Right Trigger (RT)	Fire Cannon
Start / Menu	Quit Game
Select / Back	Mute / Unmute Audio
```

## 🧠 Gameplay Strategies & Tactics

This isn't just a game of reflexes; it's a game of positioning and environmental awareness.
1. Master the Gas Clouds (Stealth & Nukes)
The Cloak: When Saucers are hunting you, fly into a Gas Cloud. The Saucers will lose their target lock, stop flanking, and fire blindly into space. Your ship will render in "Stealth Mode" (dimmed cyan).
The Trap: Gas clouds are highly volatile. If you shoot an asteroid and it explodes inside the cloud's radius, the cloud will detonate. This creates a massive shockwave that destroys nearby enemies and pushes your ship away. Use this to clear crowded screens!
Warning: Bullets pass freely through clouds, but explosions ignite them. Don't detonate a cloud while you are sitting in the center of it, or the shockwave will destroy you!
2. Bullet Interception & Friendly Fire
Interception: You can shoot enemy bullets out of the air. If a Saucer fires a spread shot, shoot the center bullet to trigger a chain reaction that clears the others.
Friendly Fire: Saucers do not recognize each other as targets. If you position yourself perfectly, a Saucer's tracking shot will fly past you and destroy a flanking Saucer, awarding you points and clearing the field.
3. Surviving the Leviathan (Level 10 Boss)
The Boss is a massive 10x scaled Saucer with a Black Hole Gravity Well.
The Event Horizon: The dark purple core of the boss is an instant-kill zone. If your ship crosses the threshold, you will be crushed.
Gravity Escape: The boss constantly pulls you, asteroids, and bullets toward its core. If you feel the pull getting too strong, turn your ship directly away from the boss and engage Maximum Thrust to break orbit.
Singularity Burst: When the boss's accretion disks turn glowing orange/red, it is charging a Singularity. It will pause and release a massive 360-degree ring of heavy bullets. Keep moving orthogonally (perpendicular) to the boss to slip through the gaps.
Entry Shield: The boss spawns with a white shield and is completely invulnerable while warping to the center of the screen. Save your ammo until the shield drops!
4. Powerup Management
Shield (Green): Absorbs one fatal hit (asteroid or bullet). Essential for navigating dense asteroid fields.
Rapid Fire (Yellow) & 2x Score (Purple): Best utilized when you have a clear line of sight. Don't pick up Rapid Fire while hiding in a Gas Cloud, or you might accidentally detonate it!

## 🤖 AI Mode (Demo)

If you do not press any keys or use the controller for 10 seconds, the game will enter AI MODE.
The Auto-Pilot uses predictive vector math to target the closest threats, collect powerups, and—crucially—recognize the Boss's gravity well, automatically fleeing the Event Horizon to survive. Press any key to instantly take back control.

```
├── asteroids-b.py          # Complete 3D holographic game engine (Desktop + WASM)
├── main.py                 # Primary entry point
├── make-wasm.ps1           # Windows build & packaging script for WebAssembly
├── make-wasm.sh            # POSIX build script for Linux/macOS/CI
├── make-b.ps1              # Desktop PyInstaller binary build script
├── pygbag.ini              # Pygbag packaging rules
├── web/
│   └── template.tmpl       # Cyberpunk HTML5 template & styling wrapper
├── dist/
│   ├── web/                # Built WebAssembly web page & assets
│   ├── asteroids-3d-web.zip# itch.io deployment archive
│   └── asteroids-b.exe     # Standalone Windows executable
├── leaderboard_3d.json     # Local leaderboard storage
└── README.md               # Project documentation
```
## 🛠️ Troubleshooting

- **Audio Cracking/Lag:** The game generates audio buffers on the fly. If you experience audio stuttering on older hardware, press M to mute the game, which disables the audio thread and can improve CPU performance.
- **Controller Not Detected:** Ensure your controller is plugged in before launching the game. Pygame initializes the joystick module on startup.



