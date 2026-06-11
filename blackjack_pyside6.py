"""
Virtual Casino — PySide6 edition.

A full port of the original Tkinter casino (Blackjack + Roulette, single-player
and LAN multiplayer) to a modern, styled Qt 6 / PySide6 interface.

The game-logic and networking layers below are GUI-agnostic and kept identical
to the original; only the presentation layer is new. All cross-thread state
updates from the networking thread are marshalled onto the GUI thread through a
QObject signal (`Bridge.state`) so widgets are only ever touched on the GUI
thread.
"""

import sys

CURRENT_LANG = "en"

TRANSLATIONS = {
    "en": {
        "Singleplayer": "Singleplayer",
        "Multiplayer": "Multiplayer",
        "Host Game": "Host Game",
        "Join Game": "Join Game",
        "LOBBY": "LOBBY",
        "SELECT A GAME": "SELECT A GAME",
        "BLACKJACK": "BLACKJACK",
        "Beat the dealer to 21": "Beat the dealer to 21",
        "ROULETTE": "ROULETTE",
        "Spin the wheel of fortune": "Spin the wheel of fortune",
        "SLOTS": "SLOTS",
        "Match three to win big": "Match three to win big",
        "POKER": "POKER",
        "Five-card draw vs bots": "Five-card draw vs bots",
        "CRASH": "CRASH",
        "Predict the rocket multiplier": "Predict the rocket multiplier",
        "WHEEL OF FORTUNE": "WHEEL OF FORTUNE",
        "Spin the money wheel": "Spin the money wheel",
        "Place Bet": "Place Bet",
        "CASH OUT": "CASH OUT",
        "Hit": "Hit",
        "Stand": "Stand",
        "Double": "Double",
        "Split": "Split",
        "Insurance": "Insurance",
        "Start New Round": "Start New Round",
        "Clear Bets": "Clear Bets",
        "Rebet": "Rebet",
        "SPIN": "SPIN",
        "Fold": "Fold",
        "Check": "Check",
        "Call": "Call",
        "Raise": "Raise",
        "Draw": "Draw",
        "Deal": "Deal",
        "Balance": "Balance",
        "Waiting for bets...": "Waiting for bets...",
        "Your Bet: 0": "Your Bet: 0",
        "Won: 0": "Won: 0",
        "History:": "History:",
        "Current Bets:": "Current Bets:",
        "Back to Lobby": "Back to Lobby",
        "Bet:": "Bet:"
    },
    "ru": {
        "Singleplayer": "Одиночная игра",
        "Multiplayer": "Мультиплеер",
        "Host Game": "Создать игру",
        "Join Game": "Присоединиться",
        "LOBBY": "ЛОББИ",
        "SELECT A GAME": "ВЫБЕРИТЕ ИГРУ",
        "BLACKJACK": "БЛЭКДЖЕК",
        "Beat the dealer to 21": "Обыграй дилера до 21",
        "ROULETTE": "РУЛЕТКА",
        "Spin the wheel of fortune": "Колесо фортуны",
        "SLOTS": "СЛОТЫ",
        "Match three to win big": "Три в ряд для победы",
        "POKER": "ПОКЕР",
        "Five-card draw vs bots": "Пятикарточный дро-покер",
        "CRASH": "КРАШ",
        "Predict the rocket multiplier": "Угадай множитель ракеты",
        "WHEEL OF FORTUNE": "КОЛЕСО ФОРТУНЫ",
        "Spin the money wheel": "Денежное колесо",
        "Place Bet": "Сделать ставку",
        "CASH OUT": "ВЫВЕСТИ",
        "Hit": "Еще",
        "Stand": "Хватит",
        "Double": "Удвоить",
        "Split": "Сплит",
        "Insurance": "Страховка",
        "Start New Round": "Новый раунд",
        "Clear Bets": "Очистить",
        "Rebet": "Повторить",
        "SPIN": "КРУТИТЬ",
        "Fold": "Пас",
        "Check": "Чек",
        "Call": "Колл",
        "Raise": "Рейз",
        "Draw": "Сброс",
        "Deal": "Сдать",
        "Balance": "Баланс",
        "Waiting for bets...": "Ожидание ставок...",
        "Your Bet: 0": "Ваша ставка: 0",
        "Won: 0": "Выигрыш: 0",
        "History:": "История:",
        "Current Bets:": "Текущие ставки:",
        "Back to Lobby": "В Лобби",
        "Bet:": "Ставка:"
    }
}

def tr(key):
    return TRANSLATIONS.get(CURRENT_LANG, {}).get(key, key)
import os
import math
import json
import uuid
import wave
import struct
import socket
import random
import tempfile
import threading
from collections import Counter

from PySide6.QtCore import (
    Qt, QObject, Signal, QTimer, QRectF, QPointF, QPoint, QUrl,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QIcon, QPixmap, QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QPushButton, QLabel,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QScrollArea,
    QMessageBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy, QSpinBox, QTextEdit,
)

try:
    from PySide6.QtMultimedia import QSoundEffect
    _HAS_AUDIO = True
except Exception:
    _HAS_AUDIO = False

HOST_PORT = 5555

# ==========================================================================
# LOGIC  (unchanged from the original game)
# ==========================================================================

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def get_value(self):
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11
        else:
            return int(self.rank)

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def to_dict(self):
        return {"suit": self.suit, "rank": self.rank}

    @staticmethod
    def from_dict(d):
        return Card(d["suit"], d["rank"])


class Deck:
    def __init__(self, num_decks=6):
        self.num_decks = num_decks
        self.cards = []
        self.build()

    def build(self):
        suits = ['♥', '♦', '♣', '♠']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.cards = [Card(s, r) for _ in range(self.num_decks) for s in suits for r in ranks]
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        if len(self.cards) < 20:
            self.build()
        return self.cards.pop()


class Hand:
    def __init__(self, bet=0):
        self.cards = []
        self.bet = bet
        self.doubled = False
        self.is_blackjack = False
        self.is_busted = False
        self.is_stand = False

    def add_card(self, card):
        self.cards.append(card)

    def get_score(self):
        score = 0
        aces = 0
        for card in self.cards:
            score += card.get_value()
            if card.rank == 'A':
                aces += 1
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

    def can_split(self):
        return len(self.cards) == 2 and self.cards[0].get_value() == self.cards[1].get_value()

    def to_dict(self):
        return {
            "cards": [c.to_dict() for c in self.cards],
            "bet": self.bet,
            "doubled": self.doubled,
            "is_blackjack": self.is_blackjack,
            "is_busted": self.is_busted,
            "is_stand": self.is_stand,
            "score": self.get_score(),
        }

    @staticmethod
    def from_dict(d):
        h = Hand(d["bet"])
        h.cards = [Card.from_dict(c) for c in d["cards"]]
        h.doubled = d["doubled"]
        h.is_blackjack = d["is_blackjack"]
        h.is_busted = d["is_busted"]
        h.is_stand = d["is_stand"]
        return h


class Player:
    def __init__(self, player_id, name="Player", balance=1000):
        self.player_id = player_id
        self.name = name
        self.balance = balance
        self.hands = []
        self.insurance_bet = 0
        self.current_hand_idx = 0
        self.state = "waiting"
        self.message = ""

    def to_dict(self):
        return {
            "player_id": self.player_id,
            "name": self.name,
            "balance": self.balance,
            "hands": [h.to_dict() for h in self.hands],
            "insurance_bet": self.insurance_bet,
            "current_hand_idx": self.current_hand_idx,
            "state": self.state,
            "message": self.message,
        }

    @staticmethod
    def from_dict(d):
        p = Player(d["player_id"], d["name"], d["balance"])
        p.hands = [Hand.from_dict(h) for h in d["hands"]]
        p.insurance_bet = d["insurance_bet"]
        p.current_hand_idx = d["current_hand_idx"]
        p.state = d["state"]
        p.message = d["message"]
        return p


class Dealer:
    def __init__(self):
        self.hand = Hand()
        self.show_hidden = False

    def to_dict(self):
        return {"hand": self.hand.to_dict(), "show_hidden": self.show_hidden}

    @staticmethod
    def from_dict(d):
        dealer = Dealer()
        dealer.hand = Hand.from_dict(d["hand"])
        dealer.show_hidden = d["show_hidden"]
        return dealer


class Game:
    def __init__(self):
        self.deck = Deck()
        self.players = {}
        self.player_order = []
        self.dealer = Dealer()
        self.state = "waiting_for_players"
        self.current_player_idx = 0

    def add_player(self, player_id, name):
        if player_id not in self.players:
            p = Player(player_id, name)
            if self.state == "betting":
                p.state = "betting"
            self.players[player_id] = p
            self.player_order.append(player_id)
            return True
        return False

    def remove_player(self, player_id):
        if player_id in self.players:
            del self.players[player_id]
            if player_id in self.player_order:
                self.player_order.remove(player_id)

            if not self.players:
                self.state = "waiting_for_players"
            elif self.state == "betting" and all(p.state in ("waiting", "finished") for p in self.players.values()):
                self.start_round()
            return True
        return False

    def start_betting_phase(self):
        if len(self.players) == 0:
            return False
        self.state = "betting"
        self.dealer.hand = Hand()
        self.dealer.show_hidden = False
        for pid, player in self.players.items():
            player.hands = []
            player.insurance_bet = 0
            player.current_hand_idx = 0
            player.message = ""
            player.state = "betting"
        return True

    def place_bet(self, player_id, amount):
        if self.state != "betting":
            return False
        player = self.players.get(player_id)
        if not player or player.state != "betting":
            return False
        if 0 < amount <= player.balance:
            player.balance -= amount
            player.hands = [Hand(bet=amount)]
            player.state = "waiting"
            if all(p.state == "waiting" or p.state == "finished" for p in self.players.values()):
                self.start_round()
            return True
        return False

    def start_round(self):
        self.state = "playing"
        for _ in range(2):
            for pid in self.player_order:
                p = self.players[pid]
                if p.hands:
                    p.hands[0].add_card(self.deck.deal())
            self.dealer.hand.add_card(self.deck.deal())
        for pid in self.player_order:
            p = self.players[pid]
            if p.hands:
                if p.hands[0].get_score() == 21:
                    p.hands[0].is_blackjack = True
                    p.state = "finished"
                else:
                    p.state = "playing"
        self.current_player_idx = 0
        self.advance_turn_if_needed()

    def advance_turn_if_needed(self):
        while self.current_player_idx < len(self.player_order):
            pid = self.player_order[self.current_player_idx]
            p = self.players[pid]
            if p.state == "playing":
                return
            self.current_player_idx += 1
        self.play_dealer_turn()

    def hit(self, player_id):
        if self.state != "playing":
            return
        if self.player_order[self.current_player_idx] != player_id:
            return
        p = self.players[player_id]
        hand = p.hands[p.current_hand_idx]
        hand.add_card(self.deck.deal())
        if hand.get_score() >= 21:
            if hand.get_score() > 21:
                hand.is_busted = True
            self.next_hand(player_id)

    def stand(self, player_id):
        if self.state != "playing":
            return
        if self.player_order[self.current_player_idx] != player_id:
            return
        p = self.players[player_id]
        hand = p.hands[p.current_hand_idx]
        hand.is_stand = True
        self.next_hand(player_id)

    def double_down(self, player_id):
        if self.state != "playing":
            return
        if self.player_order[self.current_player_idx] != player_id:
            return
        p = self.players[player_id]
        hand = p.hands[p.current_hand_idx]
        if len(hand.cards) == 2 and p.balance >= hand.bet:
            p.balance -= hand.bet
            hand.bet *= 2
            hand.doubled = True
            hand.add_card(self.deck.deal())
            if hand.get_score() > 21:
                hand.is_busted = True
            self.next_hand(player_id)

    def split(self, player_id):
        if self.state != "playing":
            return
        if self.player_order[self.current_player_idx] != player_id:
            return
        p = self.players[player_id]
        hand = p.hands[p.current_hand_idx]
        if hand.can_split() and p.balance >= hand.bet:
            p.balance -= hand.bet
            new_hand = Hand(bet=hand.bet)
            new_hand.add_card(hand.cards.pop())
            hand.add_card(self.deck.deal())
            new_hand.add_card(self.deck.deal())
            p.hands.insert(p.current_hand_idx + 1, new_hand)
            if hand.cards[0].rank == 'A':
                self.next_hand(player_id)
                self.next_hand(player_id)

    def buy_insurance(self, player_id):
        if self.state != "playing":
            return
        p = self.players.get(player_id)
        if not p or len(p.hands) != 1 or len(p.hands[0].cards) != 2:
            return
        dealer_up_card = self.dealer.hand.cards[0]
        if dealer_up_card.rank == 'A' and p.insurance_bet == 0:
            insurance_cost = p.hands[0].bet / 2
            if p.balance >= insurance_cost:
                p.balance -= insurance_cost
                p.insurance_bet = insurance_cost

    def next_hand(self, player_id):
        p = self.players[player_id]
        p.current_hand_idx += 1
        if p.current_hand_idx >= len(p.hands):
            p.state = "finished"
            self.advance_turn_if_needed()

    def play_dealer_turn(self):
        self.state = "dealer_turn"
        self.dealer.show_hidden = True
        needs_to_draw = False
        for p in self.players.values():
            for h in p.hands:
                if not h.is_busted and not h.is_blackjack:
                    needs_to_draw = True
                    break
        if needs_to_draw:
            while self.dealer.hand.get_score() < 17:
                self.dealer.hand.add_card(self.deck.deal())
        self.resolve_round()

    def resolve_round(self):
        self.state = "game_over"
        dealer_score = self.dealer.hand.get_score()
        dealer_blackjack = (dealer_score == 21 and len(self.dealer.hand.cards) == 2)
        for p in self.players.values():
            if not p.hands:
                continue
            p.message = ""
            if p.insurance_bet > 0:
                if dealer_blackjack:
                    p.balance += p.insurance_bet * 3
                    p.message += "Insurance pays 2:1! "
                else:
                    p.message += "Insurance lost. "
            for i, hand in enumerate(p.hands):
                prefix = f"Hand {i+1}: " if len(p.hands) > 1 else ""
                if hand.is_busted:
                    p.message += f"{prefix}Busted!\n"
                elif hand.is_blackjack:
                    if dealer_blackjack:
                        p.balance += hand.bet
                        p.message += f"{prefix}Push.\n"
                    else:
                        p.balance += hand.bet * 2.5
                        p.message += f"{prefix}Blackjack! (3:2).\n"
                else:
                    if dealer_blackjack:
                        p.message += f"{prefix}Dealer has Blackjack.\n"
                    elif dealer_score > 21:
                        p.balance += hand.bet * 2
                        p.message += f"{prefix}Dealer busts! Win.\n"
                    elif hand.get_score() > dealer_score:
                        p.balance += hand.bet * 2
                        p.message += f"{prefix}Win!\n"
                    elif hand.get_score() < dealer_score:
                        p.message += f"{prefix}Lose.\n"
                    else:
                        p.balance += hand.bet
                        p.message += f"{prefix}Push.\n"

    def get_state(self):
        return {
            "state": self.state,
            "dealer": self.dealer.to_dict(),
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "player_order": self.player_order,
            "current_player_id": self.player_order[self.current_player_idx] if self.current_player_idx < len(self.player_order) else None,
        }


class RouletteGame:
    def __init__(self, server):
        self.server = server
        self.bets = {}
        self.last_bets = {}   # pid -> bets from the previous round (for "rebet")
        self.last_win = {}    # pid -> winnings from the most recent spin
        self.spin_n = 0       # increments each spin (reliable new-result signal)
        self.last_result = None
        self.red_nums = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]

    def place_bet(self, pid, amount, bet_type):
        if pid not in self.server.global_players:
            return
        player_balance = self.server.global_players[pid]["balance"]
        if amount > 0 and player_balance >= amount:
            self.server.global_players[pid]["balance"] -= amount
            if pid not in self.bets:
                self.bets[pid] = []
            self.bets[pid].append({"type": bet_type, "amount": amount})

    def get_winning_multiplier(self, bet_type, number, color):
        if bet_type is None:
            return 0
        if bet_type.startswith("number_"):
            n = int(bet_type.split("_")[1])
            if n == number:
                return 36
        elif bet_type == "half_RED" and color == "red":
            return 2
        elif bet_type == "half_BLACK" and color == "black":
            return 2
        elif bet_type == "half_EVEN" and number != 0 and number % 2 == 0:
            return 2
        elif bet_type == "half_ODD" and number % 2 != 0:
            return 2
        elif bet_type == "half_1_to_18" and 1 <= number <= 18:
            return 2
        elif bet_type == "half_19_to_36" and 19 <= number <= 36:
            return 2
        elif bet_type == "dozen_1" and 1 <= number <= 12:
            return 3
        elif bet_type == "dozen_2" and 13 <= number <= 24:
            return 3
        elif bet_type == "dozen_3" and 25 <= number <= 36:
            return 3
        elif bet_type == "col_1" and number != 0 and number % 3 == 1:
            return 3
        elif bet_type == "col_2" and number != 0 and number % 3 == 2:
            return 3
        elif bet_type == "col_3" and number != 0 and number % 3 == 0:
            return 3
        return 0

    def spin(self):
        number = random.randint(0, 36)
        if number == 0:
            result_color = "green"
        elif number in self.red_nums:
            result_color = "red"
        else:
            result_color = "black"
        self.last_result = {"number": number, "color": result_color}
        winnings = {}
        for pid, player_bets in self.bets.items():
            if pid not in self.server.global_players:
                continue
            total_won = 0
            for bet in player_bets:
                multiplier = self.get_winning_multiplier(bet["type"], number, result_color)
                if multiplier > 0:
                    total_won += bet["amount"] * multiplier
            if total_won > 0:
                self.server.global_players[pid]["balance"] += total_won
            winnings[pid] = total_won
        self.last_win = winnings
        self.last_bets = {pid: list(b) for pid, b in self.bets.items()}
        self.spin_n += 1
        self.bets = {}

    def clear_bets(self, pid):
        """Refund and remove the player's not-yet-spun bets."""
        gp = self.server.global_players.get(pid)
        for bet in self.bets.get(pid, []):
            if gp:
                gp["balance"] += bet["amount"]
        self.bets.pop(pid, None)

    def rebet(self, pid):
        """Re-place the player's bets from the previous round, if affordable."""
        for bet in self.last_bets.get(pid, []):
            self.place_bet(pid, bet["amount"], bet["type"])

    def get_state(self):
        return {
            "state": "roulette",
            "last_result": self.last_result,
            "spin_n": self.spin_n,
            "last_win": dict(self.last_win),
            "active_bets": {pid: bets for pid, bets in self.bets.items()},
        }


# (symbol, hex colour, reel weight, three-of-a-kind multiplier)
SLOT_SYMBOLS = [
    ("7", "#E9C46A", 1, 50),
    ("★", "#B07CD6", 2, 20),
    ("♦", "#E5564B", 3, 10),
    ("♥", "#E5564B", 3, 8),
    ("♣", "#3FBF6B", 4, 6),
    ("♠", "#5AA6E0", 5, 4),
]
SLOT_COLOR = {ch: col for ch, col, _w, _m in SLOT_SYMBOLS}


class SlotsGame:
    """Three-reel slot machine. Each player spins their own machine; balance is
    shared with the rest of the casino via global_players."""

    def __init__(self, server):
        self.server = server
        self.last = {}   # pid -> {"reels": [c, c, c], "win": int, "bet": int}
        self._reel = []
        for ch, _col, w, _m in SLOT_SYMBOLS:
            self._reel += [ch] * w
        self._mult = {ch: m for ch, _col, _w, m in SLOT_SYMBOLS}

    def spin(self, pid, bet):
        gp = self.server.global_players.get(pid)
        if not gp:
            return
        bet = int(bet)
        if bet <= 0 or gp["balance"] < bet:
            return
        gp["balance"] -= bet
        reels = [random.choice(self._reel) for _ in range(3)]
        win = self._payout(reels, bet)
        if win > 0:
            gp["balance"] += win
        n = (self.last.get(pid) or {}).get("n", 0) + 1
        self.last[pid] = {"reels": reels, "win": win, "bet": bet, "n": n}

    def _payout(self, reels, bet):
        a, b, c = reels
        if a == b == c:
            return bet * self._mult.get(a, 5)
        if a == b or a == c or b == c:
            return bet * 2
        return 0

    def get_state(self, pid):
        return {"state": "slots", "last": self.last.get(pid)}



# ==========================================================================
# CRASH GAME
# ==========================================================================

class CrashGame:
    def __init__(self, server):
        self.server = server
        self.state = "waiting_for_bets"
        self.bets = {}        # pid -> {"amount": int, "cashed_out": bool, "won": int}
        self.crash_point = 1.0
        self.current_multiplier = 1.0
        self.ticks = 0
        self.history = []     # last 5 crash points
        self._loop_thread = None

    def place_bet(self, pid, amount):
        if self.state != "waiting_for_bets":
            return False
        gp = self.server.global_players.get(pid)
        if not gp or gp["balance"] < amount or amount <= 0:
            return False
        gp["balance"] -= amount
        self.bets[pid] = {"amount": amount, "cashed_out": False, "won": 0}

        if self._loop_thread is None or not self._loop_thread.is_alive():
            self._start_delay()

        return True

    def _start_delay(self):
        import threading
        if self._loop_thread and self._loop_thread.is_alive():
            return
        self._loop_thread = threading.Thread(target=self._flight_loop, daemon=True)
        self._loop_thread.start()

    def _flight_loop(self):
        import time, random
        time.sleep(2)
        if self.state != "waiting_for_bets":
            return

        self.state = "flying"
        e = 0.99
        u = random.random()
        if u == 0: u = 0.0001
        self.crash_point = max(1.00, e / u)
        self.current_multiplier = 1.00
        self.ticks = 0

        try: self.server.broadcast_state()
        except Exception: pass

        while self.state == "flying":
            time.sleep(0.033) # ~30 ticks per sec
            self.ticks += 1
            self.current_multiplier = 1.01 ** self.ticks

            if self.current_multiplier >= self.crash_point:
                self.trigger_crash()
                break

            if self.ticks % 3 == 0:
                try: self.server.broadcast_state()
                except Exception: pass

    def cashout(self, pid):
        if self.state != "flying":
            return False
        bet_info = self.bets.get(pid)
        if not bet_info or bet_info["cashed_out"]:
            return False

        win_amount = int(bet_info["amount"] * self.current_multiplier)
        bet_info["cashed_out"] = True
        bet_info["won"] = win_amount

        gp = self.server.global_players.get(pid)
        if gp:
            gp["balance"] += win_amount
        return True

    def trigger_crash(self):
        import time
        if self.state != "flying":
            return
        self.state = "crashed"
        self.history.insert(0, round(self.crash_point, 2))
        self.history = self.history[:5]

        try: self.server.broadcast_state()
        except Exception: pass

        time.sleep(3)
        self.reset()

    def reset(self):
        self.state = "waiting_for_bets"
        self.bets = {}
        self.crash_point = 1.0
        self.current_multiplier = 1.0
        self.ticks = 0
        try: self.server.broadcast_state()
        except Exception: pass

    def get_state(self):
        return {
            "state": self.state,
            "bets": self.bets,
            "crash_point": self.crash_point,
            "current_multiplier": self.current_multiplier,
            "history": self.history
        }

# ==========================================================================
# FIVE-CARD DRAW POKER (vs AI bots)
# ==========================================================================

RANK_ORDER = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
              '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
POKER_SUITS = ['♠', '♥', '♦', '♣']
POKER_RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
HAND_NAMES = ["High Card", "Pair", "Two Pair", "Three of a Kind", "Straight",
              "Flush", "Full House", "Four of a Kind", "Straight Flush"]


def poker_hand_rank(cards):
    """Return a comparable tuple (category, tiebreakers) for a 5-card hand;
    a larger tuple is a stronger hand."""
    vals = sorted((RANK_ORDER[c["rank"]] for c in cards), reverse=True)
    suits = [c["suit"] for c in cards]
    cnt = Counter(vals)
    by_count = sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    counts = [c for _v, c in by_count]
    ordered = [v for v, _c in by_count]
    is_flush = len(set(suits)) == 1
    distinct = sorted(set(vals), reverse=True)
    straight_high = None
    if len(distinct) == 5:
        if distinct[0] - distinct[4] == 4:
            straight_high = distinct[0]
        elif distinct == [14, 5, 4, 3, 2]:
            straight_high = 5
    if straight_high and is_flush:
        return (8, [straight_high])
    if counts[0] == 4:
        return (7, ordered)
    if counts[0] == 3 and counts[1] == 2:
        return (6, ordered)
    if is_flush:
        return (5, vals)
    if straight_high:
        return (4, [straight_high])
    if counts[0] == 3:
        return (3, ordered)
    if counts[0] == 2 and counts[1] == 2:
        return (2, ordered)
    if counts[0] == 2:
        return (1, ordered)
    return (0, vals)


def poker_rank_name(rank_tuple):
    return HAND_NAMES[rank_tuple[0]]


class PokerTable:
    """A single five-card-draw table: one human seat plus AI bots. Money for the
    human is the shared global balance; bot stacks are virtual (refreshed each
    hand so bots never run dry). Fixed-limit betting with a per-round raise cap."""

    BET_CAP = 4
    BOT_NAMES = ["Iris", "Boris", "Clara", "Dmitri"]

    def __init__(self, backend, pid, human_name, num_bots=3):
        self.backend = backend
        self.pid = pid
        self.bet_unit = 10
        self.phase = "idle"         # idle, betting1, draw, betting2, showdown, done
        self.pot = 0
        self.actor = -1
        self.raises = 0
        self.hand_no = 0
        self.message = "Press Deal to start a hand."
        self.results = None
        self.deck = []
        self.seats = [self._new_seat(human_name, False)]
        for i in range(num_bots):
            self.seats.append(self._new_seat(f"{self.BOT_NAMES[i]} 🤖", True))

    @staticmethod
    def _new_seat(name, bot):
        return {"name": name, "bot": bot, "chips": 0, "hand": [], "folded": False,
                "all_in": False, "committed_round": 0, "committed_total": 0,
                "acted": False, "drawn": False, "discards": 0}

    # -- money ---------------------------------------------------------------
    def _balance(self):
        return self.backend.global_players[self.pid]["balance"]

    def _commit(self, seat, amount):
        if seat["bot"]:
            amount = min(amount, seat["chips"])
            seat["chips"] -= amount
            if seat["chips"] <= 0:
                seat["all_in"] = True
        else:
            amount = min(amount, self._balance())
            self.backend.global_players[self.pid]["balance"] -= amount
            if self._balance() <= 0:
                seat["all_in"] = True
        seat["committed_round"] += amount
        seat["committed_total"] += amount
        self.pot += amount
        return amount

    # -- hand lifecycle ------------------------------------------------------
    def start_hand(self, bet_unit):
        if self.phase not in ("idle", "done"):
            return False   # a hand is already in progress
        self.bet_unit = max(1, int(bet_unit))
        if self._balance() < self.bet_unit:
            self.message = "Not enough balance for the ante."
            return False
        self.hand_no += 1
        self.deck = [{"suit": s, "rank": r} for s in POKER_SUITS for r in POKER_RANKS]
        random.shuffle(self.deck)
        for s in self.seats:
            if s["bot"]:
                s["chips"] = self.bet_unit * 80
            s["hand"] = []
            s["folded"] = False
            s["all_in"] = False
            s["committed_round"] = 0
            s["committed_total"] = 0
            s["acted"] = False
            s["drawn"] = False
            s["discards"] = 0
        self.pot = 0
        self.results = None
        self.message = ""
        for s in self.seats:           # ante
            self._commit(s, self.bet_unit)
        for _ in range(5):             # deal
            for s in self.seats:
                s["hand"].append(self.deck.pop())
        self.phase = "betting1"
        self._start_betting_round()
        return True

    # -- betting -------------------------------------------------------------
    def _to_call(self):
        return max((s["committed_round"] for s in self.seats if not s["folded"]), default=0)

    def _active(self):
        return [i for i, s in enumerate(self.seats) if not s["folded"]]

    def _start_betting_round(self):
        self.raises = 0
        for s in self.seats:
            s["committed_round"] = 0
            if not s["folded"] and not s["all_in"]:
                s["acted"] = False
        for i, s in enumerate(self.seats):
            if not s["folded"] and not s["all_in"]:
                self.actor = i
                return
        self._end_betting()   # everyone still in is all-in -> resolve, don't strand actor

    def _apply_bet(self, idx, action):
        seat = self.seats[idx]
        owe = self._to_call() - seat["committed_round"]
        if action == "fold":
            seat["folded"] = True
        elif action == "check":
            pass
        elif action == "call":
            self._commit(seat, owe)
        elif action == "bet":
            self._commit(seat, self.bet_unit)
            self._on_raise(idx)
        elif action == "raise":
            self._commit(seat, owe + self.bet_unit)
            self._on_raise(idx)
        seat["acted"] = True

    def _on_raise(self, idx):
        self.raises += 1
        for i, s in enumerate(self.seats):
            if i != idx and not s["folded"] and not s["all_in"]:
                s["acted"] = False

    def _betting_done(self):
        to_call = self._to_call()
        for s in self.seats:
            if s["folded"] or s["all_in"]:
                continue
            if not s["acted"] or s["committed_round"] != to_call:
                return False
        return True

    # -- draw ----------------------------------------------------------------
    def _apply_draw(self, idx, discards):
        seat = self.seats[idx]
        idxs = sorted({d for d in discards if 0 <= d < len(seat["hand"])}, reverse=True)
        for d in idxs:
            seat["hand"].pop(d)
        for _ in range(len(idxs)):
            if self.deck:
                seat["hand"].append(self.deck.pop())
        seat["drawn"] = True
        seat["discards"] = len(idxs)

    def _draw_done(self):
        return all(s["folded"] or s["drawn"] for s in self.seats)

    # -- flow ----------------------------------------------------------------
    def _after_action(self):
        active = self._active()
        if len(active) == 1:
            self._award(active, reveal=False)
            return
        if self.phase in ("betting1", "betting2"):
            if self._betting_done():
                self._end_betting()
            else:
                self._advance_betting()
        elif self.phase == "draw":
            if self._draw_done():
                self.phase = "betting2"
                self._start_betting_round()
            else:
                self._advance_draw()

    def _advance_betting(self):
        to_call = self._to_call()
        n = len(self.seats)
        for step in range(1, n + 1):
            j = (self.actor + step) % n
            s = self.seats[j]
            if s["folded"] or s["all_in"]:
                continue
            if not s["acted"] or s["committed_round"] != to_call:
                self.actor = j
                return
        self._end_betting()

    def _advance_draw(self):
        n = len(self.seats)
        for step in range(1, n + 1):
            j = (self.actor + step) % n
            s = self.seats[j]
            if not s["folded"] and not s["drawn"]:
                self.actor = j
                return
        self.phase = "betting2"
        self._start_betting_round()

    def _end_betting(self):
        if self.phase == "betting1":
            self.phase = "draw"
            for s in self.seats:
                s["drawn"] = False
            for i, s in enumerate(self.seats):
                if not s["folded"]:
                    self.actor = i
                    return
        elif self.phase == "betting2":
            self._showdown()

    def _showdown(self):
        self.phase = "showdown"
        contenders = self._active()
        ranks = {i: poker_hand_rank(self.seats[i]["hand"]) for i in contenders}
        best = max(ranks.values())
        winners = [i for i in contenders if ranks[i] == best]
        self._award(winners, reveal=True, ranks=ranks)

    def _award(self, winners, reveal, ranks=None):
        pot = self.pot
        share = pot // len(winners)
        rem = pot - share * len(winners)
        for k, i in enumerate(winners):
            amt = share + (rem if k == 0 else 0)
            if self.seats[i]["bot"]:
                self.seats[i]["chips"] += amt
            else:
                self.backend.global_players[self.pid]["balance"] += amt
        self.results = {
            "winners": winners,
            "reveal": reveal,
            "pot": pot,
            "names": {str(i): poker_rank_name(ranks[i]) for i in (ranks or {})},
        }
        if 0 in winners:
            self.message = (f"You split the ${pot} pot." if len(winners) > 1
                            else f"You win ${pot}!")
        else:
            self.message = f"{self.seats[winners[0]]['name']} wins ${pot}."
        self.phase = "done"
        self.pot = 0
        self.actor = -1

    # -- AI ------------------------------------------------------------------
    def _bot_bet(self, idx):
        seat = self.seats[idx]
        owe = self._to_call() - seat["committed_round"]
        cat = poker_hand_rank(seat["hand"])[0]
        if owe == 0:
            if cat >= 3 and self.raises < self.BET_CAP and random.random() < 0.85:
                return "bet"
            if cat >= 1 and self.raises < self.BET_CAP and random.random() < 0.30:
                return "bet"
            return "check"
        if cat >= 3:
            if self.raises < self.BET_CAP and random.random() < 0.5:
                return "raise"
            return "call"
        if cat >= 1:
            return "call" if random.random() < 0.78 else "fold"
        return "call" if random.random() < 0.18 else "fold"

    def _bot_discards(self, idx):
        hand = self.seats[idx]["hand"]
        vals = [RANK_ORDER[c["rank"]] for c in hand]
        suits = [c["suit"] for c in hand]
        if poker_hand_rank(hand)[0] >= 4:      # straight or better — stand pat
            return []
        sc = Counter(suits)
        for s, c in sc.items():                # 4-flush draw
            if c == 4:
                return [i for i in range(5) if suits[i] != s]
        vc = Counter(vals)
        keep = [i for i in range(5) if vc[vals[i]] >= 2]
        if keep:
            return [i for i in range(5) if i not in keep]
        order = sorted(range(5), key=lambda i: vals[i], reverse=True)
        keep_high = [i for i in order if vals[i] >= 11][:2] or [order[0]]
        return [i for i in range(5) if i not in keep_high]

    # -- driven by the controller -------------------------------------------
    def awaiting(self):
        if self.phase in ("idle", "done", "showdown"):
            return "done"
        if self.actor == 0 and not self.seats[0]["folded"]:
            return "draw_human" if self.phase == "draw" else "human"
        return "bot"

    def step(self):
        """Advance one bot action (paced by the GUI)."""
        if self.awaiting() != "bot":
            return
        if self.phase in ("betting1", "betting2"):
            self._apply_bet(self.actor, self._bot_bet(self.actor))
        elif self.phase == "draw":
            self._apply_draw(self.actor, self._bot_discards(self.actor))
        self._after_action()

    def act(self, action, discards=None):
        """Apply the human's action."""
        if self.actor != 0 or self.seats[0]["folded"]:
            return
        if self.phase in ("betting1", "betting2"):
            owe = self._to_call() - self.seats[0]["committed_round"]
            if action == "check" and owe > 0:
                return
            if action == "bet" and owe > 0:
                return
            if action in ("bet", "raise") and self.raises >= self.BET_CAP:
                return
            if action not in ("fold", "check", "call", "bet", "raise"):
                return
            self._apply_bet(0, action)
            self._after_action()
        elif self.phase == "draw" and not self.seats[0]["drawn"]:
            self._apply_draw(0, discards or [])
            self._after_action()

    def get_state(self):
        reveal = bool(self.results and self.results.get("reveal"))
        seats = []
        for i, s in enumerate(self.seats):
            show = (i == 0) or reveal
            seats.append({
                "name": s["name"],
                "bot": s["bot"],
                "folded": s["folded"],
                "all_in": s["all_in"],
                "chips": self._balance() if not s["bot"] else s["chips"],
                "committed_round": s["committed_round"],
                "committed_total": s["committed_total"],
                "discards": s["discards"],
                "drawn": s["drawn"],
                "hand": list(s["hand"]) if show else None,
                "card_count": len(s["hand"]),
                "is_actor": (i == self.actor),
            })
        legal = []
        owe = 0
        if self.awaiting() == "human":
            owe = self._to_call() - self.seats[0]["committed_round"]
            legal = ["fold"]
            if owe == 0:
                legal.append("check")
                if self.raises < self.BET_CAP:
                    legal.append("bet")
            else:
                legal.append("call")
                if self.raises < self.BET_CAP:
                    legal.append("raise")
        return {
            "state": "poker",
            "phase": self.phase,
            "pot": self.pot if self.phase != "done" else (self.results["pot"] if self.results else 0),
            "to_call": self._to_call(),
            "owe": owe,
            "bet_unit": self.bet_unit,
            "seats": seats,
            "actor": self.actor,
            "awaiting": self.awaiting(),
            "legal": legal,
            "message": self.message,
            "results": self.results,
            "hand_no": self.hand_no,
        }


class PokerRoom:
    """Owns one PokerTable per human player (each plays their own table vs bots)."""

    def __init__(self, server):
        self.server = server
        self.tables = {}

    def table_for(self, pid):
        if pid not in self.tables:
            name = self.server.global_players[pid]["name"]
            self.tables[pid] = PokerTable(self.server, pid, name)
        return self.tables[pid]


# ==========================================================================
# NETWORK  (unchanged from the original game)
# ==========================================================================

class Server:
    def __init__(self, host='0.0.0.0'):
        self.host = host
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, HOST_PORT))
        self.server.listen()
        self.global_players = {}
        self.blackjack_game = Game()
        self.blackjack_game.server = self
        self.roulette_game = RouletteGame(self)
        self.slots_game = SlotsGame(self)
        self.poker_room = PokerRoom(self)
        self.crash_game = CrashGame(self)
        self.clients = {}

    def start(self):
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            client, address = self.server.accept()
            threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()

    def broadcast_state(self):
        bj_state = self.blackjack_game.get_state()
        for pid in bj_state["players"]:
            if pid in self.global_players:
                bj_state["players"][pid]["balance"] = self.global_players[pid]["balance"]
        for client, pid in list(self.clients.items()):
            try:
                if pid not in self.global_players:
                    continue
                room = self.global_players[pid]["room"]
                if room == "blackjack":
                    data = json.dumps({"type": "state", "data": bj_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "roulette":
                    r_state = self.roulette_game.get_state()
                    r_state["players"] = {p_id: {"name": self.global_players[p_id]["name"], "balance": self.global_players[p_id]["balance"]} for p_id in self.global_players if self.global_players[p_id]["room"] == "roulette"}
                    data = json.dumps({"type": "state", "data": r_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "slots":
                    s_state = self.slots_game.get_state(pid)
                    s_state["players"] = {pid: {"name": self.global_players[pid]["name"], "balance": self.global_players[pid]["balance"]}}
                    data = json.dumps({"type": "state", "data": s_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "poker":
                    p_state = self.poker_room.table_for(pid).get_state()
                    p_state["players"] = {pid: {"name": self.global_players[pid]["name"], "balance": self.global_players[pid]["balance"]}}
                    data = json.dumps({"type": "state", "data": p_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "crash":
                    c_state = self.crash_game.get_state()
                    c_state["players"] = {p_id: {"name": self.global_players[p_id]["name"], "balance": self.global_players[p_id]["balance"]} for p_id in self.global_players if self.global_players[p_id]["room"] == "crash"}
                    data = json.dumps({"type": "state", "data": c_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "lobby":
                    lobby_state = {
                        "state": "lobby",
                        "players": {p_id: {"name": self.global_players[p_id]["name"], "balance": self.global_players[p_id]["balance"]} for p_id in self.global_players if self.global_players[p_id]["room"] == "lobby"},
                    }
                    data = json.dumps({"type": "state", "data": lobby_state}).encode('utf-8')
                    client.sendall(data + b"\n")
            except Exception:
                pass

    def handle_client(self, client):
        try:
            data = client.recv(1024).decode('utf-8')
            msg = json.loads(data)
            if msg["type"] == "join":
                player_id = msg["player_id"]
                name = msg["name"]
                self.clients[client] = player_id
                if player_id not in self.global_players:
                    self.global_players[player_id] = {"name": name, "balance": 1000, "room": "lobby"}
                self.global_players[player_id]["room"] = "lobby"
                self.broadcast_state()

            while True:
                data = client.recv(4096)
                if not data:
                    break
                messages = data.decode('utf-8').split('\n')
                for msg_str in messages:
                    if not msg_str:
                        continue
                    msg = json.loads(msg_str)
                    if msg["type"] == "action":
                        action = msg["action"]
                        pid = msg["player_id"]
                        if action == "join_room":
                            room_name = msg.get("room")
                            self.global_players[pid]["room"] = room_name
                            if room_name == "blackjack":
                                self.blackjack_game.add_player(pid, self.global_players[pid]["name"])
                                self.blackjack_game.players[pid].balance = self.global_players[pid]["balance"]
                        elif action == "leave_room":
                            room_name = self.global_players[pid]["room"]
                            if room_name == "blackjack":
                                self.blackjack_game.remove_player(pid)
                            self.global_players[pid]["room"] = "lobby"
                        elif action == "claim_welfare":
                            if self.global_players[pid]["balance"] <= 0:
                                self.global_players[pid]["balance"] = 1000
                                if pid in self.blackjack_game.players:
                                    self.blackjack_game.players[pid].balance = 1000
                        elif self.global_players[pid]["room"] == "blackjack":
                            if action == "bet":
                                self.blackjack_game.place_bet(pid, msg["amount"])
                                self.global_players[pid]["balance"] = self.blackjack_game.players[pid].balance
                            elif action == "hit":
                                self.blackjack_game.hit(pid)
                            elif action == "stand":
                                self.blackjack_game.stand(pid)
                            elif action == "double":
                                self.blackjack_game.double_down(pid)
                                self.global_players[pid]["balance"] = self.blackjack_game.players[pid].balance
                            elif action == "split":
                                self.blackjack_game.split(pid)
                                self.global_players[pid]["balance"] = self.blackjack_game.players[pid].balance
                            elif action == "insurance":
                                self.blackjack_game.buy_insurance(pid)
                                self.global_players[pid]["balance"] = self.blackjack_game.players[pid].balance
                            elif action == "start_round":
                                self.blackjack_game.start_betting_phase()
                        elif self.global_players[pid]["room"] == "roulette":
                            if action == "r_bet":
                                self.roulette_game.place_bet(pid, msg.get("amount", 10), msg.get("bet_type"))
                            elif action == "r_spin":
                                self.roulette_game.spin()
                            elif action == "r_clear":
                                self.roulette_game.clear_bets(pid)
                            elif action == "r_rebet":
                                self.roulette_game.rebet(pid)
                        elif self.global_players[pid]["room"] == "slots":
                            if action == "s_spin":
                                self.slots_game.spin(pid, msg.get("amount", 10))
                        elif self.global_players[pid]["room"] == "poker":
                            table = self.poker_room.table_for(pid)
                            if action == "p_deal":
                                table.start_hand(msg.get("amount", 10))
                            elif action == "p_act":
                                table.act(msg.get("poker_action"), msg.get("discards"))
                            elif action == "p_step":
                                table.step()
                        elif self.global_players[pid]["room"] == "crash":
                            if action == "c_bet":
                                self.crash_game.place_bet(pid, msg.get("amount", 10))
                            elif action == "c_start":
                                self.crash_game._start_delay()
                            elif action == "c_cashout":
                                self.crash_game.cashout(pid)
                            elif action == "c_crash":
                                self.crash_game.trigger_crash()
                            elif action == "c_reset":
                                self.crash_game.reset()
                        self.broadcast_state()
        except Exception as e:
            print("Server error:", e)
        finally:
            if client in self.clients:
                pid = self.clients[client]
                if pid in self.global_players:
                    if self.global_players[pid]["room"] == "blackjack":
                        self.blackjack_game.remove_player(pid)
                    self.global_players[pid]["room"] = "disconnected"
                del self.clients[client]
                self.broadcast_state()
            client.close()


class Client:
    def __init__(self, host, player_id, name):
        self.host = host
        self.port = HOST_PORT
        self.player_id = player_id
        self.name = name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.on_state_update = None

    def connect(self):
        # Bound timeout so an unreachable host fails fast instead of freezing
        # the GUI thread; restore blocking mode for the steady-state recv loop.
        self.socket.settimeout(5)
        self.socket.connect((self.host, self.port))
        self.socket.settimeout(None)
        join_msg = json.dumps({"type": "join", "player_id": self.player_id, "name": self.name})
        self.socket.sendall(join_msg.encode('utf-8'))
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def receive_messages(self):
        buffer = ""
        while True:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    if msg["type"] == "state" and self.on_state_update:
                        self.on_state_update(msg["data"])
            except Exception:
                break

    def send_action(self, action, **kwargs):
        msg = {"type": "action", "player_id": self.player_id, "action": action}
        msg.update(kwargs)
        try:
            self.socket.sendall((json.dumps(msg) + "\n").encode('utf-8'))
        except Exception:
            pass


class _LocalBackend:
    """In-process stand-in for Server used by single-player.

    Holds exactly the state the game logic reads (global_players, the two game
    objects) but opens no socket and starts no threads — so single-player never
    binds a network port and cannot fail because the port is already in use.
    """

    def __init__(self):
        self.global_players = {}
        self.blackjack_game = Game()
        self.blackjack_game.server = self
        self.roulette_game = RouletteGame(self)
        self.slots_game = SlotsGame(self)
        self.poker_room = PokerRoom(self)
        self.crash_game = CrashGame(self)
        self.clients = {}


class LocalClient:
    def __init__(self, player_id, name):
        self.player_id = player_id
        self.name = name
        self.server = _LocalBackend()
        self.on_state_update = None
        self.room = "lobby"
        self.server.global_players[player_id] = {"name": name, "balance": 1000, "room": "lobby"}
        self.server.clients["local_socket_mock"] = player_id
        self.server.broadcast_state = self._trigger_update

    def connect(self):
        self._trigger_update()

    def _trigger_update(self):
        if not self.on_state_update:
            return
        if self.room == "lobby":
            state = {
                "state": "lobby",
                "players": {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}},
            }
        elif self.room == "blackjack":
            state = self.server.blackjack_game.get_state()
            state["players"][self.player_id]["balance"] = self.server.global_players[self.player_id]["balance"]
        elif self.room == "roulette":
            state = self.server.roulette_game.get_state()
            state["players"] = {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}}
        elif self.room == "slots":
            state = self.server.slots_game.get_state(self.player_id)
            state["players"] = {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}}
        elif self.room == "poker":
            state = self.server.poker_room.table_for(self.player_id).get_state()
            state["players"] = {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}}
        elif self.room == "crash":
            state = self.server.crash_game.get_state()
            state["players"] = {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}}
        self.on_state_update(state)

    def send_action(self, action, **kwargs):
        pid = self.player_id
        if action == "join_room":
            self.room = kwargs.get("room")
            self.server.global_players[pid]["room"] = self.room
            if self.room == "blackjack":
                self.server.blackjack_game.add_player(pid, self.name)
                self.server.blackjack_game.players[pid].balance = self.server.global_players[pid]["balance"]
        elif action == "leave_room":
            if self.room == "blackjack":
                self.server.blackjack_game.remove_player(pid)
            self.room = "lobby"
            self.server.global_players[pid]["room"] = "lobby"
        elif action == "claim_welfare":
            if self.server.global_players[pid]["balance"] <= 0:
                self.server.global_players[pid]["balance"] = 1000
                if pid in self.server.blackjack_game.players:
                    self.server.blackjack_game.players[pid].balance = 1000
        elif self.room == "blackjack":
            game = self.server.blackjack_game
            if action == "bet":
                game.place_bet(pid, kwargs.get("amount", 0))
            elif action == "hit":
                game.hit(pid)
            elif action == "stand":
                game.stand(pid)
            elif action == "double":
                game.double_down(pid)
            elif action == "split":
                game.split(pid)
            elif action == "insurance":
                game.buy_insurance(pid)
            elif action == "start_round":
                game.start_betting_phase()
            for p in game.players.values():
                self.server.global_players[p.player_id]["balance"] = p.balance
        elif self.room == "roulette":
            game = self.server.roulette_game
            if action == "r_bet":
                game.place_bet(pid, int(kwargs.get("amount", 10)), kwargs.get("bet_type"))
            elif action == "r_spin":
                game.spin()
            elif action == "r_clear":
                game.clear_bets(pid)
            elif action == "r_rebet":
                game.rebet(pid)
        elif self.room == "slots":
            if action == "s_spin":
                self.server.slots_game.spin(pid, int(kwargs.get("amount", 10)))
        elif self.room == "poker":
            table = self.server.poker_room.table_for(pid)
            if action == "p_deal":
                table.start_hand(int(kwargs.get("amount", 10)))
            elif action == "p_act":
                table.act(kwargs.get("poker_action"), kwargs.get("discards"))
            elif action == "p_step":
                table.step()
        elif self.room == "crash":
            game = self.server.crash_game
            if action == "c_bet":
                game.place_bet(pid, kwargs.get("amount", 10))
            elif action == "c_cashout":
                game.cashout(pid)
        self._trigger_update()



class ProfileManager:
    def __init__(self, filepath="casino_save.json"):
        self.filepath = filepath
        self.name = "Player"
        self.balance = 1000
        self.welfare_claimed = False
        self.achievements = {
            "high_roller": False,
            "jackpot_king": False,
            "poker_shark": False,
            "zero_hero": False,
            "natural_21": False,
            "phoenix": False
        }
        self.stats = {
            "bj_played": 0, "bj_wins": 0,
            "roulette_played": 0, "roulette_wins": 0,
            "slots_played": 0, "slots_wins": 0,
            "poker_played": 0, "poker_wins": 0,
            "crash_played": 0, "crash_wins": 0,
            "biggest_win": 0,
            "total_wagered": 0,
            "welfare_count": 0
        }
        self.load()

    def load(self):
        import json, os
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                    self.name = data.get("name", self.name)
                    self.balance = data.get("balance", self.balance)
                    self.welfare_claimed = data.get("welfare_claimed", self.welfare_claimed)
                    loaded_ach = data.get("achievements", {})
                    for k in self.achievements:
                        self.achievements[k] = loaded_ach.get(k, False)
                    loaded_stats = data.get("stats", {})
                    for k in self.stats:
                        self.stats[k] = loaded_stats.get(k, 0)
            except Exception as e:
                print(f"Failed to load profile: {e}")

    def save(self):
        import json
        data = {
            "name": self.name,
            "balance": self.balance,
            "welfare_claimed": self.welfare_claimed,
            "achievements": self.achievements,
            "stats": self.stats
        }
        try:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Failed to save profile: {e}")

    def unlock(self, key, app):
        if key in self.achievements and not self.achievements[key]:
            self.achievements[key] = True
            self.save()
            # Show a global UI flourish via the main app
            if app:
                app.show_achievement_notification(key)

# ==========================================================================
# GUI  (new — PySide6 / Qt 6)

# ==========================================================================

# Standard European wheel order and red pockets.
WHEEL_NUMS = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8,
              23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
              35, 3, 26]
RED_NUMS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

GOLD = "#E9C46A"

STYLESHEET = """
* { font-family: 'Segoe UI', 'Arial'; }
QWidget { color: #E8E8EA; }
QMainWindow, #root { background-color: #0C0F14; }

QLabel#brand     { color: #E9C46A; font-size: 34px; font-weight: 800; letter-spacing: 3px; }
QLabel#subtitle  { color: #8A909A; font-size: 14px; letter-spacing: 3px; }
QLabel#sectionTitle { color: #F4F4F5; font-size: 28px; font-weight: 700; letter-spacing: 1px; }
QLabel#balance   { color: #E9C46A; font-size: 18px; font-weight: 800; }
QLabel#status    { color: #99A0AA; font-size: 14px; }
QLabel#fieldLbl  { color: #B9BFC8; font-size: 13px; letter-spacing: 1px; }
QLabel#result    { color: #FFFFFF; font-size: 15px; font-weight: 700; }
QLabel#advisor   { color: #E9C46A; font-size: 13px; font-weight: 700; }

QFrame#topbar { background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.06); }
QFrame#panel  { background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.07); border-radius: 18px; }
QFrame#felt   { background: qradialgradient(cx:0.5, cy:0.32, radius:0.95,
                stop:0 #1C7E4E, stop:0.7 #0F5A33, stop:1 #0A3D22);
                border: 2px solid rgba(233,196,106,0.45); border-radius: 22px; }
QFrame#seat   { background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.07); border-radius: 16px; }
QFrame#seatCurrent { background: rgba(233,196,106,0.10); border: 2px solid #E9C46A; border-radius: 16px; }
QLabel#seatName { font-size: 16px; font-weight: 800; color: #FFFFFF; }
QLabel#seatBal  { font-size: 13px; color: #E9C46A; font-weight: 700; }
QLabel#handInfo { font-size: 12px; color: #D7DBE0; }

QLineEdit { background: #161A21; border: 1px solid rgba(255,255,255,0.12);
            border-radius: 10px; padding: 11px 13px; color: #fff; font-size: 15px;
            selection-background-color: #D4AF37; }
QLineEdit:focus { border: 1px solid #E9C46A; }

QPushButton { border: none; border-radius: 12px; padding: 12px 22px;
              font-size: 15px; font-weight: 700; color: #fff; }
QPushButton[variant="gold"]     { color:#1c1606; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #F2D277, stop:1 #CFA02A); }
QPushButton[variant="gold"]:hover    { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FFE091, stop:1 #E0B43C); }
QPushButton[variant="gold"]:pressed  { background: #B8932E; }
QPushButton[variant="charcoal"] { background: #20242C; border:1px solid rgba(255,255,255,0.06); }
QPushButton[variant="charcoal"]:hover   { background: #2E3440; }
QPushButton[variant="charcoal"]:pressed { background: #15181E; }
QPushButton[variant="crimson"]  { background: #8B2500; }
QPushButton[variant="crimson"]:hover    { background: #A62C00; }
QPushButton[variant="crimson"]:pressed  { background: #6E1D00; }
QPushButton[variant]:disabled, QPushButton:disabled {
    background: rgba(0, 0, 0, 0.4);
    color: rgba(255, 255, 255, 0.15);
    border: 1px dashed rgba(255, 255, 255, 0.1);
}

QScrollArea { border: none; background: transparent; }
QScrollBar:horizontal { height: 10px; background: transparent; margin: 0; }
QScrollBar:vertical   { width: 10px; background: transparent; margin: 0; }
QScrollBar::handle { background: rgba(255,255,255,0.18); border-radius: 5px; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }

QLabel#dealerSpeech { color: #E9C46A; font-size: 15px; font-style: italic; font-weight: 600; }
QLabel#avatar { background: #E9C46A; color: #1c1606; font-size: 14px; font-weight: 800; border-radius: 14px; }
QFrame#nameBadgeNormal { background: rgba(255,255,255,0.06); border-radius: 14px; border: 1px solid rgba(255,255,255,0.1); }
QFrame#nameBadgeActive { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #F2D277, stop:1 #CFA02A); border-radius: 14px; border: 1px solid #FFD700; }
QLabel#badgeTextNormal { color: #fff; font-size: 13px; font-weight: 800; background: transparent; }
QLabel#badgeTextActive { color: #1c1606; font-size: 13px; font-weight: 800; background: transparent; }

QLabel#dealerSpeech { color: #E9C46A; font-size: 15px; font-style: italic; font-weight: 600; }
"""


def shadow(widget, blur=28, dy=6, color=QColor(0, 0, 0, 160)):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(color)
    widget.setGraphicsEffect(eff)
    return widget


_APP_ICON = None


def make_app_icon():
    """Paint the application/window icon at runtime — a gold casino chip bearing
    a spade, on a dark rounded tile. Cached so it is built only once."""
    global _APP_ICON
    if _APP_ICON is not None:
        return _APP_ICON

    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    # rounded dark tile
    tile = QRectF(8, 8, 240, 240)
    path = QPainterPath()
    path.addRoundedRect(tile, 54, 54)
    g = QLinearGradient(0, 0, 0, 256)
    g.setColorAt(0, QColor("#1B2233"))
    g.setColorAt(1, QColor("#0B0E14"))
    p.fillPath(path, QBrush(g))
    p.setPen(QPen(QColor("#D4AF37"), 4))
    p.drawPath(path)

    cx, cy, r = 128, 130, 86
    # chip edge notches (drawn under the body so they peek out as a ridged rim)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#E9C46A")))
    for i in range(12):
        a = math.radians(i * 30)
        p.drawEllipse(QPointF(cx + r * math.cos(a), cy - r * math.sin(a)), 12, 12)
    # green chip body with gold rim
    p.setBrush(QBrush(QColor("#0E8A3E")))
    p.setPen(QPen(QColor("#E9C46A"), 8))
    p.drawEllipse(QPointF(cx, cy), r, r)
    # inner disc
    p.setBrush(QBrush(QColor("#0B0E14")))
    p.setPen(QPen(QColor("#E9C46A"), 4))
    p.drawEllipse(QPointF(cx, cy), r * 0.62, r * 0.62)
    # gold spade
    p.setPen(QColor("#E9C46A"))
    p.setFont(QFont("Segoe UI", 64, QFont.Bold))
    p.drawText(QRectF(0, cy - r, 256, 2 * r), Qt.AlignCenter, "♠")
    p.end()

    _APP_ICON = QIcon(pm)
    return _APP_ICON


def enable_dark_titlebar(win):
    """Switch the native Windows title bar to dark mode so it matches the app.
    No-op on non-Windows or unsupported builds."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes, byref, sizeof, c_int
        hwnd = wintypes.HWND(int(win.winId()))
        val = c_int(1)
        dwm = ctypes.windll.dwmapi
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (Win10 20H1+/Win11); 19 on older builds
        if dwm.DwmSetWindowAttribute(hwnd, 20, byref(val), sizeof(val)) != 0:
            dwm.DwmSetWindowAttribute(hwnd, 19, byref(val), sizeof(val))
    except Exception:
        pass


def relaunch_without_console():
    """On Windows, re-spawn this script under pythonw.exe so no black console
    window appears, then signal the current (console) process to exit. Returns
    True if a windowless child was started. Safe no-op if already windowless,
    if pythonw.exe is missing, or on non-Windows."""
    if sys.platform != "win32" or os.environ.get("CASINO_CHILD") == "1":
        return False
    exe = sys.executable or ""
    if exe.lower().endswith("pythonw.exe"):
        return False
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if not os.path.exists(pythonw):
        return False
    try:
        import subprocess
        env = dict(os.environ)
        env["CASINO_CHILD"] = "1"
        subprocess.Popen(
            [pythonw, os.path.abspath(__file__)] + sys.argv[1:],
            env=env, creationflags=0x08000000)   # CREATE_NO_WINDOW
        return True
    except Exception:
        return False


class SoundManager:
    """Tiny procedural SFX engine: synthesises short WAV blips at startup (no
    external asset files) and plays them through QSoundEffect. Fully optional —
    if QtMultimedia is unavailable, every call is a harmless no-op."""

    RATE = 44100
    # name -> list of (frequency_hz, duration_s, amplitude) segments
    DEFS = {
        "deal":    [(430, 0.05, 0.45), (300, 0.05, 0.35)],
        "chip":    [(1700, 0.03, 0.5), (2100, 0.04, 0.4)],
        "spin":    [(1500, 0.02, 0.5)],
        "reel":    [(1200, 0.02, 0.45)],
        "win":     [(523, 0.09, 0.5), (659, 0.09, 0.5), (784, 0.13, 0.55)],
        "lose":    [(360, 0.13, 0.4), (260, 0.18, 0.4)],
        "jackpot": [(523, 0.08, 0.5), (659, 0.08, 0.5), (784, 0.08, 0.5),
                    (1047, 0.22, 0.6)],
        "click":   [(900, 0.02, 0.35)],
    }

    def __init__(self):
        self.enabled = True
        self._effects = {}
        self._dir = os.path.join(tempfile.gettempdir(), "virtual_casino_sfx")
        if not _HAS_AUDIO:
            return
        try:
            os.makedirs(self._dir, exist_ok=True)
        except Exception:
            return
        for name, segs in self.DEFS.items():
            try:
                path = os.path.join(self._dir, name + ".wav")
                if not os.path.exists(path):
                    self._render(path, segs)
                eff = QSoundEffect()
                eff.setSource(QUrl.fromLocalFile(path))
                eff.setVolume(0.55)
                self._effects[name] = eff
            except Exception:
                pass

    def _render(self, path, segs):
        frames = bytearray()
        for freq, dur, amp in segs:
            n = int(self.RATE * dur)
            for i in range(n):
                t = i / self.RATE
                env = min(1.0, t / 0.005) * math.exp(-4.5 * t / dur)
                val = amp * env * math.sin(2 * math.pi * freq * t)
                frames += struct.pack("<h", int(max(-1.0, min(1.0, val)) * 32767))
        with wave.open(path, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.RATE)
            w.writeframes(bytes(frames))

    def play(self, name):
        if not self.enabled:
            return
        eff = self._effects.get(name)
        if eff is not None:
            try:
                eff.play()
            except Exception:
                pass


def make_button(text, variant="charcoal", on_click=None, big=False):
    b = QPushButton(text)
    b.setProperty("variant", variant)
    b.setCursor(Qt.PointingHandCursor)
    if big:
        b.setMinimumHeight(54)
        f = b.font()
        f.setPointSize(13)
        b.setFont(f)
    if on_click:
        b.clicked.connect(lambda _=False: on_click())
    return b


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub is not None:
                clear_layout(sub)


def fade_in(widget, ms=220):
    """Fade a freshly-added widget in (used for newly dealt cards)."""
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QPropertyAnimation.DeleteWhenStopped)


def fly_chip(parent, start, end, color, text, on_done=None):
    """Animate a small chip flying from `start` to `end` (both QPoint, parent
    coords), then delete it. Used for the bet-placing flourish."""
    chip = QLabel(str(text), parent)
    chip.setAlignment(Qt.AlignCenter)
    chip.setFixedSize(38, 38)
    tc = "#1a1a1a" if color in ("#ECECEC", "#D4AF37", "#E9C46A") else "#ffffff"
    chip.setStyleSheet(
        f"background:{color}; color:{tc}; border:2px solid rgba(255,255,255,0.75);"
        f"border-radius:19px; font-weight:800; font-size:11px;")
    chip.move(start)
    chip.show()
    chip.raise_()
    anim = QPropertyAnimation(chip, b"pos", chip)
    anim.setDuration(340)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.OutCubic)

    def _fin():
        chip.deleteLater()
        if on_done:
            on_done()

    anim.finished.connect(_fin)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return chip


def show_celebration(parent, text, color=GOLD):
    """Big centred gold text that rises and fades — shown on a win/blackjack."""
    lbl = QLabel(text, parent)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"color:{color}; font-size:44px; font-weight:800; "
                      f"background:transparent; letter-spacing:2px;")
    eff = QGraphicsOpacityEffect(lbl)
    lbl.setGraphicsEffect(eff)
    y0 = parent.height() // 2 - 70
    lbl.resize(parent.width(), 120)
    lbl.move(0, y0)
    lbl.show()
    lbl.raise_()
    a_op = QPropertyAnimation(eff, b"opacity", lbl)
    a_op.setDuration(1500)
    a_op.setKeyValueAt(0.0, 1.0)
    a_op.setKeyValueAt(0.5, 1.0)
    a_op.setKeyValueAt(1.0, 0.0)
    a_pos = QPropertyAnimation(lbl, b"pos", lbl)
    a_pos.setDuration(1500)
    a_pos.setStartValue(QPoint(0, y0))
    a_pos.setEndValue(QPoint(0, y0 - 42))
    a_pos.setEasingCurve(QEasingCurve.OutCubic)
    a_op.finished.connect(lbl.deleteLater)
    a_op.start(QPropertyAnimation.DeleteWhenStopped)
    a_pos.start(QPropertyAnimation.DeleteWhenStopped)


def sound_toggle_button(app):
    """A small mute/unmute toggle for the top bars."""
    b = QPushButton()
    b.setProperty("variant", "charcoal")
    b.setCursor(Qt.PointingHandCursor)

    def refresh():
        b.setText("♪  Sound On" if app.sound.enabled else "♪  Muted")

    def toggle():
        app.sound.enabled = not app.sound.enabled
        if app.sound.enabled:
            app.sound.play("click")
        refresh()

    b.clicked.connect(lambda _=False: toggle())
    refresh()
    return b


# --------------------------------------------------------------------------
# Custom painted widgets
# --------------------------------------------------------------------------

class CardWidget(QFrame):
    """A single playing card (or a face-down back)."""

    def __init__(self, card=None, hidden=False):
        super().__init__()
        self.card = card
        self.hidden = hidden
        self.setFixedSize(74, 106)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.width() / 74.0, self.height() / 106.0)
        rect = QRectF(1, 1, 74 - 2, 106 - 2)
        path = QPainterPath()
        path.addRoundedRect(rect, 11, 11)

        if self.hidden or self.card is None:
            grad = QLinearGradient(0, 0, 0, 106)
            grad.setColorAt(0, QColor("#2C4B8F"))
            grad.setColorAt(1, QColor("#0C1A3C"))
            p.fillPath(path, QBrush(grad))
            p.setPen(QPen(QColor(GOLD), 2))
            p.drawPath(path)
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            for i in range(-106, 74, 11):
                p.drawLine(i, 0, i + 106, 106)
            p.setPen(QPen(QColor(GOLD), 2))
            p.drawEllipse(QPointF(74 / 2, 106 / 2), 16, 24)
            return

        p.fillPath(path, QBrush(QColor("#FCFCF8")))
        p.setPen(QPen(QColor("#C7C7BE"), 1))
        p.drawPath(path)

        suit = self.card["suit"]
        rank = self.card["rank"]
        col = QColor("#C81E2E") if suit in ('♥', '♦') else QColor("#16181C")
        p.setPen(col)

        rank_font = QFont("Segoe UI", 13, QFont.Bold)
        suit_font = QFont("Segoe UI", 12)
        p.setFont(rank_font)
        p.drawText(QRectF(7, 5, 34, 22), Qt.AlignLeft | Qt.AlignVCenter, rank)
        p.setFont(suit_font)
        p.drawText(QRectF(8, 26, 34, 20), Qt.AlignLeft | Qt.AlignVCenter, suit)
        p.setFont(QFont("Segoe UI", 30))
        p.drawText(rect, Qt.AlignCenter, suit)

        p.save()
        p.translate(74, 106)
        p.rotate(180)
        p.setPen(col)
        p.setFont(rank_font)
        p.drawText(QRectF(7, 5, 34, 22), Qt.AlignLeft | Qt.AlignVCenter, rank)
        p.setFont(suit_font)
        p.drawText(QRectF(8, 26, 34, 20), Qt.AlignLeft | Qt.AlignVCenter, suit)
        p.restore()


class RouletteWheel(QWidget):
    """Painted wheel with an animated ball that settles on the winning pocket."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ball_angle = 90.0
        self.spinning = False
        self.on_spin_end = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._frame = 0
        self._frames = 75
        self._start = 90.0
        self._sweep = 0.0

    def spin_to(self, number):
        if number not in WHEEL_NUMS:
            return
        step = 360.0 / len(WHEEL_NUMS)
        target_idx = WHEEL_NUMS.index(number)
        target_deg = target_idx * step + step / 2.0
        self._start = self.ball_angle % 360.0
        delta = (target_deg - self._start) % 360.0
        self._sweep = 360.0 * 4 + delta
        self._frame = 0
        self.spinning = True
        self._timer.start(16)

    def _tick(self):
        self._frame += 1
        t = self._frame / self._frames
        if t >= 1.0:
            self.ball_angle = (self._start + self._sweep) % 360.0
            self.spinning = False
            self._timer.stop()
            self.update()
            if self.on_spin_end:
                self.on_spin_end()
            return
        ease = 1 - (1 - t) ** 3
        self.ball_angle = self._start + self._sweep * ease
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2
        r_out = side / 2 - 6
        r_in = r_out * 0.62
        r_txt = (r_out + r_in) / 2
        r_ball = r_out * 0.78
        step = 360.0 / len(WHEEL_NUMS)

        # outer gold rim
        p.setBrush(QBrush(QColor("#3A2A12")))
        p.setPen(QPen(QColor("#B8860B"), 8))
        p.drawEllipse(QPointF(cx, cy), r_out, r_out)

        rect = QRectF(cx - r_out, cy - r_out, 2 * r_out, 2 * r_out)
        for i, num in enumerate(WHEEL_NUMS):
            if num == 0:
                color = QColor("#0E8A3E")
            elif num in RED_NUMS:
                color = QColor("#C42030")
            else:
                color = QColor("#1A1A1A")
            p.setBrush(QBrush(color))
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.drawPie(rect, int(i * step * 16), int(step * 16))
            mid = math.radians(i * step + step / 2)
            tx = cx + r_txt * math.cos(mid)
            ty = cy - r_txt * math.sin(mid)
            p.setPen(QColor("white"))
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            p.drawText(QRectF(tx - 12, ty - 9, 24, 18), Qt.AlignCenter, str(num))

        # inner hub
        hub = QRadialGradient(QPointF(cx, cy), r_in)
        hub.setColorAt(0, QColor("#2A2A2A"))
        hub.setColorAt(1, QColor("#101010"))
        p.setBrush(QBrush(hub))
        p.setPen(QPen(QColor("#B8860B"), 4))
        p.drawEllipse(QPointF(cx, cy), r_in, r_in)
        p.setPen(QColor(GOLD))
        p.setFont(QFont("Segoe UI", 15, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, "ROULETTE")

        # ball
        rad = math.radians(self.ball_angle)
        bx = cx + r_ball * math.cos(rad)
        by = cy - r_ball * math.sin(rad)
        p.setBrush(QBrush(QColor("#F8F8F8")))
        p.setPen(QPen(QColor("#202020"), 1))
        p.drawEllipse(QPointF(bx, by), 8, 8)


class ChipBar(QWidget):
    """A horizontal selector of casino chips; highlights the active denomination."""

    DENOMS = [1, 5, 10, 25, 100, 500, 1000, 5000, 10000]
    COLORS = {1: "#ECECEC", 5: "#D2392F", 10: "#2E6BD6", 25: "#2E9E5B",
              100: "#22272E", 500: "#7A3FB0", 1000: "#16A5BC", 5000: "#D74CC0",
              10000: "#D4AF37"}

    def __init__(self, app, on_pick=None):
        super().__init__()
        self.app = app
        self.on_pick = on_pick
        self._balance = 1000
        self.row = QHBoxLayout(self)
        self.row.setSpacing(10)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.refresh(1000)

    def refresh(self, balance):
        self._balance = balance
        if self.app.active_chip > balance and self.app.active_chip != 1:
            self.app.active_chip = 1
        clear_layout(self.row)
        for d in self.DENOMS:
            if d > balance and d != 1:
                continue
            self.row.addWidget(self._chip(d))
        self.row.addStretch(1)

    @staticmethod
    def _fmt(d):
        return str(d) if d < 1000 else f"{d // 1000}K"

    def _chip(self, d):
        active = (d == self.app.active_chip)
        b = QPushButton(self._fmt(d))
        b.setFixedSize(56, 56)
        b.setCursor(Qt.PointingHandCursor)
        color = self.COLORS[d]
        tc = "#1a1a1a" if d in (1, 10000) else "#ffffff"
        ring = "#FFFFFF" if active else "transparent"
        bw = 3 if active else 2
        scale = "transform: scale(1.1);" if active else ""
        opacity = "1.0" if active else "0.4"

        # We simulate opacity using rgba for the background color, but since we have hex colors,
        # standard pyqt stylesheet doesn't support generic opacity easily on QPushButton unless it's an effect.
        # Alternatively, QGraphicsOpacityEffect can be used, but since we are modifying stylesheets:
        if not active:
            # simple trick: just dim the text and border, since hex to rgba is complex without a helper.
            # let's just use standard Qt properties if needed, but for now we'll stick to a simpler dimming
            # if we can't reliably do 0.4 opacity on hex strings inside a pure string replacement.
            pass

        b.setStyleSheet(
            f"QPushButton{{background:{color};color:{tc};border:{bw}px solid {ring};"
            f"border-radius:28px;font-weight:800;font-size:14px;padding:0;}}"
            f"QPushButton:hover{{border:3px solid #FFFFFF;}}"
        )

        if not active:
            from PySide6.QtWidgets import QGraphicsOpacityEffect
            eff = QGraphicsOpacityEffect()
            eff.setOpacity(0.4)
            b.setGraphicsEffect(eff)
        b.clicked.connect(lambda _=False, den=d: self._pick(den))
        return b

    def _pick(self, d):
        self.app.active_chip = d
        self.refresh(self._balance)
        if self.on_pick:
            self.on_pick(d)


class ClickableTile(QFrame):
    """A large clickable game-selection tile with a title and a subtitle."""

    def __init__(self, title, subtitle, base, top, top_hover, on_click):
        super().__init__()
        self.on_click = on_click
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(290, 200)
        self.setStyleSheet(
            f"#tile{{border-radius:20px;"
            f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:1 {base});}}"
            f"#tile:hover{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top_hover},stop:1 {top});}}"
        )
        shadow(self, blur=34, dy=10)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignCenter)
        v.setSpacing(12)
        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("background:transparent;color:#fff;font-size:26px;font-weight:800;letter-spacing:2px;")
        s = QLabel(subtitle)
        s.setAlignment(Qt.AlignCenter)
        s.setWordWrap(True)
        s.setStyleSheet("background:transparent;color:rgba(255,255,255,0.85);font-size:13px;")
        v.addWidget(t)
        v.addWidget(s)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click:
            self.on_click()


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------

class StartScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("panel")
        card.setMaximumWidth(480)
        shadow(card, blur=40, dy=10)
        v = QVBoxLayout(card)
        v.setContentsMargins(40, 36, 40, 40)
        v.setSpacing(14)

        brand = QLabel("VIRTUAL CASINO")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        sub = QLabel("BLACKJACK   •   ROULETTE")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignCenter)
        v.addWidget(brand)
        v.addWidget(sub)
        v.addSpacing(20)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Player Name")
        self.name_edit.setText(app.profile.name)
        v.addWidget(self.name_edit)

        v.addWidget(make_button(tr("Singleplayer"), "gold", self._single, big=True))
        v.addSpacing(16)

        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("IP Address (for multiplayer)")
        v.addWidget(self.ip_edit)

        v.addWidget(make_button(tr("Host Game"), "charcoal", self._host, big=True))
        v.addWidget(make_button(tr("Join Game"), "charcoal", self._join, big=True))

        lang_layout = QHBoxLayout()
        en_btn = QPushButton("🇬🇧 EN")
        en_btn.setFixedSize(60, 30)
        en_btn.setStyleSheet("color: white; background: #222; border-radius: 5px;")
        en_btn.clicked.connect(lambda: self.app.set_language("en"))

        ru_btn = QPushButton("🇷🇺 RU")
        ru_btn.setFixedSize(60, 30)
        ru_btn.setStyleSheet("color: white; background: #222; border-radius: 5px;")
        ru_btn.clicked.connect(lambda: self.app.set_language("ru"))

        lang_layout.addWidget(en_btn)
        lang_layout.addWidget(ru_btn)
        v.addLayout(lang_layout)

        root.addWidget(card)

    def _single(self):
        self.app.start_singleplayer(self.name_edit.text().strip() or "Player")

    def _host(self):
        self.app.host_game(self.name_edit.text().strip() or "Player")

    def _join(self):
        self.app.join_game(self.name_edit.text().strip() or "Player", self.ip_edit.text().strip())



# ==========================================================================
# CRASH SCREEN
# ==========================================================================


class CrashGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.multiplier = 1.0
        self.status = "waiting_for_bets"

    def update_state(self, mult, status):
        self.multiplier = mult
        self.status = status
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Draw background grid
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        for i in range(1, 5):
            p.drawLine(0, h * i // 5, w, h * i // 5)
            p.drawLine(w * i // 5, 0, w * i // 5, h)

        # Draw curve
        path = QPainterPath()
        path.moveTo(0, h)

        # Calculate curve endpoint based on multiplier
        # Max out visually at around 10x for the curve mapping
        progress = min(1.0, (self.multiplier - 1.0) / 9.0)
        end_x = w * (0.2 + 0.8 * progress)
        end_y = h * (1.0 - progress)

        # Control points for a rocket curve
        ctrl1_x = end_x * 0.5
        ctrl1_y = h
        ctrl2_x = end_x * 0.8
        ctrl2_y = end_y * 1.2

        path.cubicTo(ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, end_x, end_y)

        # Fill area under curve
        fill_path = QPainterPath(path)
        fill_path.lineTo(end_x, h)
        fill_path.lineTo(0, h)

        if self.status == "crashed":
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(231, 76, 60, 100))
            grad.setColorAt(1, QColor(231, 76, 60, 10))
            p.fillPath(fill_path, QBrush(grad))
            p.setPen(QPen(QColor("#E74C3C"), 3))
        else:
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(46, 204, 113, 100))
            grad.setColorAt(1, QColor(46, 204, 113, 10))
            p.fillPath(fill_path, QBrush(grad))
            p.setPen(QPen(QColor("#2ECC71"), 3))

        if self.status != "waiting_for_bets":
            p.drawPath(path)

            # Draw rocket/dot at end
            p.setBrush(QColor("#fff"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(end_x, end_y), 5, 5)

        # Draw Multiplier Text
        p.setPen(QColor("#E74C3C") if self.status == "crashed" else QColor("#2ECC71"))
        font = QFont("Arial", 48, QFont.Bold)
        p.setFont(font)
        text = f"{self.multiplier:.2f}x"
        if self.status == "waiting_for_bets": text = "1.00x"

        metrics = p.fontMetrics()
        tx, ty = (w - metrics.horizontalAdvance(text)) / 2, (h + metrics.ascent()) / 2
        p.drawText(tx, ty, text)


class CrashScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.last_state = None
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)

        # Header / Top Bar
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(24, 0, 24, 0)

        back_btn = make_button("‹  " + tr("LOBBY"), "crimson", self.app.leave_room)
        title = QLabel(tr("CRASH"))
        title.setObjectName("balance")
        title.setStyleSheet("color:#C9CDD4; font-size:16px; letter-spacing:3px;")

        self.balance_lbl = QLabel(f"{tr('Balance')}: —")
        self.balance_lbl.setObjectName("balance")

        bl.addWidget(back_btn)
        bl.addStretch(1)
        bl.addWidget(title)
        bl.addStretch(1)
        bl.addWidget(self.balance_lbl)
        bl.addSpacing(12)
        bl.addWidget(sound_toggle_button(self.app))
        self.layout.addWidget(bar)

        # Main Area
        main_layout = QHBoxLayout()

        # Left: Controls
        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)

        self.status_lbl = QLabel(tr("Waiting for bets..."))
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet("color: #E9C46A; font-size: 18px;")

        self.chipbar = ChipBar(self.app)

        bet_layout = QHBoxLayout()
        self.bet_btn = QPushButton(tr("Place Bet"))
        self.bet_btn.setStyleSheet("background: #1E90FF; color: #fff; font-weight: bold; font-size: 16px; border-radius: 8px; padding: 12px; border: 2px solid #00BFFF;")
        self.bet_btn.clicked.connect(self.on_bet)

        self.cashout_btn = QPushButton(tr("CASH OUT"))
        self.cashout_btn.setStyleSheet("background: #2ECC71; color: #fff; font-weight: bold; font-size: 16px; border-radius: 8px; padding: 12px; border: 2px solid #00FF7F;")
        self.cashout_btn.clicked.connect(self.on_cashout)
        self.cashout_btn.setEnabled(False)

        bet_layout.addWidget(self.bet_btn)
        bet_layout.addWidget(self.cashout_btn)

        self.my_bet_lbl = QLabel(tr("Your Bet: 0"))
        self.my_win_lbl = QLabel(tr("Won: 0"))

        left_layout.addWidget(self.status_lbl)
        left_layout.addStretch()
        left_layout.addWidget(self.chipbar)
        left_layout.addLayout(bet_layout)
        left_layout.addWidget(self.my_bet_lbl)
        left_layout.addWidget(self.my_win_lbl)
        main_layout.addWidget(left_panel, 1)

        # Center: Graph / Multiplier
        center_panel = QFrame()
        center_panel.setObjectName("panel")
        center_layout = QVBoxLayout(center_panel)
        self.graph = CrashGraph()
        center_layout.addWidget(self.graph)
        main_layout.addWidget(center_panel, 2)

        # Right: History / Bets
        right_panel = QFrame()
        right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(QLabel("History:"))
        self.history_lbl = QLabel("")
        self.history_lbl.setStyleSheet("font-size: 16px; color: #aaa;")
        right_layout.addWidget(self.history_lbl)

        right_layout.addWidget(QLabel("Current Bets:"))
        self.bets_list = QTextEdit()
        self.bets_list.setReadOnly(True)
        self.bets_list.setStyleSheet("background: #2a2a2a; border: none;")
        right_layout.addWidget(self.bets_list)
        main_layout.addWidget(right_panel, 1)

        self.layout.addLayout(main_layout, 1)

    def on_bet(self):
        amt = self.app.active_chip
        if hasattr(self, 'app') and getattr(self.app, 'client', None):
            self.app.client.send_action("c_bet", amount=amt)
            self.app.profile.stats["crash_played"] += 1
            self.app.profile.stats["total_wagered"] += amt
            self.app.profile.save()

    def on_cashout(self):
        if hasattr(self, 'app') and getattr(self.app, 'client', None):
            self.app.client.send_action("c_cashout")
            self.app.profile.stats["crash_wins"] += 1
            self.app.profile.save()



    def update_state(self, state):
        status = state.get("state", "waiting_for_bets")
        client = getattr(self.app, 'client', None) if hasattr(self, 'app') else None
        pid = client.player_id if client else ""
        bets = state.get("bets", {})
        my_bet = bets.get(pid)

        me = state.get("players", {}).get(self.app.player_id)
        if me:
            self.balance_lbl.setText(f"{tr('Balance')}: ${int(me['balance'])}")
            self.chipbar.refresh(me["balance"])

        if status == "waiting_for_bets":
            self.status_lbl.setText("Waiting for bets...")
            self.graph.update_state(1.0, "waiting_for_bets")
            self.bet_btn.setEnabled(not my_bet)
            self.cashout_btn.setEnabled(False)
        elif status == "flying":
            self.status_lbl.setText("Flying...")
            mult = state.get("current_multiplier", 1.0)
            self.graph.update_state(mult, "flying")
            self.bet_btn.setEnabled(False)
            self.cashout_btn.setEnabled(bool(my_bet and not my_bet.get("cashed_out")))
        elif status == "crashed":
            self.status_lbl.setText("CRASHED!")
            crash_pt = state.get("crash_point", 1.0)
            self.graph.update_state(crash_pt, "crashed")
            self.bet_btn.setEnabled(False)
            self.cashout_btn.setEnabled(False)

        if my_bet:
            self.my_bet_lbl.setText(f"Your Bet: {my_bet['amount']}")
            if my_bet["cashed_out"]:
                won = my_bet["won"]
                self.my_win_lbl.setText(f"Won: {won}")
                self.my_win_lbl.setStyleSheet("color: #2ECC71;")

                # Check for biggest win safely by tracking if we already recorded this round
                if not getattr(self, "_recorded_win", False) and won > 0:
                    if won > self.app.profile.stats["biggest_win"]:
                        self.app.profile.stats["biggest_win"] = won
                    self.app.profile.save()
                    self._recorded_win = True
            else:
                self._recorded_win = False
                self.my_win_lbl.setText("Won: 0")
                self.my_win_lbl.setStyleSheet("color: #fff;")
        else:
            self.my_bet_lbl.setText("Your Bet: 0")
            self.my_win_lbl.setText("Won: 0")

        history = state.get("history", [])
        self.history_lbl.setText("  ".join([f"{x}x" for x in history]))

        bets_text = ""
        for p, b in bets.items():
            b_amt = b['amount']
            if b['cashed_out']:
                bets_text += f"{p[:5]}: {b_amt} -> {b['won']}\n"
            else:
                bets_text += f"{p[:5]}: {b_amt} (Flying)\n"
        self.bets_list.setText(bets_text)



class LobbyScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(24, 0, 24, 0)
        title = QLabel("LOBBY")
        title.setObjectName("balance")
        title.setStyleSheet("color:#C9CDD4; font-size:16px; letter-spacing:3px;")
        self.balance_lbl = QLabel("Balance: —")
        self.balance_lbl.setObjectName("balance")
        bl.addWidget(title)
        bl.addStretch(1)
        bl.addWidget(self.balance_lbl)
        bl.addSpacing(12)

        achv_btn = make_button("🏆 " + tr("ACHIEVEMENTS"), "gold", lambda: [self.app.achievements.refresh(), self.app.stack.setCurrentWidget(self.app.achievements)])
        bl.addWidget(achv_btn)
        bl.addSpacing(12)

        stats_btn = make_button("📊 " + tr("STATISTICS"), "gold", lambda: [self.app.stats_screen.refresh(), self.app.stack.setCurrentWidget(self.app.stats_screen)])
        bl.addWidget(stats_btn)
        bl.addSpacing(12)

        bl.addWidget(sound_toggle_button(self.app))
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setAlignment(Qt.AlignCenter)
        body.setSpacing(28)
        st = QLabel("SELECT A GAME")
        st.setObjectName("sectionTitle")
        st.setAlignment(Qt.AlignCenter)
        body.addWidget(st)

        games = QGridLayout()
        games.setSpacing(24)
        games.addWidget(ClickableTile("BLACKJACK", "Beat the dealer to 21",
                                      "#0B6E4F", "#12936A", "#16B07F", self.app.join_blackjack), 0, 0)
        games.addWidget(ClickableTile("ROULETTE", "Spin the wheel of fortune",
                                      "#7A1220", "#9C1A2C", "#C02236", self.app.join_roulette), 0, 1)
        games.addWidget(ClickableTile("SLOTS", "Match three to win big",
                                      "#7A5A12", "#A07A1E", "#C99A2C", self.app.join_slots), 1, 0)
        games.addWidget(ClickableTile("POKER", "Five-card draw vs bots",
                                      "#3A2A6E", "#4E3A93", "#6A52C0", self.app.join_poker), 1, 1)
        games.addWidget(ClickableTile("CRASH", "Predict the rocket multiplier",
                                      "#0B3D91", "#1E62C4", "#2A7EE0", self.app.join_crash), 2, 0)
        gw = QWidget()
        gw.setLayout(games)
        body.addWidget(gw, 0, Qt.AlignCenter)

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.addStretch(1)
        wl.addLayout(body)
        wl.addStretch(1)
        root.addWidget(wrap, 1)



    def update_state(self, state):
        me = state.get("players", {}).get(self.app.player_id)
        if me:
            self.balance_lbl.setText(f"{tr('Balance')}: ${int(me['balance'])}")


class BlackjackScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.prev_state = None
        self.history = []
        self._card_counts = {}   # area-key -> cards shown last update (for deal anim)
        self._new_cards = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # top bar
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.addWidget(make_button("‹  Lobby", "crimson", self.app.leave_room))
        self.balance_lbl = QLabel("")
        self.balance_lbl.setObjectName("balance")
        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("status")
        bl.addSpacing(12)
        bl.addWidget(self.balance_lbl)
        bl.addStretch(1)
        bl.addWidget(self.status_lbl)
        bl.addSpacing(12)
        bl.addWidget(sound_toggle_button(self.app))
        root.addWidget(bar)

        # felt table
        felt = QFrame()
        felt.setObjectName("felt")
        fl = QVBoxLayout(felt)
        fl.setContentsMargins(24, 18, 24, 18)
        fl.setSpacing(8)

        self.rules_lbl = QLabel("BLACKJACK PAYS 3 TO 2     •     INSURANCE PAYS 2 TO 1")
        self.rules_lbl.setAlignment(Qt.AlignCenter)
        self.rules_lbl.setStyleSheet("color: rgba(233,196,106,0.85); font-size:13px; letter-spacing:2px; font-weight:700;")
        fl.addWidget(self.rules_lbl)

        dealer_cap = QLabel("DEALER")
        dealer_cap.setAlignment(Qt.AlignCenter)
        dealer_cap.setStyleSheet("color:#DfE3E8; font-size:13px; letter-spacing:3px;")
        fl.addWidget(dealer_cap)
        self.dealer_row = QHBoxLayout()
        self.dealer_row.setAlignment(Qt.AlignCenter)
        self.dealer_row.setSpacing(8)
        fl.addLayout(self.dealer_row)
        self.dealer_score = QLabel("")
        self.dealer_score.setAlignment(Qt.AlignCenter)
        self.dealer_score.setStyleSheet("color:#fff; font-size:13px;")
        fl.addWidget(self.dealer_score)

        self.dealer_speech_lbl = QLabel("")
        self.dealer_speech_lbl.setObjectName("dealerSpeech")
        self.dealer_speech_lbl.setAlignment(Qt.AlignCenter)
        fl.addWidget(self.dealer_speech_lbl)

        fl.addStretch(1)

        seats_scroll = QScrollArea()
        seats_scroll.setWidgetResizable(True)
        seats_scroll.setMinimumHeight(340)
        seats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        seats_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        seats_scroll.setStyleSheet("background: transparent; border: none;")
        seats_scroll.viewport().setStyleSheet("background: transparent;")
        seats_host = QWidget()
        seats_host.setStyleSheet("background: transparent;")
        self.seats_row = QHBoxLayout(seats_host)
        self.seats_row.setAlignment(Qt.AlignCenter)
        self.seats_row.setSpacing(20)
        seats_scroll.setWidget(seats_host)
        fl.addWidget(seats_scroll, 0)

        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(18, 14, 18, 6)
        bv.addWidget(felt, 1)
        root.addWidget(body, 1)

        # bottom controls
        controls = QFrame()
        controls.setFixedHeight(132)
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(18, 8, 18, 12)
        cl.setSpacing(8)

        self.chipbar = ChipBar(self.app)
        cl.addWidget(self.chipbar)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.bet_btn = make_button(tr("Place Bet"), "gold", self._on_bet)
        self.hit_btn = make_button(tr("Hit"), "charcoal", lambda: self.app.send_action("hit"))
        self.stand_btn = make_button(tr("Stand"), "charcoal", lambda: self.app.send_action("stand"))
        self.double_btn = make_button(tr("Double"), "charcoal", lambda: self.app.send_action("double"))
        self.split_btn = make_button(tr("Split"), "charcoal", lambda: self.app.send_action("split"))
        self.ins_btn = make_button(tr("Insurance"), "charcoal", lambda: self.app.send_action("insurance"))
        self.start_btn = make_button(tr("Start New Round"), "gold", lambda: self.app.send_action("start_round"))
        self.action_btns = [self.hit_btn, self.stand_btn, self.double_btn, self.split_btn, self.ins_btn]
        btn_row.addStretch(1)
        for b in [self.bet_btn] + self.action_btns + [self.start_btn]:
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        cl.addLayout(btn_row)
        root.addWidget(controls)

    def _set_controls(self, *, chips, bet, actions, start):
        self.chipbar.setVisible(chips)
        self.bet_btn.setVisible(bet)
        for b in self.action_btns:
            b.setVisible(actions)
        self.start_btn.setVisible(start)

    def _on_bet(self):
        amount = self.app.active_chip
        color = ChipBar.COLORS.get(amount, "#888")
        start = self.chipbar.mapTo(self, QPoint(self.chipbar.width() // 2, 12))
        end = QPoint(self.width() // 2 - 19, self.height() // 2)
        fly_chip(self, start, end, color, ChipBar._fmt(amount))
        self.app.sound.play("chip")
        self.app.send_action("bet", amount=amount)

    def _update_action_enabled(self, me, dealer):
        """Enable Double/Split/Insurance only when the move is actually legal;
        disable everything (incl. Hit/Stand) when there is no current hand."""
        if not me or not me.get("hands") or me["current_hand_idx"] >= len(me["hands"]):
            for b in self.action_btns:
                b.setEnabled(False)
            return
        self.hit_btn.setEnabled(True)
        self.stand_btn.setEnabled(True)
        idx = me["current_hand_idx"]
        hand = me["hands"][idx]
        bal, bet = me["balance"], hand["bet"]
        two = len(hand["cards"]) == 2

        def val(c):
            return 10 if c["rank"] in ("J", "Q", "K") else (11 if c["rank"] == "A" else int(c["rank"]))

        self.double_btn.setEnabled(two and bal >= bet)
        self.split_btn.setEnabled(
            two and val(hand["cards"][0]) == val(hand["cards"][1]) and bal >= bet)
        up = dealer["hand"]["cards"][0] if dealer["hand"]["cards"] else None
        self.ins_btn.setEnabled(
            up is not None and up["rank"] == "A" and len(me["hands"]) == 1
            and two and me.get("insurance_bet", 0) == 0 and bal >= bet / 2)



    def update_state(self, state):
        s = state["state"]
        players = state["players"]
        order = state["player_order"]
        me = players.get(self.app.player_id)
        dealer = state["dealer"]

        if me:
            self.balance_lbl.setText(f"{me['name']}  •  ${int(me['balance'])}")
            self.chipbar.refresh(me["balance"])
        self.status_lbl.setText({
            "waiting_for_players": "Press “Start New Round” to deal",
            "betting": "Place your bet",
            "playing": "Your move" if state.get("current_player_id") == self.app.player_id else "Waiting for other players…",
            "dealer_turn": "Dealer is playing…",
            "game_over": "Round over",
        }.get(s, ""))

        # a fresh round resets the deal-animation bookkeeping
        if s in ("betting", "waiting_for_players"):
            self._card_counts = {}
        self._new_cards = 0

        # dealer
        clear_layout(self.dealer_row)
        if s in ("playing", "dealer_turn", "game_over"):
            cards = dealer["hand"]["cards"]
            prev = self._card_counts.get("dealer", 0)
            for i, c in enumerate(cards):
                hidden = (i == 1 and not dealer["show_hidden"])
                cw = CardWidget(c, hidden)
                if i >= prev:
                    fade_in(cw)
                    self._new_cards += 1
                self.dealer_row.addWidget(cw)
            self._card_counts["dealer"] = len(cards)
            self.dealer_score.setText(f"Score: {dealer['hand']['score']}" if dealer["show_hidden"] else "")
        else:
            self.dealer_score.setText("")

        # seats
        clear_layout(self.seats_row)
        for pid in order:
            if pid in players:
                self.seats_row.addWidget(self._seat(players[pid], pid, state, s))

        if self._new_cards > 0:
            self.app.sound.play("deal")

        # dealer speech logic
        speech_text = ""
        if s == "betting":
            speech_text = "Делайте ваши ставки, господа. Игра начинается."
        elif s == "playing":
            if state.get("current_player_id") == self.app.player_id and me and me.get("hands"):
                idx = me["current_hand_idx"]
                if idx < len(me["hands"]):
                    h = me["hands"][idx]
                    if h.get("is_busted"):
                        speech_text = "Перебор! Карты дилеру."
                    else:
                        speech_text = f"У вас {h['score']}. Будете брать карту или остановитесь?"
        elif s == "game_over" and me and me.get("message"):
            msg = me["message"].strip()
            outcome = "Win" if ("Win" in msg or "Blackjack" in msg) else ("Loss" if ("Lose" in msg or "Bust" in msg) else "Push")
            if outcome == "Win":
                speech_text = "Выигрыш ваш, отличная игра!"
            elif outcome == "Loss":
                speech_text = "Дилер побеждает. Повезет в следующий раз."
            else:
                speech_text = "Пуш. Ставки остаются при своих."
        self.dealer_speech_lbl.setText(speech_text)

        # history + win/lose feedback on the playing -> game_over transition
        if self.prev_state in ("playing", "dealer_turn") and s == "game_over" and me and me.get("message"):
            msg = me["message"].strip()
            outcome = "Win" if ("Win" in msg or "Blackjack" in msg) else ("Loss" if ("Lose" in msg or "Bust" in msg) else "Push")
            self.history.insert(0, outcome)
            self.history = self.history[:5]

            # Update stats
            self.app.profile.stats["bj_played"] += 1
            hand_bet = me.get("hands", [{}])[0].get("bet", 0) if me.get("hands") else 0
            self.app.profile.stats["total_wagered"] += hand_bet
            if outcome == "Win":
                self.app.profile.stats["bj_wins"] += 1
                net_win = hand_bet * 1.5 if "Blackjack" in msg else hand_bet
                if net_win > self.app.profile.stats["biggest_win"]:
                    self.app.profile.stats["biggest_win"] = net_win
            self.app.profile.save()

            if outcome == "Win":
                is_bj = "Blackjack" in msg
                if is_bj:
                    self.app.profile.unlock("natural_21", self.app)
                show_celebration(self, "BLACKJACK!" if is_bj else "YOU WIN!")
                self.app.sound.play("jackpot" if is_bj else "win")
            elif outcome == "Loss":
                self.app.sound.play("lose")
        self.prev_state = s

        # controls
        if s == "betting" and me:
            self._set_controls(chips=True, bet=True, actions=False, start=False)
        elif s == "playing" and state.get("current_player_id") == self.app.player_id:
            self._set_controls(chips=False, bet=False, actions=True, start=False)
            self._update_action_enabled(me, dealer)
        elif s in ("waiting_for_players", "game_over"):
            self._set_controls(chips=False, bet=False, actions=False, start=True)
        else:
            self._set_controls(chips=False, bet=False, actions=False, start=False)

    def _seat(self, p, pid, state, s):
        is_current = (state.get("current_player_id") == pid and s == "playing")
        box = QFrame()
        box.setObjectName("nameBadgeActive" if is_current else "nameBadgeNormal")
        box.setFixedWidth(300)
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 12, 16, 14)
        v.setSpacing(6)

        head = QHBoxLayout()
        name_str = p["name"]

        avatar_char = name_str[0].upper() if name_str else "?"
        avatar_lbl = QLabel(avatar_char, box)
        avatar_lbl.setObjectName("avatar")
        avatar_lbl.setFixedSize(28, 28)
        avatar_lbl.setAlignment(Qt.AlignCenter)

        info = QVBoxLayout()
        info.setSpacing(0)

        nm = QLabel(name_str)
        nm.setObjectName("badgeTextActive" if is_current else "badgeTextNormal")

        ch = QLabel(f"${int(p['balance'])}")
        ch.setStyleSheet("color: #E9C46A; font-size: 11px;")

        info.addWidget(nm)
        info.addWidget(ch)

        head.addWidget(avatar_lbl)
        head.addLayout(info)
        head.addStretch(1)
        v.addLayout(head)

        is_me = (pid == self.app.player_id)
        if is_current and is_me:
            idx = p["current_hand_idx"]
            score = p["hands"][idx].get("score", 0) if p["hands"] and idx < len(p["hands"]) else 0
            advice = "HIT" if score < 17 else "STAND"
            adv = QLabel(f"🤖 Advisor suggests:  {advice}")
            adv.setObjectName("advisor")
            v.addWidget(adv)

        for hi, h in enumerate(p["hands"]):
            info = QLabel(f"Bet  ${int(h['bet'])}    •    Score {h['score']}"
                          + ("   ✦ BJ" if h["is_blackjack"] else "")
                          + ("   ✗ Bust" if h["is_busted"] else ""))
            info.setObjectName("handInfo")
            v.addWidget(info)
            cards = QHBoxLayout()
            cards.setSpacing(6)
            cards.setAlignment(Qt.AlignLeft)
            key = f"{pid}:{hi}"
            prev = self._card_counts.get(key, 0)
            for ci, c in enumerate(h["cards"]):
                cw = CardWidget(c)
                if ci >= prev:
                    fade_in(cw)
                    self._new_cards += 1
                cards.addWidget(cw)
            self._card_counts[key] = len(h["cards"])
            v.addLayout(cards)

        if p.get("message"):
            msg = p["message"].strip()
            color = GOLD if ("Win" in msg or "Blackjack" in msg) else ("#E5564B" if ("Lose" in msg or "Bust" in msg) else "#D7DBE0")
            ml = QLabel(msg)
            ml.setWordWrap(True)
            ml.setStyleSheet(f"color:{color}; font-size:15px; font-weight:800;")
            v.addWidget(ml)

        v.addStretch(1)
        return box


class RouletteScreen(QWidget):
    OUTSIDE = {"half_1_to_18": "1 to 18", "half_EVEN": "EVEN", "half_RED": "RED",
               "half_BLACK": "BLACK", "half_ODD": "ODD", "half_19_to_36": "19 to 36"}

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cells = {}        # bet_type -> button
        self.base_text = {}    # bet_type -> base label
        self._last_spin_n = None
        self._pending_win = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.addWidget(make_button("‹  Lobby", "crimson", self.app.leave_room))
        self.balance_lbl = QLabel("")
        self.balance_lbl.setObjectName("balance")
        self.result_lbl = QLabel("")
        self.result_lbl.setObjectName("result")
        bl.addSpacing(12)
        bl.addWidget(self.balance_lbl)
        bl.addStretch(1)
        bl.addWidget(self.result_lbl)
        bl.addSpacing(12)
        bl.addWidget(sound_toggle_button(self.app))
        root.addWidget(bar)

        self.croupier_speech_lbl = QLabel("Пожалуйста, делайте ваши ставки на поле.")
        self.croupier_speech_lbl.setObjectName("dealerSpeech")
        self.croupier_speech_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self.croupier_speech_lbl)

        body = QHBoxLayout()
        body.setContentsMargins(20, 16, 20, 16)
        body.setSpacing(20)

        # left: wheel + spin
        left = QFrame()
        left.setObjectName("panel")
        left.setMinimumWidth(420)
        shadow(left, blur=34, dy=8)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(20, 20, 20, 20)
        self.wheel = RouletteWheel()
        self.wheel.on_spin_end = self._on_spin_end
        lv.addWidget(self.wheel, 1)
        self.spin_btn = make_button("SPIN THE WHEEL", "gold", self._spin, big=True)
        lv.addWidget(self.spin_btn)
        body.addWidget(left, 0)

        # right: board + chips
        right = QVBoxLayout()
        right.setSpacing(14)
        board = QFrame()
        board.setObjectName("felt")
        shadow(board, blur=30, dy=8)
        gv = QVBoxLayout(board)
        gv.setContentsMargins(18, 18, 18, 18)
        gv.addLayout(self._build_board())
        right.addWidget(board, 1)

        chips_wrap = QFrame()
        chips_wrap.setObjectName("panel")
        cwl = QVBoxLayout(chips_wrap)
        cwl.setContentsMargins(16, 12, 16, 12)
        cwl.setSpacing(8)
        cap = QLabel("SELECT CHIP, THEN CLICK THE TABLE TO BET")
        cap.setObjectName("fieldLbl")
        cwl.addWidget(cap)
        self.chipbar = ChipBar(self.app)
        cwl.addWidget(self.chipbar)
        self.bets_lbl = QLabel("No active bets")
        self.bets_lbl.setStyleSheet("color:#B9BFC8; font-size:12px;")
        self.bets_lbl.setWordWrap(True)
        cwl.addWidget(self.bets_lbl)
        act = QHBoxLayout()
        act.setSpacing(10)
        act.addWidget(make_button("Clear Bets", "charcoal", self._clear))
        act.addWidget(make_button("Rebet", "charcoal", self._rebet))
        act.addStretch(1)
        cwl.addLayout(act)
        right.addWidget(chips_wrap, 0)

        body.addLayout(right, 1)
        bw = QWidget()
        bw.setLayout(body)
        root.addWidget(bw, 1)

    # -- board construction --------------------------------------------------
    def _cell(self, key, text, bg, fg="#ffffff", font_size=13):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumSize(46, 44)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        b.setStyleSheet(
            f"QPushButton{{background:{bg};color:{fg};border:1px solid rgba(255,255,255,0.25);"
            f"border-radius:6px;font-weight:800;font-size:{font_size}px;padding:2px;}}"
            f"QPushButton:hover{{border:2px solid {GOLD};}}"
        )
        b.clicked.connect(lambda _=False, k=key: self._on_cell(k))
        self.cells[key] = b
        self.base_text[key] = text
        return b

    def _build_board(self):
        grid = QGridLayout()
        grid.setSpacing(5)

        # zero (spans 3 rows)
        grid.addWidget(self._cell("number_0", "0", "#0E8A3E"), 0, 0, 3, 1)

        # numbers 1..36 — column c has 3c(top), 3c-1(mid), 3c-2(bottom)
        for c in range(1, 13):
            for row in range(3):
                num = 3 * c - row  # row0 -> 3c, row1 -> 3c-1, row2 -> 3c-2
                bg = "#C42030" if num in RED_NUMS else "#1A1A1A"
                grid.addWidget(self._cell(f"number_{num}", str(num), bg), row, c)

        # column (2:1) bets to the right; top row %3==0 -> col_3, etc.
        col_for_row = {0: "col_3", 1: "col_2", 2: "col_1"}
        for row, key in col_for_row.items():
            grid.addWidget(self._cell(key, "2:1", "#0F5A33", GOLD, 12), row, 13)

        # dozens
        grid.addWidget(self._cell("dozen_1", "1st 12", "#0F5A33"), 3, 1, 1, 4)
        grid.addWidget(self._cell("dozen_2", "2nd 12", "#0F5A33"), 3, 5, 1, 4)
        grid.addWidget(self._cell("dozen_3", "3rd 12", "#0F5A33"), 3, 9, 1, 4)

        # even-money outside bets
        outside = [
            ("half_1_to_18", "1 to 18", "#0F5A33"),
            ("half_EVEN", "EVEN", "#0F5A33"),
            ("half_RED", "RED", "#C42030"),
            ("half_BLACK", "BLACK", "#1A1A1A"),
            ("half_ODD", "ODD", "#0F5A33"),
            ("half_19_to_36", "19 to 36", "#0F5A33"),
        ]
        for i, (key, text, bg) in enumerate(outside):
            grid.addWidget(self._cell(key, text, bg), 4, 1 + i * 2, 1, 2)

        for c in range(14):
            grid.setColumnStretch(c, 1)
        return grid

    # -- actions -------------------------------------------------------------
    def _on_cell(self, key):
        amount = self.app.active_chip
        me = (self.app.game_state or {}).get("players", {}).get(self.app.player_id)
        if me and me["balance"] < amount:
            return
        cell = self.cells.get(key)
        if cell is not None:
            color = ChipBar.COLORS.get(amount, "#888")
            start = self.chipbar.mapTo(self, QPoint(self.chipbar.width() // 2, 12))
            end = cell.mapTo(self, cell.rect().center()) - QPoint(19, 19)
            fly_chip(self, start, end, color, ChipBar._fmt(amount))
        self.croupier_speech_lbl.setText("Пожалуйста, делайте ваши ставки на поле.")
        self.app.sound.play("chip")
        self.app.place_roulette_bet(key)

    def _clear(self):
        self.croupier_speech_lbl.setText("Пожалуйста, делайте ваши ставки на поле.")
        self.app.sound.play("click")
        self.app.send_action("r_clear")

    def _rebet(self):
        self.app.sound.play("chip")
        self.app.send_action("r_rebet")

    def _spin(self):
        if self.wheel.spinning:
            return
        self.spin_btn.setEnabled(False)
        self.croupier_speech_lbl.setText("Колесо запущено! Ставок больше нет!")
        self.app.sound.play("spin")
        self.app.send_action("r_spin")

    def _on_spin_end(self):
        self.spin_btn.setEnabled(True)

        # Croupier logic
        if self.app.game_state and self.app.game_state.get("last_result"):
            res = self.app.game_state["last_result"]
            color_map = {"red": "КРАСНОЕ", "black": "ЧЕРНОЕ", "green": "ЗЕРО"}
            ru_color = color_map.get(res["color"], "")
            self.croupier_speech_lbl.setText(f"Выпало {res['number']}, {ru_color}! Поздравляем победителей!")

        if self._pending_win is not None:
            # Update stats
            self.app.profile.stats["roulette_played"] += 1
            past_active = self.app.game_state.get("active_bets", {}).get(self.app.player_id, []) if self.app.game_state else []
            total_bet = sum(b.get("amount", 0) for b in past_active)
            self.app.profile.stats["total_wagered"] += total_bet
            if self._pending_win > 0:
                self.app.profile.stats["roulette_wins"] += 1
                net_win = self._pending_win - total_bet
                if net_win > self.app.profile.stats["biggest_win"]:
                    self.app.profile.stats["biggest_win"] = net_win
            self.app.profile.save()

            if self._pending_win > 0:
                show_celebration(self, f"+${int(self._pending_win)}")
                self.app.sound.play("win")
            else:
                self.app.sound.play("lose")
            self._pending_win = None



    def update_state(self, state):
        me = state.get("players", {}).get(self.app.player_id)
        if me:
            self.balance_lbl.setText(f"{tr('Balance')}: ${int(me['balance'])}")
            self.chipbar.refresh(me["balance"])

        res = state.get("last_result")
        spin_n = state.get("spin_n")
        if res:
            color_hex = {"red": "#E5564B", "black": "#D7DBE0", "green": "#3FBF6B"}.get(res["color"], "#fff")
            self.result_lbl.setText(f"Last:  {res['number']}  ")
            self.result_lbl.setStyleSheet(f"color:{color_hex}; font-size:16px; font-weight:800;")
            if spin_n is not None and spin_n != self._last_spin_n:
                self._last_spin_n = spin_n
                # exact winnings from the server; revealed when the ball settles
                self._pending_win = state.get("last_win", {}).get(self.app.player_id, 0)
                self.wheel.spin_to(res["number"])

        # check for zero hero unlock
        if self._pending_win is not None and self._pending_win > 0 and res and res["number"] == 0:
            self.app.profile.unlock("zero_hero", self.app)

        # reset cell labels, then mark active bets with the staked amount
        for k, b in self.cells.items():
            b.setText(self.base_text[k])

        active = state.get("active_bets", {}).get(self.app.player_id, [])
        if active:
            totals = {}
            for bet in active:
                totals[bet["type"]] = totals.get(bet["type"], 0) + bet["amount"]
            summary = []
            for k, amt in totals.items():
                if k in self.cells:
                    self.cells[k].setText(f"{self.base_text[k]}\n${int(amt)}")
                summary.append(f"{self.OUTSIDE.get(k, k.replace('_', ' '))}: ${int(amt)}")
            self.bets_lbl.setText("Active bets — " + ",  ".join(summary))
        else:
            self.bets_lbl.setText("No active bets")


class SlotReel(QFrame):
    """One slot reel: paints a single big symbol and can spin to a target."""

    SYMS = [(ch, col) for ch, col, _w, _m in SLOT_SYMBOLS]

    def __init__(self):
        super().__init__()
        self.setFixedSize(118, 150)
        self.symbol = ("7", SLOT_COLOR["7"])
        self.spinning = False
        self.on_stop = None
        self._target = self.symbol
        self._tick = 0
        self._max = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._cycle)

    def spin_to(self, ch, ticks):
        self._timer.stop()   # never leave a stale timer running into a new spin
        self._target = (ch, SLOT_COLOR.get(ch, "#fff"))
        self._tick = 0
        self._max = max(3, ticks)
        self.spinning = True
        self._timer.start(55)

    def _cycle(self):
        self._tick += 1
        if self._tick >= self._max:
            self._timer.stop()
            self.spinning = False
            self.symbol = self._target
            self.update()
            if self.on_stop:
                self.on_stop()
            return
        self.symbol = random.choice(self.SYMS)
        self.update()

    def hideEvent(self, _e):
        self._timer.stop()
        self.spinning = False

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor("#FCFCF8"))
        g.setColorAt(1, QColor("#E6E6DE"))
        p.fillPath(path, QBrush(g))
        p.setPen(QPen(QColor("#C7C7BE"), 2))
        p.drawPath(path)
        ch, col = self.symbol
        p.setPen(QColor(col))
        p.setFont(QFont("Segoe UI", 60, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, ch)


class SlotsScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._last_n = None
        self._awaiting = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.addWidget(make_button("‹  Lobby", "crimson", self.app.leave_room))
        self.balance_lbl = QLabel("")
        self.balance_lbl.setObjectName("balance")
        bl.addSpacing(12)
        bl.addWidget(self.balance_lbl)
        bl.addStretch(1)
        bl.addWidget(sound_toggle_button(self.app))
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 10)
        body.setSpacing(16)

        machine = QFrame()
        machine.setObjectName("felt")
        shadow(machine, blur=34, dy=10)
        mv = QVBoxLayout(machine)
        mv.setContentsMargins(26, 26, 26, 26)
        mv.setSpacing(16)
        title = QLabel("LUCKY SPIN")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#E9C46A; font-size:22px; font-weight:800; letter-spacing:4px; background:transparent;")
        mv.addWidget(title)
        reels_row = QHBoxLayout()
        reels_row.setSpacing(18)
        reels_row.setAlignment(Qt.AlignCenter)
        self.reels = [SlotReel() for _ in range(3)]
        for r in self.reels:
            reels_row.addWidget(r)
        mv.addLayout(reels_row)
        self.win_lbl = QLabel("Spin to play!")
        self.win_lbl.setAlignment(Qt.AlignCenter)
        self.win_lbl.setStyleSheet("color:#fff; font-size:18px; font-weight:800; background:transparent;")
        mv.addWidget(self.win_lbl)
        body.addWidget(machine, 1)

        pay = QLabel(self._paytable_text())
        pay.setAlignment(Qt.AlignCenter)
        pay.setStyleSheet("color:#B9BFC8; font-size:12px;")
        body.addWidget(pay)

        bw = QWidget()
        bw.setLayout(body)
        root.addWidget(bw, 1)

        controls = QFrame()
        controls.setFixedHeight(150)
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(18, 10, 18, 14)
        cl.setSpacing(10)
        self.chipbar = ChipBar(self.app)
        cl.addWidget(self.chipbar)
        brow = QHBoxLayout()
        brow.addStretch(1)
        self.spin_btn = make_button("SPIN", "gold", self._spin, big=True)
        self.spin_btn.setMinimumWidth(220)
        brow.addWidget(self.spin_btn)
        brow.addStretch(1)
        cl.addLayout(brow)
        root.addWidget(controls)

    @staticmethod
    def _paytable_text():
        parts = [f"{ch}{ch}{ch} ×{m}" for ch, _col, _w, m in SLOT_SYMBOLS]
        return "    ".join(parts) + "      any pair ×2"

    def _spin(self):
        if self._awaiting or any(r.spinning for r in self.reels):
            return
        bet = self.app.active_chip
        me = (self.app.game_state or {}).get("players", {}).get(self.app.player_id)
        if me and me["balance"] < bet:
            self.win_lbl.setText("Not enough balance for that chip")
            self.win_lbl.setStyleSheet("color:#E5564B; font-size:15px; background:transparent;")
            return
        self._awaiting = True
        self.spin_btn.setEnabled(False)
        self.win_lbl.setText("")
        self.app.sound.play("spin")
        self.app.send_action("s_spin", amount=bet)



    def update_state(self, state):
        me = state.get("players", {}).get(self.app.player_id)
        if me:
            self.balance_lbl.setText(f"{tr('Balance')}: ${int(me['balance'])}")
            self.chipbar.refresh(me["balance"])
        last = state.get("last")
        spinning = any(r.spinning for r in self.reels)
        if last and last.get("n") != self._last_n and not spinning:
            self._last_n = last.get("n")
            self._animate(last)
        elif self._awaiting and not spinning:
            # a spin that produced no new result (e.g. rejected) — restore button
            self._awaiting = False
            self.spin_btn.setEnabled(True)

    def _animate(self, last):
        if any(r.spinning for r in self.reels):
            return
        reels = last["reels"]
        self._awaiting = True
        self.spin_btn.setEnabled(False)
        for i, r in enumerate(self.reels):
            if i < len(self.reels) - 1:
                r.on_stop = lambda: self.app.sound.play("reel")
            else:
                r.on_stop = lambda last=last: self._finish(last)
            r.spin_to(reels[i], 12 + i * 7)

    def _finish(self, last):
        self._awaiting = False
        self.spin_btn.setEnabled(True)
        win = last["win"]
        reels = last["reels"]
        bet = last.get("bet", 0)

        # Update stats
        self.app.profile.stats["slots_played"] += 1
        self.app.profile.stats["total_wagered"] += bet
        if win > 0:
            self.app.profile.stats["slots_wins"] += 1
            net_win = win - bet
            if net_win > self.app.profile.stats["biggest_win"]:
                self.app.profile.stats["biggest_win"] = net_win
        self.app.profile.save()

        if win > 0:
            jackpot = (reels[0] == reels[1] == reels[2])
            if jackpot and reels[0] == "7":
                self.app.profile.unlock("jackpot_king", self.app)
            self.win_lbl.setText(f"YOU WIN  ${int(win)}!")
            self.win_lbl.setStyleSheet("color:#E9C46A; font-size:20px; font-weight:800; background:transparent;")
            show_celebration(self, ("JACKPOT!  " if jackpot else "") + f"+${int(win)}")
            self.app.sound.play("jackpot" if jackpot else "win")
        else:
            self.win_lbl.setText("No win — spin again")
            self.win_lbl.setStyleSheet("color:#9AA0AA; font-size:16px; background:transparent;")
            self.app.sound.play("lose")


class PokerHandCard(CardWidget):
    """A player hole card that can be clicked to mark it for discard."""

    clicked = Signal()

    def __init__(self, card):
        super().__init__(card)
        self.marked = False
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def set_marked(self, on):
        self.marked = on
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.marked:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.scale(self.width() / 74.0, self.height() / 106.0)
            rect = QRectF(1, 1, 74 - 2, 106 - 2)
            path = QPainterPath()
            path.addRoundedRect(rect, 11, 11)
            p.fillPath(path, QColor(200, 40, 40, 120))
            p.setPen(QPen(QColor("#E5564B"), 3))
            p.drawPath(path)
            p.setPen(QColor("white"))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(rect, Qt.AlignHCenter | Qt.AlignBottom, "DISCARD")


class PokerScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._discards = set()
        self._hand_no = None
        self._was_drawn = False
        self._step_scheduled = False
        self._last_showdown_hand = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.addWidget(make_button("‹  Lobby", "crimson", self.app.leave_room))
        self.balance_lbl = QLabel("")
        self.balance_lbl.setObjectName("balance")
        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("status")
        bl.addSpacing(12)
        bl.addWidget(self.balance_lbl)
        bl.addStretch(1)
        bl.addWidget(self.status_lbl)
        bl.addSpacing(12)
        bl.addWidget(sound_toggle_button(self.app))
        root.addWidget(bar)

        felt = QFrame()
        felt.setObjectName("felt")
        fl = QVBoxLayout(felt)
        fl.setContentsMargins(22, 16, 22, 16)
        fl.setSpacing(8)

        cap = QLabel("FIVE-CARD DRAW")
        cap.setAlignment(Qt.AlignCenter)
        cap.setStyleSheet("color: rgba(233,196,106,0.85); font-size:13px; letter-spacing:3px; font-weight:700; background:transparent;")
        fl.addWidget(cap)

        self.bots_row = QHBoxLayout()
        self.bots_row.setAlignment(Qt.AlignCenter)
        self.bots_row.setSpacing(16)
        fl.addLayout(self.bots_row)

        self.pot_lbl = QLabel("")
        self.pot_lbl.setAlignment(Qt.AlignCenter)
        self.pot_lbl.setStyleSheet("color:#E9C46A; font-size:22px; font-weight:800; background:transparent;")
        fl.addStretch(1)
        fl.addWidget(self.pot_lbl)
        self.msg_lbl = QLabel("")
        self.msg_lbl.setAlignment(Qt.AlignCenter)
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.setStyleSheet("color:#fff; font-size:16px; font-weight:700; background:transparent;")
        fl.addWidget(self.msg_lbl)
        fl.addStretch(1)

        self.you_lbl = QLabel("")
        self.you_lbl.setAlignment(Qt.AlignCenter)
        self.you_lbl.setStyleSheet("color:#fff; font-size:14px; font-weight:700; background:transparent;")
        fl.addWidget(self.you_lbl)

        self.advisor_lbl = QLabel("")
        self.advisor_lbl.setObjectName("advisor")
        self.advisor_lbl.setAlignment(Qt.AlignCenter)
        fl.addWidget(self.advisor_lbl)
        self.hand_row = QHBoxLayout()
        self.hand_row.setAlignment(Qt.AlignCenter)
        self.hand_row.setSpacing(8)
        fl.addLayout(self.hand_row)

        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(18, 12, 18, 6)
        bv.addWidget(felt, 1)
        root.addWidget(body, 1)

        # bottom controls
        controls = QFrame()
        controls.setFixedHeight(132)
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(18, 8, 18, 12)
        cl.setSpacing(8)
        self.chipbar = ChipBar(self.app)
        cl.addWidget(self.chipbar)
        self.hint_lbl = QLabel("")
        self.hint_lbl.setAlignment(Qt.AlignCenter)
        self.hint_lbl.setStyleSheet("color:#9AA0AA; font-size:12px;")
        cl.addWidget(self.hint_lbl)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        self.deal_btn = make_button(tr("Deal"), "gold", lambda: self._deal())
        self.fold_btn = make_button(tr("Fold"), "crimson", lambda: self._act("fold"))
        self.check_btn = make_button(tr("Check"), "charcoal", lambda: self._act("check"))
        self.call_btn = make_button(tr("Call"), "charcoal", lambda: self._act("call"))
        self.bet_btn = make_button(tr("Place Bet"), "gold", lambda: self._act("bet"))
        self.raise_btn = make_button(tr("Raise"), "gold", lambda: self._act("raise"))
        self.draw_btn = make_button(tr("Draw"), "gold", lambda: self._draw_cards())
        self._all_btns = [self.deal_btn, self.fold_btn, self.check_btn, self.call_btn,
                          self.bet_btn, self.raise_btn, self.draw_btn]
        for b in self._all_btns:
            row.addWidget(b)
        row.addStretch(1)
        cl.addLayout(row)
        root.addWidget(controls)

    # -- actions -------------------------------------------------------------
    def _deal(self):
        self._discards = set()
        self.app.send_action("p_deal", amount=self.app.active_chip)

    def _act(self, action):
        if (self.app.game_state or {}).get("awaiting") != "human":
            return
        self.app.sound.play("chip" if action in ("call", "bet", "raise") else "click")
        self.app.send_action("p_act", poker_action=action)

    def _draw_cards(self):
        if (self.app.game_state or {}).get("awaiting") != "draw_human":
            return
        self.app.sound.play("deal")
        self.app.send_action("p_act", poker_action="draw", discards=sorted(self._discards))
        self._discards = set()

    def _toggle_discard(self, i, card):
        if i in self._discards:
            self._discards.discard(i)
            card.set_marked(False)
        else:
            self._discards.add(i)
            card.set_marked(True)

    # -- rendering -----------------------------------------------------------
    def _bot_seat(self, seat, idx):
        box = QFrame()
        box.setObjectName("nameBadgeActive" if seat["is_actor"] else "nameBadgeNormal")
        box.setFixedWidth(210)

        v = QVBoxLayout(box)
        v.setContentsMargins(12, 8, 12, 10)
        v.setSpacing(4)

        head = QHBoxLayout()
        name = seat["name"]
        avatar_char = "🤖" if seat.get("bot", False) else (name[0].upper() if name else "?")
        avatar_lbl = QLabel(avatar_char, box)
        avatar_lbl.setObjectName("avatar")
        avatar_lbl.setFixedSize(28, 28)
        avatar_lbl.setAlignment(Qt.AlignCenter)

        info = QVBoxLayout()
        nm = QLabel(name)
        nm.setObjectName("badgeTextActive" if seat["is_actor"] else "badgeTextNormal")

        action_text = seat.get('action', seat.get('status', ''))
        ch = QLabel(f"${int(seat['chips'])} | {action_text}" if action_text else f"${int(seat['chips'])}")
        ch.setStyleSheet("color: #E9C46A; font-size: 11px;")

        info.addWidget(nm)
        info.addWidget(ch)

        head.addWidget(avatar_lbl)
        head.addLayout(info)
        head.addStretch(1)
        v.addLayout(head)

        cards = QHBoxLayout()
        cards.setSpacing(3)
        cards.setAlignment(Qt.AlignCenter)
        if seat["folded"]:
            lbl = QLabel("folded")
            lbl.setStyleSheet("color:#8A909A; font-size:13px; background:transparent;")
            cards.addWidget(lbl)
        elif seat["hand"]:                       # revealed at showdown
            for c in seat["hand"]:
                mini = CardWidget(c)
                mini.setFixedSize(34, 48)
                cards.addWidget(mini)
        else:
            for _ in range(seat["card_count"]):
                mini = CardWidget(None, hidden=True)
                mini.setFixedSize(34, 48)
                cards.addWidget(mini)
        v.addLayout(cards)

        sub = QLabel("" if seat["committed_round"] == 0 else f"bet ${int(seat['committed_round'])}")
        sub.setStyleSheet("color:#E9C46A; font-size:11px; background:transparent;")
        sub.setAlignment(Qt.AlignCenter)
        v.addWidget(sub)
        return box



    def update_state(self, state):
        seats = state["seats"]
        me = seats[0]
        phase = state["phase"]
        awaiting = state["awaiting"]
        self.balance_lbl.setText(f"{me['name']}  •  ${int(me['chips'])}")
        self.chipbar.refresh(me["chips"])
        self.status_lbl.setText({
            "betting1": "Betting round 1", "draw": "Draw phase",
            "betting2": "Betting round 2", "showdown": "Showdown",
            "done": "Hand over", "idle": "",
        }.get(phase, ""))

        # bots
        clear_layout(self.bots_row)
        for i in range(1, len(seats)):
            self.bots_row.addWidget(self._bot_seat(seats[i], i))

        self.pot_lbl.setText(f"POT  ${int(state['pot'])}" if state["pot"] else "")
        self.msg_lbl.setText(state.get("message", ""))

        # detect new deal / draw to play sound + fade
        new_deal = state["hand_no"] != self._hand_no
        if new_deal:
            self._hand_no = state["hand_no"]
            self._was_drawn = False
            self._discards = set()
        drew_now = me["drawn"] and not self._was_drawn
        self._was_drawn = me["drawn"]
        if new_deal or drew_now:
            self.app.sound.play("deal")

        # your hand
        you_tag = "  •  ".join(
            x for x in [f"committed ${int(me['committed_total'])}" if me["committed_total"] else "",
                        "FOLDED" if me["folded"] else ""] if x)
        self.you_lbl.setText((me["name"] + ("   " + you_tag if you_tag else "")))
        clear_layout(self.hand_row)
        if me["hand"]:
            for i, c in enumerate(me["hand"]):
                if awaiting == "draw_human":
                    card = PokerHandCard(c)
                    card.set_marked(i in self._discards)
                    card.clicked.connect(lambda ii=i, cw=card: self._toggle_discard(ii, cw))
                    self.hand_row.addWidget(card)
                else:
                    cw = CardWidget(c)
                    if new_deal or drew_now:
                        fade_in(cw)
                    self.hand_row.addWidget(cw)

        if me["hand"]:
            rank_tuple = poker_hand_rank(me["hand"])
            cat = rank_tuple[0]
            hand_name = poker_rank_name(rank_tuple)
            owe = state.get("owe", 0)

            advice_text = ""
            if awaiting == "human":
                if owe == 0:
                    if cat >= 3:
                        advice_text = f"🤖 Advisor: Strong hand ({hand_name})! You should definitely BET."
                    elif cat >= 1:
                        advice_text = f"🤖 Advisor: Made a {hand_name}. CHECK to see what happens, or place a cautious BET."
                    else:
                        advice_text = f"🤖 Advisor: No combination ({hand_name}). Declare a safe CHECK."
                else:
                    if cat >= 3:
                        advice_text = f"🤖 Advisor: Great hand ({hand_name})! Confidently CALL or RAISE."
                    elif cat >= 1:
                        advice_text = f"🤖 Advisor: Low pair ({hand_name}). Worth a CALL to stay in the game."
                    else:
                        advice_text = f"🤖 Advisor: Weak hand ({hand_name}). Better to FOLD and save your chips."
            elif awaiting == "draw_human":
                if cat >= 4:
                    advice_text = f"🤖 Advisor: Monster made hand ({hand_name})! Do NOT discard anything (Stand Pat)."
                elif cat >= 1:
                    advice_text = f"🤖 Advisor: Keep your {hand_name} cards! Click on the other trash cards to DISCARD them."
                else:
                    advice_text = f"🤖 Advisor: No pair. Keep 1 or 2 highest cards (Ace/King), click the rest to DISCARD."
            elif awaiting == "bot":
                advice_text = "🤖 Advisor: Watching the opponents act..."
            else:
                advice_text = f"🤖 Advisor: Your current hand valuation is {hand_name}."

            self.advisor_lbl.setText(advice_text)
        else:
            self.advisor_lbl.setText("")

        # showdown result feedback (once per hand)
        res = state.get("results")
        if res and state["hand_no"] != self._last_showdown_hand:
            self._last_showdown_hand = state["hand_no"]

            # Update stats
            self.app.profile.stats["poker_played"] += 1
            self.app.profile.stats["total_wagered"] += me.get("committed_total", 0)
            if 0 in res.get("winners", []):
                self.app.profile.stats["poker_wins"] += 1
                pot_size = res.get("pot", 0)
                net_win = (pot_size // len(res["winners"])) - me.get("committed_total", 0)
                if net_win > self.app.profile.stats["biggest_win"]:
                    self.app.profile.stats["biggest_win"] = net_win
            self.app.profile.save()

            if 0 in res.get("winners", []):
                win_name = res.get("names", {}).get("0", "")
                if win_name in ["Straight", "Flush", "Full House", "Four of a Kind", "Straight Flush"]:
                    self.app.profile.unlock("poker_shark", self.app)
                show_celebration(self, self.msg_lbl.text() or "YOU WIN!")
                self.app.sound.play("win")
            else:
                self.app.sound.play("lose")

        self._update_controls(state)

        # pace the bots
        if awaiting == "bot":
            if not self._step_scheduled:
                self._step_scheduled = True
                QTimer.singleShot(700, self._do_step)

    def _do_step(self):
        self._step_scheduled = False
        if self.app.stack.currentWidget() is self and self.app.game_state \
                and self.app.game_state.get("awaiting") == "bot":
            self.app.send_action("p_step")

    def _update_controls(self, state):
        awaiting = state["awaiting"]
        legal = state.get("legal", [])
        for b in self._all_btns:
            b.setVisible(False)
        self.chipbar.setVisible(False)
        self.hint_lbl.setText("")

        if awaiting == "done":
            self.chipbar.setVisible(True)
            self.deal_btn.setText("Deal" if state["phase"] != "done" else "Deal next hand")
            self.deal_btn.setVisible(True)
            self.hint_lbl.setText(f"Ante = selected chip (${self.app.active_chip}). Pick a chip and deal.")
        elif awaiting == "human":
            owe = state.get("owe", 0)
            unit = state["bet_unit"]
            self.fold_btn.setVisible(True)
            if "check" in legal:
                self.check_btn.setVisible(True)
            if "call" in legal:
                self.call_btn.setText(f"Call ${int(owe)}")
                self.call_btn.setVisible(True)
            if "bet" in legal:
                self.bet_btn.setText(f"Bet ${int(unit)}")
                self.bet_btn.setVisible(True)
            if "raise" in legal:
                self.raise_btn.setText(f"Raise ${int(unit)}")
                self.raise_btn.setVisible(True)
        elif awaiting == "draw_human":
            n = len(self._discards)
            self.draw_btn.setText(f"Draw ({n})" if n else "Stand Pat")
            self.draw_btn.setVisible(True)
            self.hint_lbl.setText("Click your cards to discard, then Draw.")



class AchievementsScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.addWidget(make_button("‹  Lobby", "charcoal", lambda: self.app.stack.setCurrentWidget(self.app.lobby)))
        title = QLabel("TROPHY ROOM")
        title.setStyleSheet("color:#E9C46A; font-size:18px; font-weight:800; letter-spacing:3px;")
        bl.addStretch(1)
        bl.addWidget(title)
        bl.addStretch(1)
        bl.addWidget(sound_toggle_button(self.app))
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setAlignment(Qt.AlignCenter)
        body.setSpacing(28)

        self.grid = QGridLayout()
        self.grid.setSpacing(24)

        gw = QWidget()
        gw.setLayout(self.grid)
        body.addWidget(gw, 0, Qt.AlignCenter)

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.addStretch(1)
        wl.addLayout(body)
        wl.addStretch(1)
        root.addWidget(wrap, 1)

    def refresh(self):
        clear_layout(self.grid)
        achievements_data = [
            ("high_roller", "High Roller", "Bet $10,000 in any game"),
            ("jackpot_king", "Jackpot King", "Hit 3x '7' in slots"),
            ("poker_shark", "Poker Shark", "Win a poker hand with Straight or better"),
            ("zero_hero", "Zero Hero", "Win a single number '0' bet in roulette"),
            ("natural_21", "Natural 21", "Get a natural Blackjack on deal"),
            ("phoenix", "Phoenix", "Go broke to $0, get welfare bonus, and reach $5,000+")
        ]

        row, col = 0, 0
        for key, title, desc in achievements_data:
            unlocked = self.app.profile.achievements.get(key, False)
            tile = QFrame()
            tile.setFixedSize(290, 140)

            if unlocked:
                tile.setStyleSheet("border-radius:20px; background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #A07A1E,stop:1 #7A5A12); border: 2px solid #E9C46A;")
            else:
                tile.setStyleSheet("border-radius:20px; background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2E3440,stop:1 #20242C); border: 1px solid rgba(255,255,255,0.1);")
                eff = QGraphicsOpacityEffect(tile)
                eff.setOpacity(0.6)
                tile.setGraphicsEffect(eff)

            shadow(tile, blur=20, dy=6)
            v = QVBoxLayout(tile)
            v.setAlignment(Qt.AlignCenter)
            v.setSpacing(8)

            t = QLabel(title)
            t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet(f"background:transparent; color:{'#fff' if unlocked else '#8A909A'}; font-size:22px; font-weight:800; letter-spacing:1px;")

            s = QLabel(desc)
            s.setAlignment(Qt.AlignCenter)
            s.setWordWrap(True)
            s.setStyleSheet(f"background:transparent; color:{'rgba(255,255,255,0.9)' if unlocked else '#5b5f66'}; font-size:12px;")

            status = QLabel("🏆 Unlocked!" if unlocked else "🔒 Locked")
            status.setAlignment(Qt.AlignCenter)
            status.setStyleSheet(f"background:transparent; color:{'#FFD700' if unlocked else '#5b5f66'}; font-size:14px; font-weight:700; margin-top:5px;")

            v.addWidget(t)
            v.addWidget(s)
            v.addWidget(status)

            self.grid.addWidget(tile, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

# --------------------------------------------------------------------------
# Main window / controller

# --------------------------------------------------------------------------


class StatsScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.addWidget(make_button("‹  Lobby", "charcoal", lambda: self.app.stack.setCurrentWidget(self.app.lobby)))
        title = QLabel("📊 PLAYER ANALYTICS")
        title.setStyleSheet("color:#E9C46A; font-size:18px; font-weight:800; letter-spacing:3px;")
        bl.addStretch(1)
        bl.addWidget(title)
        bl.addStretch(1)
        bl.addWidget(sound_toggle_button(self.app))
        root.addWidget(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        body_layout.setSpacing(28)
        body_layout.setContentsMargins(20, 30, 20, 30)

        # General Records
        gen_box = QFrame()
        gen_box.setStyleSheet("border-radius:20px; background:rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);")
        gen_box.setFixedWidth(580)
        shadow(gen_box, blur=20, dy=6)
        gv = QVBoxLayout(gen_box)
        gv.setContentsMargins(24, 20, 24, 20)
        gv.setSpacing(12)

        gt = QLabel("GENERAL RECORDS")
        gt.setStyleSheet("color:#D7DBE0; font-size:14px; font-weight:800; letter-spacing:2px; background:transparent; border:none;")
        gt.setAlignment(Qt.AlignCenter)
        gv.addWidget(gt)

        self.gen_grid = QGridLayout()
        self.gen_grid.setSpacing(16)
        gv.addLayout(self.gen_grid)
        body_layout.addWidget(gen_box)

        # Game Breakdowns
        break_box = QFrame()
        break_box.setStyleSheet("border-radius:20px; background:rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);")
        break_box.setFixedWidth(580)
        shadow(break_box, blur=20, dy=6)
        bv = QVBoxLayout(break_box)
        bv.setContentsMargins(24, 20, 24, 20)
        bv.setSpacing(12)

        bt = QLabel("GAME BREAKDOWN")
        bt.setStyleSheet("color:#D7DBE0; font-size:14px; font-weight:800; letter-spacing:2px; background:transparent; border:none;")
        bt.setAlignment(Qt.AlignCenter)
        bv.addWidget(bt)

        self.break_grid = QGridLayout()
        self.break_grid.setSpacing(16)
        bv.addLayout(self.break_grid)
        body_layout.addWidget(break_box)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _make_stat_card(self, title, value):
        w = QFrame()
        w.setStyleSheet("background:rgba(0,0,0,0.3); border-radius:12px; border: 1px solid rgba(255,255,255,0.05);")
        w.setMinimumHeight(70)
        l = QVBoxLayout(w)
        l.setAlignment(Qt.AlignCenter)
        l.setSpacing(4)
        tl = QLabel(title)
        tl.setStyleSheet("color:#8A909A; font-size:12px; background:transparent; border:none;")
        tl.setAlignment(Qt.AlignCenter)
        vl = QLabel(str(value))
        vl.setStyleSheet("color:#E9C46A; font-size:20px; font-weight:800; background:transparent; border:none;")
        vl.setAlignment(Qt.AlignCenter)
        l.addWidget(tl)
        l.addWidget(vl)
        return w

    def _make_game_row(self, title, played, wins):
        w = QFrame()
        w.setStyleSheet("background:rgba(0,0,0,0.3); border-radius:12px; border: 1px solid rgba(255,255,255,0.05);")
        w.setMinimumHeight(60)
        l = QHBoxLayout(w)
        l.setContentsMargins(20, 10, 20, 10)

        t = QLabel(title)
        t.setStyleSheet("color:#fff; font-size:16px; font-weight:800; background:transparent; border:none; width: 120px;")
        t.setMinimumWidth(120)
        l.addWidget(t)

        l.addStretch(1)

        p = QLabel(f"Played: {played}")
        p.setStyleSheet("color:#B9BFC8; font-size:13px; background:transparent; border:none;")
        p.setMinimumWidth(80)
        l.addWidget(p)

        wi = QLabel(f"Wins: {wins}")
        wi.setStyleSheet("color:#B9BFC8; font-size:13px; background:transparent; border:none;")
        wi.setMinimumWidth(80)
        l.addWidget(wi)

        rate = (wins / played * 100) if played > 0 else 0
        r = QLabel(f"{rate:.1f}%")
        r.setStyleSheet("color:#E9C46A; font-size:16px; font-weight:800; background:transparent; border:none;")
        r.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        r.setMinimumWidth(60)
        l.addWidget(r)

        return w

    def refresh(self):
        clear_layout(self.gen_grid)
        clear_layout(self.break_grid)

        s = self.app.profile.stats

        self.gen_grid.addWidget(self._make_stat_card("Total Wagered", f"${int(s['total_wagered'])}"), 0, 0)
        self.gen_grid.addWidget(self._make_stat_card("Biggest Win", f"${int(s['biggest_win'])}"), 0, 1)
        self.gen_grid.addWidget(self._make_stat_card("Welfare Claims", str(s['welfare_count'])), 0, 2)

        self.break_grid.addWidget(self._make_game_row("BLACKJACK", s["bj_played"], s["bj_wins"]), 0, 0)
        self.break_grid.addWidget(self._make_game_row("ROULETTE", s["roulette_played"], s["roulette_wins"]), 1, 0)
        self.break_grid.addWidget(self._make_game_row("SLOTS", s["slots_played"], s["slots_wins"]), 2, 0)
        self.break_grid.addWidget(self._make_game_row("POKER", s["poker_played"], s["poker_wins"]), 3, 0)
        self.break_grid.addWidget(self._make_game_row("CRASH", s.get("crash_played", 0), s.get("crash_wins", 0)), 4, 0)

class Bridge(QObject):

    """Marshals state updates from the network thread onto the GUI thread."""
    state = Signal(object)


class CasinoApp(QMainWindow):
    def set_language(self, lang):
        global CURRENT_LANG
        CURRENT_LANG = lang

        # Clear the stack entirely
        while self.stack.count() > 0:
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.deleteLater()

        # Re-initialize all screens to apply translations
        self.start = StartScreen(self)
        self.lobby = LobbyScreen(self)
        self.blackjack = BlackjackScreen(self)
        self.roulette = RouletteScreen(self)
        self.slots = SlotsScreen(self)
        self.poker = PokerScreen(self)
        self.crash_screen = CrashScreen(self)
        self.achievements = AchievementsScreen(self)
        self.stats_screen = StatsScreen(self)

        for w in (self.start, self.lobby, self.blackjack, self.roulette, self.slots, self.poker, self.crash_screen, self.achievements, self.stats_screen):
            self.stack.addWidget(w)

        # If client is already connected, push it to new screens
        if self.client:
            self.client.on_state_update = self.bridge.state.emit
            self.crash_screen.app = self
            if getattr(self.client, "room", "lobby") != "lobby":
                self.client.send_action("join_room", room=self.client.room)

        self.stack.setCurrentWidget(self.start)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("blackjack")

        self.setMinimumSize(1060, 720)

        self.player_id = str(uuid.uuid4())
        self.client = None
        self.server = None
        self.active_chip = 10
        self.game_state = None
        self.sound = SoundManager()
        self.profile = ProfileManager()

        # Bridge is parented to the window and the connection is explicitly
        # queued, so state pushed from the socket thread is always delivered
        # on the GUI thread (and the in-process single-player path is decoupled
        # from the action that produced it, avoiding re-entrant updates).
        self.bridge = Bridge(self)
        self.bridge.state.connect(self.on_state, Qt.QueuedConnection)

        central = QWidget()
        central.setObjectName("root")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.setCentralWidget(central)

        self.start = StartScreen(self)
        self.lobby = LobbyScreen(self)
        self.blackjack = BlackjackScreen(self)
        self.roulette = RouletteScreen(self)
        self.slots = SlotsScreen(self)
        self.poker = PokerScreen(self)
        self.crash_screen = CrashScreen(self)
        self.achievements = AchievementsScreen(self)
        self.stats_screen = StatsScreen(self)
        for w in (self.start, self.lobby, self.blackjack, self.roulette, self.slots, self.poker, self.crash_screen, self.achievements, self.stats_screen):
            self.stack.addWidget(w)
        self.stack.setCurrentWidget(self.start)
        self._install_shortcuts()

    # -- connection flows ----------------------------------------------------
    def _attach(self, client):
        self.client = client
        self.client.on_state_update = self.bridge.state.emit

    def start_singleplayer(self, name):
        try:
            self.profile.name = name
            self.profile.save()
            local_client = LocalClient(self.player_id, name)
            local_client.server.global_players[self.player_id]["balance"] = self.profile.balance
            self._attach(local_client)
            self.client.connect()
            self.stack.setCurrentWidget(self.lobby)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not start single-player.\n{e}")

    def host_game(self, name):
        try:
            self.server = Server()
            self.server.start()
            self._connect_remote("127.0.0.1", name)
        except Exception as e:
            QMessageBox.critical(self, "Host Error", f"Could not host the game.\n{e}")

    def join_game(self, name, ip):
        self._connect_remote(ip or "127.0.0.1", name)

    def _connect_remote(self, ip, name):
        try:
            self._attach(Client(ip, self.player_id, name))
            self.client.connect()
            self.stack.setCurrentWidget(self.lobby)
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to {ip}.\n{e}")

    # -- navigation / actions -----------------------------------------------
    def join_blackjack(self):
        if not self.client:
            return
        self.client.send_action("join_room", room="blackjack")
        self.stack.setCurrentWidget(self.blackjack)

    def join_roulette(self):
        if not self.client:
            return
        self.client.send_action("join_room", room="roulette")
        self.stack.setCurrentWidget(self.roulette)

    def join_slots(self):
        if not self.client:
            return
        self.client.send_action("join_room", room="slots")
        self.stack.setCurrentWidget(self.slots)

    def join_poker(self):
        if not self.client:
            return
        self.client.send_action("join_room", room="poker")
        self.stack.setCurrentWidget(self.poker)

    def join_crash(self):
        if not self.client: return
        self.client.send_action("join_room", room="crash")
        self.stack.setCurrentWidget(self.crash_screen)


    def leave_room(self):
        if self.client:
            self.client.send_action("leave_room")
        self.stack.setCurrentWidget(self.lobby)

    def send_action(self, action, **kwargs):
        if kwargs.get("amount", 0) >= 10000:
            self.profile.unlock("high_roller", self)
        if self.client:
            self.client.send_action(action, **kwargs)

    def place_roulette_bet(self, bet_type):
        self.send_action("r_bet", bet_type=bet_type, amount=self.active_chip)

    # -- state routing (runs on the GUI thread) ------------------------------
    def on_state(self, state):
        self.game_state = state

        # Check balances for phoenix achievement and welfare
        me = state.get("players", {}).get(self.player_id)
        if me:
            bal = me.get("balance", 0)
            if bal <= 0:
                if self.profile.stats["welfare_count"] == 0 or not getattr(self, "_welfare_flag_locked", False):
                    self.profile.stats["welfare_count"] += 1
                    setattr(self, "_welfare_flag_locked", True)
                self.send_action("claim_welfare")
                self.profile.welfare_claimed = True
            elif bal > 0:
                setattr(self, "_welfare_flag_locked", False)

            if self.profile.welfare_claimed and bal >= 5000:
                self.profile.unlock("phoenix", self)

        s = state.get("state")
        if s == "lobby":
            self.stack.setCurrentWidget(self.lobby)
            self.lobby.update_state(state)
        elif s == "roulette":
            self.stack.setCurrentWidget(self.roulette)
            self.roulette.update_state(state)
        elif s == "slots":
            self.stack.setCurrentWidget(self.slots)
            self.slots.update_state(state)
        elif s == "poker" or ("players" in state and "hands" in state):
            self.stack.setCurrentWidget(self.poker)
            self.poker.update_state(state)
        elif s in ("flying", "crashed") or "crash_point" in state:
            self.stack.setCurrentWidget(self.crash_screen)
            self.crash_screen.update_state(state)
        else:
            self.game_state = state
            self.stack.setCurrentWidget(self.blackjack)
            self.blackjack.update_state(state)

    def show_achievement_notification(self, key):
        names = {
            "high_roller": "High Roller",
            "jackpot_king": "Jackpot King",
            "poker_shark": "Poker Shark",
            "zero_hero": "Zero Hero",
            "natural_21": "Natural 21",
            "phoenix": "Phoenix"
        }
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        name = names.get(key, key)
        self.sound.play("jackpot")

        lbl = QLabel(f"🏆 Achievement Unlocked: {name}!", self)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color:#E9C46A; font-size:22px; font-weight:800; background:rgba(0,0,0,0.8); border: 2px solid #E9C46A; border-radius: 12px; padding: 10px;")
        lbl.adjustSize()
        x = (self.width() - lbl.width()) // 2
        lbl.move(x, 20)
        lbl.show()
        lbl.raise_()

        eff = QGraphicsOpacityEffect(lbl)
        lbl.setGraphicsEffect(eff)

        a_op = QPropertyAnimation(eff, b"opacity", lbl)
        a_op.setDuration(4000)
        a_op.setKeyValueAt(0.0, 0.0)
        a_op.setKeyValueAt(0.1, 1.0)
        a_op.setKeyValueAt(0.8, 1.0)
        a_op.setKeyValueAt(1.0, 0.0)

        a_pos = QPropertyAnimation(lbl, b"pos", lbl)
        a_pos.setDuration(4000)
        a_pos.setStartValue(QPoint(x, -50))
        a_pos.setKeyValueAt(0.1, QPoint(x, 20))
        a_pos.setKeyValueAt(0.8, QPoint(x, 20))
        a_pos.setEndValue(QPoint(x, -50))
        a_pos.setEasingCurve(QEasingCurve.OutCubic)

        a_op.finished.connect(lbl.deleteLater)
        a_op.start(QPropertyAnimation.DeleteWhenStopped)
        a_pos.start(QPropertyAnimation.DeleteWhenStopped)

    # -- keyboard shortcuts --------------------------------------------------
    def _install_shortcuts(self):
        self._shortcuts = []
        for key, fn in [
            ("H", lambda: self._bj_key("hit")),
            ("S", lambda: self._bj_key("stand")),
            ("D", lambda: self._bj_key("double")),
            ("P", lambda: self._bj_key("split")),
            ("Space", self._space_key),
            ("Return", self._enter_key),
            ("Enter", self._enter_key),
        ]:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(fn)
            self._shortcuts.append(sc)
        # Single-key shortcuts must not swallow characters typed into the Start
        # screen's name / IP fields, so disable them while that screen is shown.
        self.stack.currentChanged.connect(self._sync_shortcuts)
        self._sync_shortcuts()

    def _sync_shortcuts(self, *_):
        on_start = self.stack.currentWidget() is self.start
        for sc in self._shortcuts:
            sc.setEnabled(not on_start)

    def _bj_key(self, action):
        if self.stack.currentWidget() is not self.blackjack:
            return
        st = self.game_state or {}
        if st.get("state") == "playing" and st.get("current_player_id") == self.player_id:
            self.send_action(action)

    def _space_key(self):
        w = self.stack.currentWidget()
        if w is self.roulette:
            self.roulette._spin()
        elif w is self.slots:
            self.slots._spin()

    def _enter_key(self):
        w = self.stack.currentWidget()
        st = self.game_state or {}
        if w is self.blackjack:
            s = st.get("state")
            if s == "betting":
                me = st.get("players", {}).get(self.player_id)
                if me and me.get("state") == "betting":
                    self.blackjack._on_bet()
            elif s in ("waiting_for_players", "game_over"):
                self.send_action("start_round")
        elif w is self.slots:
            self.slots._spin()

    def closeEvent(self, event):
        try:
            if self.profile:
                if self.game_state and self.game_state.get("players") and self.player_id in self.game_state["players"]:
                    self.profile.balance = self.game_state["players"][self.player_id]["balance"]
                self.profile.save()
            if self.client is not None:
                self.client.send_action("leave_room")
                sock = getattr(self.client, "socket", None)
                if sock is not None:
                    sock.close()
            if self.server is not None:
                self.server.server.close()
        except Exception:
            pass
        super().closeEvent(event)


def main():
    # Relaunch under pythonw.exe so the black console window disappears.
    if relaunch_without_console():
        return
    # Under pythonw there is no console: stdout/stderr are None, so make print()
    # and any library logging harmless instead of crashing.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    # Quiet Qt multimedia's ffmpeg banner.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")

    # Make Windows use our window icon in the taskbar (not the python.exe icon).
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VirtualCasino.PySide6")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(make_app_icon())
    win = CasinoApp()
    win.resize(1180, 760)
    enable_dark_titlebar(win)   # winId() forces native handle creation
    win.show()
    enable_dark_titlebar(win)   # re-apply now that the native frame exists
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
