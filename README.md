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

---
 jules-achievements-system-7182464259711722883
=======


