import random
import json
import os
import uuid
import socket
import threading
import math
import tkinter as tk
from tkinter import messagebox

HOST_PORT = 5555

# ==========================================
# LOGIC
# ==========================================

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
            "score": self.get_score()
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
            "message": self.message
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
        return {
            "hand": self.hand.to_dict(),
            "show_hidden": self.show_hidden
        }

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
            self.players[player_id] = Player(player_id, name)
            self.player_order.append(player_id)
            return True
        return False

    def remove_player(self, player_id):
        if player_id in self.players:
            del self.players[player_id]
            if player_id in self.player_order:
                self.player_order.remove(player_id)
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
        if self.state != "betting": return False

        player = self.players.get(player_id)
        if not player or player.state != "betting": return False

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
        if self.state != "playing": return
        if self.player_order[self.current_player_idx] != player_id: return

        p = self.players[player_id]
        hand = p.hands[p.current_hand_idx]

        hand.add_card(self.deck.deal())

        if hand.get_score() >= 21:
            if hand.get_score() > 21:
                hand.is_busted = True
            self.next_hand(player_id)

    def stand(self, player_id):
        if self.state != "playing": return
        if self.player_order[self.current_player_idx] != player_id: return

        p = self.players[player_id]
        hand = p.hands[p.current_hand_idx]
        hand.is_stand = True
        self.next_hand(player_id)

    def double_down(self, player_id):
        if self.state != "playing": return
        if self.player_order[self.current_player_idx] != player_id: return

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
        if self.state != "playing": return
        if self.player_order[self.current_player_idx] != player_id: return

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
        if self.state != "playing": return
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
            if not p.hands: continue

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
            "current_player_id": self.player_order[self.current_player_idx] if self.current_player_idx < len(self.player_order) else None
        }


class RouletteGame:
    def __init__(self, server):
        self.server = server
        self.bets = {}
        self.last_result = None
        self.red_nums = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]

    def place_bet(self, pid, amount, bet_type):
        if pid not in self.server.global_players: return
        player_balance = self.server.global_players[pid]["balance"]

        if amount > 0 and player_balance >= amount:
            self.server.global_players[pid]["balance"] -= amount
            if pid not in self.bets: self.bets[pid] = []
            self.bets[pid].append({"type": bet_type, "amount": amount})

    def get_winning_multiplier(self, bet_type, number, color):
        if bet_type is None: return 0
        if bet_type.startswith("number_"):
            n = int(bet_type.split("_")[1])
            if n == number: return 36
        elif bet_type == "half_RED" and color == "red": return 2
        elif bet_type == "half_BLACK" and color == "black": return 2
        elif bet_type == "half_EVEN" and number != 0 and number % 2 == 0: return 2
        elif bet_type == "half_ODD" and number % 2 != 0: return 2
        elif bet_type == "half_1_to_18" and 1 <= number <= 18: return 2
        elif bet_type == "half_19_to_36" and 19 <= number <= 36: return 2
        elif bet_type == "dozen_1" and 1 <= number <= 12: return 3
        elif bet_type == "dozen_2" and 13 <= number <= 24: return 3
        elif bet_type == "dozen_3" and 25 <= number <= 36: return 3
        elif bet_type == "col_1" and number != 0 and number % 3 == 1: return 3
        elif bet_type == "col_2" and number != 0 and number % 3 == 2: return 3
        elif bet_type == "col_3" and number != 0 and number % 3 == 0: return 3

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

        for pid, player_bets in self.bets.items():
            if pid not in self.server.global_players: continue

            total_won = 0
            for bet in player_bets:
                multiplier = self.get_winning_multiplier(bet["type"], number, result_color)
                if multiplier > 0:
                    total_won += bet["amount"] * multiplier

            if total_won > 0:
                self.server.global_players[pid]["balance"] += total_won

        self.bets = {}

    def get_state(self):
        return {
            "state": "roulette",
            "last_result": self.last_result,
            "active_bets": {pid: bets for pid, bets in self.bets.items()}
        }

class SlotsGame:
    def __init__(self, server):
        self.server = server
        self.symbols = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
        self.last_result = {} # {pid: {"reels": [], "message": "", "win": 0}}

    def spin(self, pid, amount):
        if pid not in self.server.global_players: return
        player_balance = self.server.global_players[pid]["balance"]

        if amount > 0 and player_balance >= amount:
            self.server.global_players[pid]["balance"] -= amount

            import random
            reels = [random.choice(self.symbols) for _ in range(3)]
            win_amount = 0
            msg = "No Win. Try Again!"

            if reels[0] == reels[1] == reels[2]:
                if reels[0] == '7️⃣':
                    win_amount = amount * 100
                    msg = f"JACKPOT! 3x 7️⃣ (100x)"
                elif reels[0] == '💎':
                    win_amount = amount * 50
                    msg = f"BIG WIN! 3x 💎 (50x)"
                elif reels[0] == '🔔':
                    win_amount = amount * 25
                    msg = f"WIN! 3x 🔔 (25x)"
                else: # Fruits
                    win_amount = amount * 10
                    msg = f"WIN! 3x {reels[0]} (10x)"
            elif reels[0] == reels[1] or reels[1] == reels[2]:
                win_amount = amount * 2
                match = reels[1]
                msg = f"Small Win! 2x {match} (2x)"

            self.server.global_players[pid]["balance"] += win_amount
            self.last_result[pid] = {"reels": reels, "message": msg, "win": win_amount}

    def get_state(self):
        return {
            "state": "slots",
            "last_result": self.last_result
        }

# ==========================================
# NETWORK
# ==========================================

class Server:
    def __init__(self, host='0.0.0.0'):
        self.host = host
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, HOST_PORT))
        self.server.listen()

        self.global_players = {}
        self.blackjack_game = Game()
        self.blackjack_game.server = self
        self.roulette_game = RouletteGame(self)
        self.slots_game = SlotsGame(self)
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
                if pid not in self.global_players: continue
                room = self.global_players[pid]["room"]

                if room == "blackjack":
                    data = json.dumps({"type": "state", "data": bj_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "slots":
                    s_state = self.slots_game.get_state()
                    s_state["players"] = {p_id: {"name": self.global_players[p_id]["name"], "balance": self.global_players[p_id]["balance"]} for p_id in self.global_players if self.global_players[p_id]["room"] == "slots"}
                    data = json.dumps({"type": "state", "data": s_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "roulette":
                    r_state = self.roulette_game.get_state()
                    r_state["players"] = {p_id: {"name": self.global_players[p_id]["name"], "balance": self.global_players[p_id]["balance"]} for p_id in self.global_players if self.global_players[p_id]["room"] == "roulette"}
                    data = json.dumps({"type": "state", "data": r_state}).encode('utf-8')
                    client.sendall(data + b"\n")
                elif room == "lobby":
                    lobby_state = {
                        "state": "lobby",
                        "players": {p_id: {"name": self.global_players[p_id]["name"], "balance": self.global_players[p_id]["balance"]} for p_id in self.global_players if self.global_players[p_id]["room"] == "lobby"}
                    }
                    data = json.dumps({"type": "state", "data": lobby_state}).encode('utf-8')
                    client.sendall(data + b"\n")
            except:
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
                    if not msg_str: continue
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

                        elif self.global_players[pid]["room"] == "slots":
                            if action == "s_spin":
                                self.slots_game.spin(pid, msg.get("amount", 10))

                        elif self.global_players[pid]["room"] == "roulette":
                            if action == "r_bet":
                                self.roulette_game.place_bet(pid, msg.get("amount", 10), msg.get("bet_type"))
                            elif action == "r_spin":
                                self.roulette_game.spin()

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
        self.socket.connect((self.host, self.port))
        join_msg = json.dumps({"type": "join", "player_id": self.player_id, "name": self.name})
        self.socket.sendall(join_msg.encode('utf-8'))
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def receive_messages(self):
        buffer = ""
        while True:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data: break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip(): continue
                    msg = json.loads(line)
                    if msg["type"] == "state" and self.on_state_update:
                        self.on_state_update(msg["data"])
            except:
                break

    def send_action(self, action, **kwargs):
        msg = {"type": "action", "player_id": self.player_id, "action": action}
        msg.update(kwargs)
        try:
            self.socket.sendall((json.dumps(msg) + "\n").encode('utf-8'))
        except:
            pass

class LocalClient:
    def __init__(self, player_id, name):
        self.player_id = player_id
        self.name = name
        self.server = Server()
        self.on_state_update = None
        self.room = "lobby"
        self.server.global_players[player_id] = {"name": name, "balance": 1000, "room": "lobby"}
        self.server.clients["local_socket_mock"] = player_id

    def connect(self):
        self._trigger_update()

    def _trigger_update(self):
        if not self.on_state_update: return
        if self.room == "lobby":
            state = {
                "state": "lobby",
                "players": {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}}
            }
        elif self.room == "blackjack":
            state = self.server.blackjack_game.get_state()
            state["players"][self.player_id]["balance"] = self.server.global_players[self.player_id]["balance"]
        elif self.room == "slots":
            state = self.server.slots_game.get_state()
            state["players"] = {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}}
        elif self.room == "roulette":
            state = self.server.roulette_game.get_state()
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
        elif self.room == "slots":
            game = self.server.slots_game
            if action == "s_spin":
                game.spin(pid, int(kwargs.get("amount", 10)))
        elif self.room == "roulette":
            game = self.server.roulette_game
            if action == "r_bet":
                game.place_bet(pid, int(kwargs.get("amount", 10)), kwargs.get("bet_type"))
            elif action == "r_spin":
                game.spin()
        self._trigger_update()

# ==========================================
# GUI
# ==========================================

class BlackjackGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Virtual Casino")
        self.root.geometry("1000x700")
        self.root.configure(bg="#006600")

        self.player_id = str(uuid.uuid4())
        self.client = None
        self.server = None
        self.game_state = None
        self.current_view = "lobby"
        self.active_chip = 10
        self.hand_history = []
        self.prev_state = None

        self.setup_start_screen()

    def create_custom_button(self, parent, text, command, btn_type="primary", **kwargs):
        base_bg, hover_bg, fg = "#D4AF37", "#E6C25E", "black"
        if btn_type == "flow":
            base_bg, hover_bg, fg = "#1F1F1F", "#333333", "white"
        elif btn_type == "nav":
            base_bg, hover_bg, fg = "#8B2500", "#A62C00", "white"

        btn = tk.Button(parent, text=text, command=command, bg=base_bg, fg=fg, relief=tk.FLAT, borderwidth=0, cursor="hand2", font=("Arial", 12, "bold"), **kwargs)
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=base_bg))
        return btn

    def setup_start_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        frame = tk.Frame(self.root, bg="#006600")
        frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(frame, text="Virtual Casino", font=("Arial", 36, "bold"), bg="#006600", fg="white").pack(pady=20)
        tk.Label(frame, text="Your Name:", font=("Arial", 14), bg="#006600", fg="white").pack()
        self.name_entry = tk.Entry(frame, font=("Arial", 14))
        self.name_entry.insert(0, "Player")
        self.name_entry.pack(pady=10)

        self.create_custom_button(frame, text="Singleplayer", command=self.start_singleplayer, btn_type="primary", width=20).pack(pady=10)
        tk.Frame(frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=15)
        tk.Label(frame, text="Multiplayer", font=("Arial", 18, "bold"), bg="#006600", fg="white").pack()
        self.create_custom_button(frame, text="Host Game", command=self.host_game, btn_type="flow", width=20).pack(pady=10)
        tk.Label(frame, text="Or Join via IP:", font=("Arial", 14), bg="#006600", fg="white").pack(pady=(10, 5))
        self.ip_entry = tk.Entry(frame, font=("Arial", 14))
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack()
        self.create_custom_button(frame, text="Join Game", command=self.join_game, btn_type="flow", width=20).pack(pady=10)

    def start_singleplayer(self):
        name = self.name_entry.get()
        self.client = LocalClient(self.player_id, name)
        self.client.on_state_update = self.on_state_update
        self.client.connect()
        self.setup_lobby_screen()

    def host_game(self):
        self.server = Server()
        self.server.start()
        self.connect_client("127.0.0.1")

    def join_game(self):
        self.connect_client(self.ip_entry.get())

    def connect_client(self, ip):
        name = self.name_entry.get()
        self.client = Client(ip, self.player_id, name)
        self.client.on_state_update = self.on_state_update
        try:
            self.client.connect()
            self.setup_lobby_screen()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {ip}\n{e}")

    def setup_lobby_screen(self):
        self.current_view = "lobby"
        for widget in self.root.winfo_children():
            widget.destroy()

        self.lobby_frame = tk.Frame(self.root, bg="#1a1a1a")
        self.lobby_frame.pack(expand=True, fill=tk.BOTH)

        top_bar = tk.Frame(self.lobby_frame, bg="#333")
        top_bar.pack(fill=tk.X, pady=0)

        self.lobby_balance_label = tk.Label(top_bar, text="Balance: Loading...", fg="gold", bg="#333", font=("Arial", 16, "bold"))
        self.lobby_balance_label.pack(side=tk.RIGHT, padx=20, pady=10)

        tk.Label(self.lobby_frame, text="Select a Game", font=("Arial", 32, "bold"), fg="white", bg="#1a1a1a").pack(pady=50)
        games_frame = tk.Frame(self.lobby_frame, bg="#1a1a1a")
        games_frame.pack()

        self.create_custom_button(games_frame, text="Blackjack", command=self.join_blackjack, btn_type="flow", width=15, height=3, font=("Arial", 20, "bold")).pack(side=tk.LEFT, padx=20)
        self.create_custom_button(games_frame, text="Roulette", command=self.join_roulette, btn_type="flow", width=15, height=3, font=("Arial", 20, "bold")).pack(side=tk.LEFT, padx=20)

        btn = self.create_custom_button(games_frame, text="Slots Machine", command=self.join_slots, btn_type="flow", width=15, height=3, font=("Arial", 20, "bold"))
        btn.config(bg="#8B008B")
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#FF00FF"))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#8B008B"))
        btn.pack(side=tk.LEFT, padx=20)

    def join_blackjack(self):
        self.client.send_action("join_room", room="blackjack")
        self.current_view = "blackjack"
        self.setup_game_screen()

    def join_slots(self):
        self.client.send_action("join_room", room="slots")
        self.current_view = "slots"
        self.setup_slots_screen()

    def setup_slots_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.s_frame = tk.Frame(self.root, bg="#1a1a1a")
        self.s_frame.pack(expand=True, fill=tk.BOTH)

        top_bar = tk.Frame(self.s_frame, bg="#333")
        top_bar.pack(fill=tk.X)
        self.create_custom_button(top_bar, text="< Back to Lobby", command=self.leave_room, btn_type="nav").pack(side=tk.LEFT, padx=10, pady=5)
        self.s_balance_label = tk.Label(top_bar, text="Balance: $", fg="gold", bg="#333", font=("Arial", 14, "bold"))
        self.s_balance_label.pack(side=tk.RIGHT, padx=20)

        self.s_canvas = tk.Canvas(self.s_frame, bg="#1a1a1a", width=1000, height=450, highlightthickness=0)
        self.s_canvas.pack(pady=10)

        bottom_frame = tk.Frame(self.s_frame, bg="#1a1a1a")
        bottom_frame.pack(fill=tk.X, pady=10)

        self.s_chip_canvas = tk.Canvas(bottom_frame, bg="#1a1a1a", width=800, height=80, highlightthickness=0)
        self.s_chip_canvas.pack(side=tk.LEFT, padx=20)
        self.s_chip_canvas.bind("<Button-1>", self.on_chip_select)

        self.create_custom_button(bottom_frame, text="Spin Slots!", command=self.trigger_slots_spin, btn_type="primary", font=("Arial", 16, "bold")).pack(side=tk.RIGHT, padx=20)
        self.draw_chip_bank(self.s_chip_canvas)

        self.is_slot_spinning = False
        self.draw_slots_machine(['🍒', '🍒', '🍒'], "Welcome! Place your bet and spin.")

    def trigger_slots_spin(self):
        if self.is_slot_spinning: return
        amount = self.active_chip
        if amount <= 0: return

        balance = self.game_state["players"][self.player_id]["balance"] if self.game_state and self.player_id in self.game_state.get("players", {}) else 0
        if amount > balance: return

        self.is_slot_spinning = True
        self.client.send_action("s_spin", amount=amount)
        # The result will arrive via state update, handled in update_ui

    def draw_slots_machine(self, reels, message):
        self.s_canvas.delete("all")

        # Draw Neon Frame
        self.s_canvas.create_rectangle(150, 50, 970, 350, fill="#222", outline="#8B008B", width=10)
        self.s_canvas.create_rectangle(170, 70, 950, 330, fill="#111", outline="#FF00FF", width=4)
        self.s_canvas.create_text(500, 100, text="NEON SLOTS", fill="#FF00FF", font=("Arial", 28, "bold"))

        # Draw 3 Reels
        for i in range(3):
            x = 250 + (i * 250)
            self.s_canvas.create_rectangle(x, 150, x+200, 300, fill="#000", outline="#00FFFF", width=4)
            self.s_canvas.create_text(x+100, 225, text=reels[i], fill="white", font=("Arial", 64))

        # Message
        msg_color = "gold" if "WIN" in message or "JACKPOT" in message else "white"
        self.s_canvas.create_text(500, 380, text=message, fill=msg_color, font=("Arial", 20, "bold"))

    def animate_slots_spin(self, target_reels, message):
        import random
        symbols = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
        spins = 20
        delay = 50

        def roll(step):
            if step < spins:
                current_reels = [
                    random.choice(symbols) if step < 10 else target_reels[0],
                    random.choice(symbols) if step < 15 else target_reels[1],
                    random.choice(symbols) if step < 20 else target_reels[2]
                ]
                self.draw_slots_machine(current_reels, "Spinning...")
                self.root.after(delay, lambda: roll(step+1))
            else:
                self.draw_slots_machine(target_reels, message)
                self.is_slot_spinning = False

        roll(0)

    def join_roulette(self):
        self.client.send_action("join_room", room="roulette")
        self.current_view = "roulette"
        self.setup_roulette_screen()

    def setup_roulette_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.r_frame = tk.Frame(self.root, bg="#005500")
        self.r_frame.pack(expand=True, fill=tk.BOTH)

        top_bar = tk.Frame(self.r_frame, bg="#333")
        top_bar.pack(fill=tk.X)
        self.create_custom_button(top_bar, text="< Back to Lobby", command=self.leave_room, btn_type="nav").pack(side=tk.LEFT, padx=10, pady=5)
        self.r_balance_label = tk.Label(top_bar, text="Balance: $", fg="gold", bg="#333", font=("Arial", 14, "bold"))
        self.r_balance_label.pack(side=tk.RIGHT, padx=20)

        self.r_canvas = tk.Canvas(self.r_frame, bg="#006600", width=1000, height=450, highlightthickness=0)
        self.r_canvas.pack(pady=10)

        bottom_frame = tk.Frame(self.r_frame, bg="#005500")
        bottom_frame.pack(fill=tk.X, pady=10)

        self.r_chip_canvas = tk.Canvas(bottom_frame, bg="#005500", width=800, height=80, highlightthickness=0)
        self.r_chip_canvas.pack(side=tk.LEFT, padx=20)
        self.r_chip_canvas.bind("<Button-1>", self.on_chip_select)

        self.create_custom_button(bottom_frame, text="Spin Wheel!", command=self.trigger_spin, btn_type="primary", font=("Arial", 16, "bold")).pack(side=tk.RIGHT, padx=20)
        self.draw_chip_bank(self.r_chip_canvas)

        self.r_canvas.bind("<Button-1>", self.on_roulette_click)
        self.r_canvas.bind("<Motion>", self.on_roulette_hover)
        self.r_canvas.bind("<Leave>", self.on_roulette_leave)
        self.roulette_grid_coords = {}
        self.hovered_bet_key = None
        self.is_spinning = False
        self.spin_angle = 0

    def get_available_chips(self):
        balance = 1000
        if getattr(self, 'game_state', None) and "players" in self.game_state and self.player_id in self.game_state["players"]:
            balance = self.game_state["players"][self.player_id]["balance"]

        all_denoms = [1, 5, 10, 25, 100, 500, 1000, 5000, 10000]
        all_colors = ["#FFFFFF", "#FF0000", "#0000FF", "#008000", "#1a1a1a", "#800080", "#00FFFF", "#FF00FF", "#D4AF37"]

        available = [(d, c) for d, c in zip(all_denoms, all_colors) if d <= balance or d == 1]
        return [x[0] for x in available], [x[1] for x in available]

    def draw_chip_bank(self, canvas):
        canvas.delete("all")
        denoms, colors = self.get_available_chips()

        for i, (denom, color) in enumerate(zip(denoms, colors)):
            x = 40 + (i * 80)
            y = 40

            if denom == self.active_chip:
                canvas.create_oval(x-25, y-25, x+25, y+25, outline="yellow", width=4)

            text_color = "black" if denom == 1 else "white"
            canvas.create_oval(x-20, y-20, x+20, y+20, fill=color, outline="white", width=2)
            canvas.create_oval(x-15, y-15, x+15, y+15, outline="white", width=1)
            canvas.create_text(x, y, text=str(denom), fill=text_color, font=("Arial", 10, "bold"))


    def animate_chip_throw(self, canvas, start_x, start_y, end_x, end_y, denom, color):
        # Create a temporary chip
        chip_id = canvas.create_oval(start_x-15, start_y-15, start_x+15, start_y+15, fill=color, outline="white", width=2, tags="flying_chip")
        text_id = canvas.create_text(start_x, start_y, text=str(denom), fill=("black" if denom==1 else "white"), font=("Arial", 8, "bold"), tags="flying_chip")

        steps = 15
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps

        def move(step):
            if step < steps:
                canvas.move(chip_id, dx, dy)
                canvas.move(text_id, dx, dy)
                self.root.after(20, lambda: move(step+1))
            else:
                canvas.delete(chip_id)
                canvas.delete(text_id)
                self.update_ui()

        move(0)

    def on_chip_select(self, event):
        x = event.x
        denoms, _ = self.get_available_chips()
        idx = int((x - 15) // 80)
        if 0 <= idx < len(denoms):
            self.active_chip = denoms[idx]
            if hasattr(self, 'r_chip_canvas'): self.draw_chip_bank(self.r_chip_canvas)
            if hasattr(self, 'bj_chip_canvas'): self.draw_chip_bank(self.bj_chip_canvas)
            if hasattr(self, 's_chip_canvas'): self.draw_chip_bank(self.s_chip_canvas)

    def trigger_spin(self):
        if self.is_spinning: return
        self.is_spinning = True
        self.spin_angle = 0
        self.client.send_action("r_spin")
        self.animate_spin()

    def animate_spin(self):
        if not self.is_spinning: return
        self.spin_angle += 20
        if self.spin_angle >= 360 * 3:
            self.is_spinning = False
            self.update_ui()
            return

        self.r_canvas.delete("ball")
        rad = math.radians(self.spin_angle)
        ball_x = 200 + (125 * math.cos(rad))
        ball_y = 225 - (125 * math.sin(rad))
        self.r_canvas.create_oval(ball_x-5, ball_y-5, ball_x+5, ball_y+5, fill="white", tags="ball")
        self.root.after(30, self.animate_spin)

    def draw_roulette_table(self):
        self.r_canvas.delete("all")
        self.r_canvas.create_rectangle(0, 0, 1000, 450, outline="#5c3a21", width=20)

        wheel_cx, wheel_cy = 200, 225
        r_outer, r_inner = 170, 110
        self.r_canvas.create_oval(wheel_cx - r_outer, wheel_cy - r_outer, wheel_cx + r_outer, wheel_cy + r_outer, outline="#b8860b", width=10, fill="#2a1b12")

        wheel_nums = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        angle_step = 360 / 37
        red_nums = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]

        for i, num in enumerate(wheel_nums):
            start_angle = i * angle_step
            color = "#008000" if num == 0 else ("#cc0000" if num in red_nums else "#1a1a1a")
            self.r_canvas.create_arc(wheel_cx - r_outer, wheel_cy - r_outer, wheel_cx + r_outer, wheel_cy + r_outer, start=start_angle, extent=angle_step, fill=color, outline="white")
            mid_angle = math.radians(start_angle + (angle_step / 2))
            text_x = wheel_cx + (140 * math.cos(mid_angle))
            text_y = wheel_cy - (140 * math.sin(mid_angle))
            self.r_canvas.create_text(text_x, text_y, text=str(num), fill="white", font=("Arial", 8, "bold"))

        self.r_canvas.create_oval(wheel_cx - r_inner, wheel_cy - r_inner, wheel_cx + r_inner, wheel_cy + r_inner, outline="#b8860b", width=4, fill="#1a1a1a")
        self.r_canvas.create_text(wheel_cx, wheel_cy, text="ROULETTE", fill="#b8860b", font=("Arial", 16, "bold"))

        grid_start_x, grid_start_y, cell_w, cell_h = 420, 50, 35, 50
        zx1, zy1, zx2, zy2 = grid_start_x, grid_start_y, grid_start_x + 40, grid_start_y + (cell_h * 3)
        self.r_canvas.create_rectangle(zx1, zy1, zx2, zy2, fill="#008000", outline="white")
        self.r_canvas.create_text((zx1+zx2)/2, (zy1+zy2)/2, text="0", fill="white", font=("Arial", 20, "bold"))
        self.roulette_grid_coords["number_0"] = (zx1, zy1, zx2, zy2)

        num = 1
        for col in range(12):
            for row in range(2, -1, -1):
                x1 = grid_start_x + 40 + (col * cell_w)
                y1 = grid_start_y + (row * cell_h)
                x2, y2 = x1 + cell_w, y1 + cell_h
                color = "#cc0000" if num in red_nums else "#1a1a1a"
                self.r_canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="white")
                self.r_canvas.create_text(x1 + cell_w/2, y1 + cell_h/2, text=str(num), fill="white", font=("Arial", 14, "bold"))
                self.roulette_grid_coords[f"number_{num}"] = (x1, y1, x2, y2)
                num += 1

        col_x = grid_start_x + 40 + (12 * cell_w)
        for row in range(2, -1, -1):
            x1, y1, x2, y2 = col_x, grid_start_y + (row * cell_h), col_x + 50, grid_start_y + (row * cell_h) + cell_h
            self.r_canvas.create_rectangle(x1, y1, x2, y2, fill="#005500", outline="white")
            self.r_canvas.create_text((x1+x2)/2, (y1+y2)/2, text="2 to 1", fill="white", font=("Arial", 10, "bold"))
            self.roulette_grid_coords[f"col_{3-row}"] = (x1, y1, x2, y2)

        ox1, oy1 = grid_start_x + 40, grid_start_y + (cell_h * 3)
        for i, text in enumerate(["1st 12", "2nd 12", "3rd 12"]):
            x1, x2, y2 = ox1 + (i * cell_w * 4), ox1 + (i * cell_w * 4) + (cell_w * 4), oy1 + 40
            self.r_canvas.create_rectangle(x1, oy1, x2, y2, fill="#005500", outline="white")
            self.r_canvas.create_text((x1+x2)/2, (oy1+y2)/2, text=text, fill="white", font=("Arial", 12, "bold"))
            self.roulette_grid_coords[f"dozen_{i+1}"] = (x1, oy1, x2, y2)

        oy2 = oy1 + 40
        halves = [("1 to 18", "#005500"), ("EVEN", "#005500"), ("RED", "#cc0000"), ("BLACK", "#1a1a1a"), ("ODD", "#005500"), ("19 to 36", "#005500")]
        for i, (text, color) in enumerate(halves):
            x1, x2, y2 = ox1 + (i * cell_w * 2), ox1 + (i * cell_w * 2) + (cell_w * 2), oy2 + 40
            self.r_canvas.create_rectangle(x1, oy2, x2, y2, fill=color, outline="white")
            self.r_canvas.create_text((x1+x2)/2, (oy2+y2)/2, text=text, fill="white", font=("Arial", 12, "bold"))
            self.roulette_grid_coords[f"half_{text.replace(' ', '_')}"] = (x1, oy2, x2, y2)

        if self.game_state.get("last_result") and not getattr(self, 'is_spinning', False):
            res = self.game_state["last_result"]
            win_num = res['number']
            if win_num in wheel_nums:
                idx = wheel_nums.index(win_num)
                start_angle = idx * angle_step
                mid_angle = math.radians(start_angle + (angle_step / 2))
                ball_x = wheel_cx + (125 * math.cos(mid_angle))
                ball_y = wheel_cy - (125 * math.sin(mid_angle))
                self.r_canvas.create_oval(ball_x-6, ball_y-6, ball_x+6, ball_y+6, fill="white", outline="black", width=1, tags="ball")

    def on_roulette_hover(self, event):
        x, y = event.x, event.y
        new_hover = None
        for bet_key, (x1, y1, x2, y2) in self.roulette_grid_coords.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                new_hover = bet_key
                break
        if new_hover != self.hovered_bet_key:
            self.hovered_bet_key = new_hover
            self.update_ui()

    def on_roulette_leave(self, event):
        if self.hovered_bet_key is not None:
            self.hovered_bet_key = None
            self.update_ui()

    def on_roulette_click(self, event):
        x, y = event.x, event.y
        amount = self.active_chip
        if amount <= 0: return

        for bet_key, (x1, y1, x2, y2) in self.roulette_grid_coords.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.client.send_action("r_bet", bet_type=bet_key, amount=amount)
                denoms, colors = self.get_available_chips()
                color = colors[denoms.index(amount)] if amount in denoms else "blue"
                self.animate_chip_throw(self.r_canvas, x, 450, x, y, amount, color)
                break

    def leave_room(self):
        self.client.send_action("leave_room")
        self.setup_lobby_screen()

    def on_state_update(self, state):
        self.game_state = state
        self.root.after(0, self.update_ui)

    def setup_game_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.top_frame = tk.Frame(self.root, bg="#006600")
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        self.create_custom_button(self.top_frame, text="< Back to Lobby", command=self.leave_room, btn_type="nav").pack(side=tk.LEFT, padx=10)

        self.canvas = tk.Canvas(self.root, bg="#006600", width=1000, height=500, highlightthickness=0)
        self.canvas.pack(expand=True, fill=tk.BOTH)

        self.bottom_frame = tk.Frame(self.root, bg="#006600")
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

        self.balance_label = tk.Label(self.top_frame, text="", bg="#006600", fg="white", font=("Arial", 14, "bold"))
        self.balance_label.pack(side=tk.LEFT, padx=20)

        self.status_label = tk.Label(self.top_frame, text="Waiting for state...", bg="#006600", fg="yellow", font=("Arial", 14))
        self.status_label.pack(side=tk.RIGHT, padx=20)

        self.bj_chip_canvas = tk.Canvas(self.bottom_frame, bg="#006600", width=800, height=80, highlightthickness=0)
        self.bj_chip_canvas.bind("<Button-1>", self.on_chip_select)
        self.draw_chip_bank(self.bj_chip_canvas)

        self.bet_button = self.create_custom_button(self.bottom_frame, text="Place Bet", command=self.on_bj_bet, btn_type="primary", font=("Arial", 16, "bold"))

        self.hit_btn = self.create_custom_button(self.bottom_frame, text="Hit", command=lambda: self.client.send_action("hit"), btn_type="flow")
        self.stand_btn = self.create_custom_button(self.bottom_frame, text="Stand", command=lambda: self.client.send_action("stand"), btn_type="flow")
        self.double_btn = self.create_custom_button(self.bottom_frame, text="Double", command=lambda: self.client.send_action("double"), btn_type="flow")
        self.split_btn = self.create_custom_button(self.bottom_frame, text="Split", command=lambda: self.client.send_action("split"), btn_type="flow")
        self.ins_btn = self.create_custom_button(self.bottom_frame, text="Insurance", command=lambda: self.client.send_action("insurance"), btn_type="flow")
        self.start_round_btn = self.create_custom_button(self.bottom_frame, text="Start New Round", command=lambda: self.client.send_action("start_round"), btn_type="flow")

    def on_bj_bet(self):
        amount = getattr(self, 'active_chip', 10)
        self.client.send_action("bet", amount=amount)
        denoms, colors = self.get_available_chips()
        color = colors[denoms.index(amount)] if amount in denoms else "blue"
        self.animate_chip_throw(self.canvas, 500, 500, 500, 250, amount, color)

    def draw_table(self):
        self.canvas.create_rectangle(0, 0, 1000, 500, fill="#3d2314", outline="", tags="bg_table")
        self.canvas.create_oval(50, -250, 950, 480, fill="#006600", outline="#b8860b", width=10, tags="bg_table")
        self.canvas.create_text(500, 170, text="BLACKJACK PAYS 3 TO 2", fill="#b8860b", font=("Arial", 16, "bold"), tags="bg_table")
        self.canvas.create_text(500, 195, text="Dealer must draw to 16, and stand on all 17s", fill="#b8860b", font=("Arial", 12), tags="bg_table")
        self.canvas.create_arc(200, -100, 800, 300, start=180, extent=180, style=tk.ARC, outline="#b8860b", width=2, tags="bg_table")
        self.canvas.create_text(500, 280, text="INSURANCE PAYS 2 TO 1", fill="#b8860b", font=("Arial", 14, "bold"), tags="bg_table")

    def draw_chips(self, x, y, amount):
        if amount <= 0: return
        chip_denominations = [
            (10000, "#D4AF37"), (5000, "#FF00FF"), (1000, "#00FFFF"),
            (500, "#800080"), (100, "#1a1a1a"), (25, "#008000"),
            (10, "#0000FF"), (5, "#FF0000"), (1, "#FFFFFF")
        ]
        chips_to_draw = []
        remaining = amount
        for denom, color in chip_denominations:
            count = int(remaining // denom)
            for _ in range(count): chips_to_draw.append((denom, color))
            remaining %= denom

        if len(chips_to_draw) > 10: chips_to_draw = chips_to_draw[:10]
        chips_to_draw.reverse()

        chip_width, chip_height, offset_y = 40, 20, 5
        for i, (denom, color) in enumerate(chips_to_draw):
            cy = y - (i * offset_y)
            text_color = "black" if denom == 1 else "white"
            self.canvas.create_oval(x, cy, x + chip_width, cy + chip_height, fill=color, outline="black", width=1, tags="dynamic")
            self.canvas.create_oval(x + 5, cy + 3, x + chip_width - 5, cy + chip_height - 3, outline="black", width=1, tags="dynamic")
            self.canvas.create_line(x+5, cy+chip_height/2, x+10, cy+chip_height/2, fill="white", width=2, tags="dynamic")
            self.canvas.create_line(x+chip_width-10, cy+chip_height/2, x+chip_width-5, cy+chip_height/2, fill="white", width=2, tags="dynamic")
            self.canvas.create_text(x + chip_width/2, cy + chip_height/2, text=str(denom), fill=text_color, font=("Arial", 8, "bold"), tags=("dynamic", "chip_text"))

        self.canvas.tag_raise("chip_text")

    def draw_card(self, x, y, card_dict, hidden=False):
        width, height = 65, 95
        self.canvas.create_rectangle(x+3, y+3, x+width+3, y+height+3, fill="#111111", outline="", tags="dynamic")
        if hidden:
            self.canvas.create_rectangle(x, y, x+width, y+height, fill="#003366", outline="white", width=2, tags="dynamic")
            for i in range(5, width-5, 10):
                self.canvas.create_line(x+i, y+5, x+i, y+height-5, fill="#005599", width=2, tags="dynamic")
            self.canvas.create_oval(x+15, y+30, x+width-15, y+height-30, outline="white", width=2, tags="dynamic")
        else:
            self.canvas.create_rectangle(x, y, x+width, y+height, fill="white", outline="#333333", width=1, tags="dynamic")
            color = "#cc0000" if card_dict["suit"] in ['♥', '♦'] else "black"
            self.canvas.create_text(x+12, y+15, text=card_dict["rank"], fill=color, font=("Arial", 12, "bold"), tags="dynamic")
            self.canvas.create_text(x+12, y+30, text=card_dict["suit"], fill=color, font=("Arial", 12), tags="dynamic")
            self.canvas.create_text(x+width/2, y+height/2, text=card_dict["suit"], fill=color, font=("Arial", 28), tags="dynamic")
            self.canvas.create_text(x+width-12, y+height-30, text=card_dict["suit"], fill=color, font=("Arial", 12), tags="dynamic")
            self.canvas.create_text(x+width-12, y+height-15, text=card_dict["rank"], fill=color, font=("Arial", 12, "bold"), tags="dynamic")

    def update_ui(self):
        if not self.game_state: return

        state = self.game_state["state"]
        players = self.game_state["players"]
        me = players.get(self.player_id)

        if self.current_view == "lobby":
            if me and hasattr(self, 'lobby_balance_label'):
                self.lobby_balance_label.config(text=f"Balance: ${me['balance']}")
            return

        if self.current_view == "slots":
            if me and hasattr(self, 's_balance_label'):
                self.s_balance_label.config(text=f"Balance: ${me['balance']}")

            if self.game_state.get("last_result") and str(self.player_id) in self.game_state["last_result"]:
                res = self.game_state["last_result"][str(self.player_id)]
                if getattr(self, 'is_slot_spinning', False):
                    self.animate_slots_spin(res["reels"], res["message"])
            return

        if self.current_view == "roulette":
            if me and hasattr(self, 'r_balance_label'):
                self.r_balance_label.config(text=f"Balance: ${me['balance']}")
            if not getattr(self, 'is_spinning', False):
                self.draw_roulette_table()
                if getattr(self, 'hovered_bet_key', None) and self.hovered_bet_key in self.roulette_grid_coords:
                    x1, y1, x2, y2 = self.roulette_grid_coords[self.hovered_bet_key]
                    self.r_canvas.create_rectangle(x1, y1, x2, y2, outline="yellow", width=4, tags="hover_box")
                if self.game_state.get("last_result"):
                    res = self.game_state["last_result"]
                    self.r_canvas.create_text(200, 225, text=str(res['number']), fill="white", font=("Arial", 36, "bold"))
                    self.r_canvas.create_text(200, 260, text=res['color'].upper(), fill=res['color'], font=("Arial", 14, "bold"))
                    if f"number_{res['number']}" in self.roulette_grid_coords:
                        x1, y1, x2, y2 = self.roulette_grid_coords[f"number_{res['number']}"]
                        self.r_canvas.create_rectangle(x1, y1, x2, y2, outline="yellow", width=4)
                if "active_bets" in self.game_state:
                    for pid, player_bets in self.game_state["active_bets"].items():
                        for bet in player_bets:
                            if bet["type"] in self.roulette_grid_coords:
                                x1, y1, x2, y2 = self.roulette_grid_coords[bet["type"]]
                                cx, cy = (x1+x2)/2, (y1+y2)/2
                                self.r_canvas.create_oval(cx-15, cy-15, cx+15, cy+15, fill="blue", outline="white", width=2)
                                self.r_canvas.create_text(cx, cy, text=str(bet["amount"]), fill="white", font=("Arial", 8, "bold"))
            return

        if self.current_view != "blackjack": return

        self.canvas.delete("dynamic")
        self.draw_table()

        for widget in self.bottom_frame.winfo_children(): widget.pack_forget()

        if me: self.balance_label.config(text=f"{me['name']} | Balance: ${me['balance']}")
        if state in ["waiting_for_players", "game_over"]: self.start_round_btn.pack(side=tk.LEFT, padx=10)

        if state == "betting":
            if me and me["state"] == "betting":
                self.canvas.create_text(500, 250, text="Place your bet", fill="white", font=("Arial", 24, "bold"), tags="dynamic")
                self.bj_chip_canvas.pack(side=tk.LEFT, padx=10)
                self.draw_chip_bank(self.bj_chip_canvas)
                self.bet_button.pack(side=tk.LEFT, padx=10)
            else:
                self.canvas.create_text(500, 250, text="Waiting for others to bet...", fill="white", font=("Arial", 24), tags="dynamic")
        else:
            if hasattr(self, 'bj_chip_canvas'): self.bj_chip_canvas.pack_forget()
            if hasattr(self, 'bet_button'): self.bet_button.pack_forget()

        if state in ["playing", "dealer_turn", "game_over"]:
            self.canvas.create_text(500, 30, text="Dealer", fill="white", font=("Arial", 16), tags="dynamic")
            dealer = self.game_state["dealer"]
            dealer_cards = dealer["hand"]["cards"]
            dealer_x = 500 - (len(dealer_cards) * 35)

            for i, c in enumerate(dealer_cards):
                hidden = (i == 1 and not dealer["show_hidden"])
                self.draw_card(dealer_x + i*70, 50, c, hidden)

            if dealer["show_hidden"]:
                self.canvas.create_text(500, 160, text=f"Score: {dealer['hand']['score']}", fill="white", tags="dynamic")

            num_players = len(self.game_state["player_order"])
            if num_players > 0:
                spacing = 1000 / (num_players + 1)
                for i, pid in enumerate(self.game_state["player_order"]):
                    p = players[pid]
                    center_x = spacing * (i + 1)

                    is_current = (self.game_state["current_player_id"] == pid and state == "playing")
                    if is_current:
                        self.canvas.create_rectangle(center_x-120, 200, center_x+120, 450, outline="yellow", width=3, tags="dynamic")
                        adv_x, adv_y = 850, 150
                        self.canvas.create_rectangle(adv_x, adv_y, adv_x+130, adv_y+80, fill="#1a1a1a", outline="#b8860b", width=2, tags="dynamic")
                        self.canvas.create_text(adv_x+65, adv_y+20, text="🤖 AI Advisor", fill="#b8860b", font=("Arial", 12, "bold"), tags="dynamic")

                        suggestion = "STAND"
                        try:
                            if p.get("hands") and len(p["hands"]) > 0 and dealer.get("hand") and dealer["hand"].get("cards"):
                                player_score = p["hands"][p["current_hand_idx"]]["score"]
                                d_val = Card.from_dict(dealer["hand"]["cards"][0]).get_value()
                                suggestion = "HIT" if player_score < 17 else "STAND"
                        except: pass
                        self.canvas.create_text(adv_x+65, adv_y+50, text=f"Suggested: {suggestion}", fill="white", font=("Arial", 10), tags="dynamic")

                    self.canvas.create_text(center_x, 220, text=f"{p['name']} (${p['balance']})", fill="white", font=("Arial", 14, "bold"), tags="dynamic")

                    if p["message"]:
                        msg_color = "gold" if "Win" in p["message"] or "Blackjack" in p["message"] else ("red" if "Lose" in p["message"] or "Bust" in p["message"] else "white")
                        self.canvas.create_text(center_x, 350, text=p["message"], fill=msg_color, font=("Arial", 28, "bold"), tags=("dynamic", "result_msg"))

                    for h_idx, h in enumerate(p["hands"]):
                        hy = 250 + (h_idx * 110)
                        self.canvas.create_text(center_x, hy-15, text=f"Bet: ${h['bet']} | Score: {h['score']}", fill="white", tags="dynamic")
                        if h['bet'] > 0: self.draw_chips(center_x - 100, hy + 40, h['bet'])
                        cards_x = center_x - (len(h["cards"]) * 20)
                        for c_idx, c in enumerate(h["cards"]):
                            self.draw_card(cards_x + c_idx*40, hy, c)

            if self.prev_state in ["playing", "dealer_turn"] and state == "game_over":
                if me and me.get("message"):
                    msg = me.get("message", "").strip()
                    outcome = "Win" if "Win" in msg or "Blackjack" in msg else ("Loss" if "Lose" in msg or "Bust" in msg else "Push")
                    self.hand_history.insert(0, outcome)
                    self.hand_history = self.hand_history[:5]

            self.prev_state = state
            hist_x, hist_y = 20, 150
            self.canvas.create_rectangle(hist_x, hist_y, hist_x+100, hist_y+150, fill="#1a1a1a", outline="#b8860b", width=2, tags="dynamic")
            self.canvas.create_text(hist_x+50, hist_y+20, text="HISTORY", fill="#b8860b", font=("Arial", 10, "bold"), tags="dynamic")
            for i, res in enumerate(self.hand_history):
                color = "green" if res == "Win" else ("red" if res == "Loss" else "white")
                self.canvas.create_text(hist_x+50, hist_y+50 + (i*20), text=res, fill=color, font=("Arial", 10, "bold"), tags="dynamic")

            if state == "playing" and self.game_state["current_player_id"] == self.player_id:
                self.hit_btn.pack(side=tk.LEFT, padx=5)
                self.stand_btn.pack(side=tk.LEFT, padx=5)
                self.double_btn.pack(side=tk.LEFT, padx=5)
                self.split_btn.pack(side=tk.LEFT, padx=5)
                self.ins_btn.pack(side=tk.LEFT, padx=5)

        self.canvas.tag_lower("bg_table")
        self.canvas.tag_raise("dynamic")
        if self.canvas.find_withtag("result_msg"): self.canvas.tag_raise("result_msg")

def main():
    root = tk.Tk()
    app = BlackjackGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()