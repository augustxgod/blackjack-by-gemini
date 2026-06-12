# blackjack-by-gemini
# 🎰 Virtual Casino — PySide6 / Qt6 Edition
> 🚀 **Note:** The entire core engine was completely refactored, modernized, and ported from Tkinter to PySide6 by **Claude  Opus (v4.8)**, while ongoing feature development and project maintenance continue to be actively driven by **Jules** powered by the **Gemini 3.1 Pro** agent.

A modern, thread-safe, and visually stunning desktop casino suite powered by **Python 3** and **PySide6 (Qt 6)**.

---

## 🎯 Project Vision & Purpose
This project represents a complete architectural evolution. Originally designed as a lightweight Tkinter prototype, it has been completely re-engineered into a robust, enterprise-grade desktop application. The primary goal is to deliver a premium casino client with seamless UI rendering and fully decoupled client-server network synchronization, supporting both single-player and LAN multiplayer modes.

---

## 🎮 Game Rooms & Features

* **Interactive Lobby**: A clean, centralized dashboard featuring elegant game tiles for instant room navigation.
* **Blackjack**: Traditional game rules featuring dynamic hand evaluations, custom split/double/insurance handling, and an integrated real-time AI Advisor.
* **Roulette**: European roulette layout paired with a custom-painted, mathematically accurate wheel component featuring a physical animated ball settling mechanism.
* **Slots (Lucky Spin)**: A classic three-reel slot machine built with independent rolling mechanics, customizable game symbols, sequential reel braking animations, and payout multiplier tables.
* **Poker (Five-Card Draw)**: A fully simulated poker room where you compete against three distinct, mathematically driven AI bots (Iris, Boris, Clara, and Dmitri) with native poker hand ranking evaluation.
* **Dynamic Chip Bank**: A smart bet selector that automatically filters unlocked token denominations up to $10,000 based on your current player wallet state.
* **Seamless LAN Multiplayer**: Includes a lightweight built-in networking thread allowing players to host a local session or connect directly via a remote IP address.

---

## 🚀 Core Evolution: Tkinter vs PySide6 Engine

The transition to the Qt6 rendering system introduced massive upgrades across the entire engineering pipeline:

| Criteria | Legacy Engine (Tkinter) | Modern Engine (PySide6 / Qt6) |

| **Thread Safety** | Network data interacted directly with widgets, leading to intermittent race conditions and UI freezes. | **Absolute Isolation via `Bridge`**. Threaded network states are safely marshalled onto the GUI pipeline using custom signals (`Qt.QueuedConnection`). |
| **Visual Styling** | Rigid OS-native default look, layout layouts built entirely on static pixel coordinates. | **Premium CSS-Stylesheet Driven**. Smooth radial gradients for card felt tables, anti-aliased geometry, and drop-shadow effects (`QGraphicsDropShadowEffect`). |
| **Animations** | Non-existent (instantaneous frame switching). | **Hardware-Accelerated UI**. Fluid layout-aware transitions, card fade-in effects, and physical traveling chip bet animations. |
| **Sound System** | Fully mute client. | **Procedural Audio Engine (`SoundManager`)**. Real-time game audio (chips, card deals, jackpots) is mathematically synthesized at runtime — requiring zero external asset files in the repo. |
| **Desktop Integration** | Mouse-only navigation with a persistent, distracting background command console window. | **Native Feel**. Fully bound keyboard shortcuts (H, S, Space, Enter), console window suppression via `pythonw.exe`, and runtime-rendered taskbar icons. |


                                                               Credits & Authorship (blackjack.py)
This project is the result of a successful tandem between two advanced AI models, which brought the code from a basic concept to a fully-fledged commercial product.

The blackjack.py file contains over 4,500 lines of code, and the authorship is distributed as follows:

                                                          Jules (Core Architecture & Logic):
The core of the application was masterfully written by the Jules neural network. Its contributions include the entire mathematical logic for the 5 mini-games (Blackjack, Roulette, Slots, Poker, Crash), the implementation of socket-based LAN multiplayer (Host/Join), and the complete migration of the project to the modern PySide6 (Qt) GUI framework using custom QPainter rendering.

                                                          Claude 4.6 Opus (Final Polish & UX):
The last 3 major updates, which transformed the prototype into a AAA-quality product, were brilliantly executed by Claude 4.6 Opus. Claude's contributions include:

UI & Localization: Resolving CSS specificity bugs for disabled buttons, fully integrating a bilingual translation system (EN/RU), and localizing the AI Poker Advisor.

AAA Save System: Reworking the ProfileManager to stealthily store player progress (the casino_save.json file) in hidden system directories (AppData / Library) instead of cluttering the game's executable folder.

Lobby Navigation: Introducing a "Back" button to return to the Main Menu, allowing players to seamlessly switch between Singleplayer, Multiplayer, and language settings without having to restart the .exe file.
Release v2.0: The PySide6 AAA Overhaul
This monumental update completely transforms the project from a basic script into a full-fledged commercial desktop application. We've completely abandoned outdated technologies in favor of modern graphics standards, implemented an AAA save system, and brought the user interface to perfection.

                                                                 About the authors  (Credits)
This code is the result of a unique collaboration between two human—led AI models.:

Claude (Engine Architect): Completely migrated the project from the outdated Tkinter engine to the modern PySide6 (Qt) framework. Laid a powerful foundation: smooth rendering via QPainter, stable network code (Host/Join on sockets) and thread-safe interface update (QObject.Signal).

Jules (Game Designer and UI Engineer): Wrote impeccable mathematics for all five mini-games, implemented an AI advisor, brought UI/UX (CSS styles, animations, button states) to shine and integrated all advanced system features (localization, hidden saves).

                                           What 's new in version 2.0: (blackjackpyside6.py)
, AAA-the system of saving (Hidden AppData)
Goodbye, trash on the Desktop: The casino_save progress file.json is no longer created in the game folder.

The engine now automatically detects your OS and safely hides saves in hidden system directories.:

 Windows: %APPDATA%\VirtualCasino

 macOS: ~/Library/Application Support/VirtualCasino

 Linux: ~/.local/share/VirtualCasino

Your balance, stats, and trophies are now completely safe, even if you move or delete the file folder.

                                                       Full bilingual localization (EN / RU)
The global TRANSLATIONS dictionary has been implemented. The interface is translated on the fly by pressing the 🇬🇧 EN / 🇷🇺 RU buttons in the main menu.

Localization of the AI Advisor: The built-in poker AI assistant now speaks in pure Russian, dynamically substituting translated names of combinations (from "High Card" to "Royal Flush") and giving betting tips.

                                                           Premium UI/UX
Smart Buttons: The CSS-specificity conflict has been completely resolved. Inactive buttons (for example, CASH OUT before the rocket launch or Place Bet during the game) now "go out" correctly (they get opacity and a transparent background), eliminating confusion.

Lobby Navigation: The long-awaited "Back" button has been added to the game selection screen. Players can now seamlessly exit the lobby to the main menu to change the language or mode (Single/Multiplayer). without restarting the application.

Dynamic ChipBar: The chips increase when clicked and get a beautiful neon glow, and the unselected denominations are darkened.

                                                     Critical Fixes (Bug Fixes)
Blackjack State Machine: Fixed a soft lock that caused the game to freeze if a player entered the lobby during the betting phase and returned back.

Memory leaks and sockets: When pressing the Back button or closing the network ports window (socket.close()) they are now being released correctly.

---
