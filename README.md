# Wraith W75 Profile Changer

Automatically switches your Wraith W75 keyboard to your game profile when you focus a game, and back to your normal profile when you switch to anything else. It runs quietly in the system tray.

[Türkçe README](README.tr.md)

> This is an unofficial community tool. It is not affiliated with or endorsed by Wraith or the makers of the keyboard.

## The problem

The Wraith configurator at [wraith.software](https://wraith.software) keeps your profiles in the browser, not in the keyboard. To change profile you have to open the site, connect the keyboard and click the profile yourself. If you want different lighting, key mappings or actuation settings for games, you repeat this every time you launch or leave a game.

## What this tool does

- Watches which application has focus.
- When a game is in the foreground, it loads your game profile onto the keyboard.
- When you switch to another application (Alt+Tab, desktop, browser), it loads your normal profile again.
- Lets you choose which applications count as games from a small settings window.
- Starts with Windows and lives in the system tray (grey icon for the normal profile, green icon for the game profile).

It talks to the keyboard directly over USB HID, so no browser has to stay open.

## How it works

On this keyboard, switching a profile on the website uploads that profile's whole configuration to the keyboard as a series of 64-byte HID reports (roughly 120 of them). This tool records that series once, when you click a profile on the website, and stores it in `profiles.json`. Later it replays the recorded reports whenever the focused application changes.

Because the reports are a snapshot, you need to record a profile again after you change it on the website. The settings window has a step-by-step wizard for this.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer (developed and tested on Python 3.14)
- A Wraith W75 connected with a USB cable
- A Chromium-based browser (Chrome, Edge) for the one-time profile recording step, because the Wraith website uses WebHID

Tested only with the Wraith W75 over a USB cable. Other Wraith models that expose the same configuration interface (HID usage page `0xFF1B`, usage `0x91`) may work but are untested. Wireless modes are untested.

## Installation

```bash
git clone https://github.com/cankamer/Wraith-W75-Profile-Changer.git
cd Wraith-W75-Profile-Changer
pip install -r requirements.txt
```

Start it without a console window by double-clicking `start.bat`, or run:

```bash
pythonw wraith_auto.py
```

A grey "W" icon appears in the system tray (it may be inside the hidden icons area).

## First-time setup

The app ships without any profiles, because a profile is specific to your keyboard setup. Record two of them:

1. Double-click the tray icon to open the settings window.
2. In the **Klavye profilleri** (Keyboard profiles) section, click **Tanımla...** (Define) next to **Game profili** (Game profile).
3. Follow the wizard:
   1. Open the website with the provided button and connect your keyboard (Connect button).
   2. Set up the profile you want to use for games on the website (lighting, keys, and so on).
   3. Press `F12` on the website, open the **Console** tab, use the button to copy the code, paste it into the console and press Enter. If Chrome asks you to type `allow pasting` first, do that. If Chrome asks for local network access, allow it.
   4. In the website's left menu, click your normal profile first, then your game profile.
   5. When the wizard shows the captured packet count, press **Kaydet** (Save).
4. Repeat for **Normal profil** (Normal profile). This time click your game profile first, then your normal profile.
5. Click **Uygulama seç...** (Choose application) or **Çalışanlardan seç...** (Choose from running) to add your games, or leave the automatic detection on.
6. Tick **Windows ile birlikte başlat** (Start with Windows) if you want it to run at login.

Test the switch at any time with:

```bash
python wraith_auto.py --test
```

It loads the game profile, waits four seconds and loads the normal profile again. If you changed the lighting of the game profile on the website, you will see it change on the keyboard.

## Daily use

The tray icon menu:

| Item | Meaning |
| --- | --- |
| Status line | Current profile and the application that triggered it |
| Ayarlar... | Opens the settings window (also opens on double-click) |
| Otomatik | Follows the focused application (default) |
| Oyun profili (elle) | Forces the game profile |
| Normal profil (elle) | Forces the normal profile |
| Windows ile başlat | Adds or removes the app from Windows startup |
| Çıkış | Quits |

In the settings window you can add applications by choosing an `.exe` file or picking from the running programs, remove them, redefine the two profiles, toggle automatic detection and toggle startup.

### How a game is recognised

The application that owns the focused window counts as a game when either:

- its executable name is in the `games` list (for example `cs2.exe`), or
- automatic detection is on and its executable path contains one of the folders in `game_path_patterns` (Steam `steamapps/common`, Epic Games, Riot Games and Battle.net by default).

Launchers and helper processes such as Steam, the Epic launcher and Wallpaper Engine are ignored. Games running as administrator may not expose their path; add those to the `games` list by name.

## Configuration

Settings are stored in `config.json`, created on first run. Changes are picked up within a second, without restarting.

| Key | Default | Description |
| --- | --- | --- |
| `game_profile` | `"game"` | Name of the game profile in `profiles.json` |
| `normal_profile` | `"default"` | Name of the normal profile in `profiles.json` |
| `poll_seconds` | `0.5` | How often the focused window is checked |
| `stable_polls` | `2` | Focus must stay the same for this many checks before switching |
| `min_switch_seconds` | `4` | Minimum time between two profile loads |
| `auto_detect` | `true` | Treat programs in known game folders as games |
| `games` | `[]` | Executable names that always count as games |
| `game_path_patterns` | see file | Path fragments (use `/`) that mark a game folder |
| `ignore_names` | see file | Executables that never count as games |
| `ignore_path_parts` | see file | Path fragments that never count as games |

## Safety measures

Loading a profile rewrites the keyboard's configuration for about a second and a half. To reduce the chance of interfering with typing, the tool:

- waits until no key is held down before loading a profile (after five seconds it loads anyway),
- waits at least `min_switch_seconds` between loads,
- requires the focus to be stable for a moment, so quickly passing through Alt+Tab does not trigger a load.

If a key ever stops responding, unplugging and replugging the keyboard restores its normal state.

## Privacy and security

- The tool reads only the name and path of the process that owns the focused window. It does not inject into games, read game memory or capture keystrokes.
- Nothing is sent over the internet. All communication with the keyboard is local USB HID.
- While the profile recording wizard is open, the tool listens on `127.0.0.1:8765`. The listener stops when the wizard closes, uses a random token generated for each wizard session, and accepts only requests whose `Origin` is `https://wraith.software`. Other websites cannot send data to it.
- The code you paste into the browser console only forwards the reports the website sends to the keyboard, and only to that local listener.
- `profiles.json` contains your keyboard configuration and `config.json` contains your game list. Both are excluded from version control.

## Troubleshooting

**The tray status shows an error about a missing profile.** Define both profiles in the settings window first (see First-time setup).

**Keyboard not found.** Make sure it is connected with a USB cable and not used exclusively by another program. `log.txt` records switches and errors.

**A game is not detected.** Focus the game, open the settings window, choose **Çalışanlardan seç...** and add it. Alternatively add its executable name to `games` in `config.json`.

**The game profile looks outdated.** You changed it on the website after recording it. Record it again with the wizard.

**Nothing arrives in the wizard.** Check that you pasted the code into the console of the `wraith.software` tab, that the keyboard is connected on that page, and that you clicked a profile after pasting.

## Files

| File | Purpose |
| --- | --- |
| `wraith_auto.py` | Tray app, focus monitor, settings window and keyboard communication |
| `profile_capture.py` | Local listener used by the profile recording wizard |
| `start.bat` | Starts the app without a console window |
| `requirements.txt` | Python dependencies |
| `config.json` | Your settings (created on first run, not committed) |
| `profiles.json` | Your recorded profiles (created by the wizard, not committed) |
| `log.txt` | Profile switch log (not committed) |

## Disclaimer

This tool sends raw configuration reports to your keyboard. It replays exactly what the official website sends, but it is provided as is, without any warranty. Use it at your own risk.

## License

MIT. See [LICENSE](LICENSE).
