# Premium UI Update Applied
import random
import json
import os
import uuid
import socket
import threading
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
        self.bets = {} # {pid: [{"type": "number_5", "amount": 10}, ...]}
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
        import random
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

# ==========================================
# NETWORK
# ==========================================


class Server:
    def __init__(self, host='0.0.0.0'):
        self.host = host
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, HOST_PORT))
        self.server.listen()

        self.global_players = {} # {pid: {"name": name, "balance": 1000, "room": "lobby"}}
        self.blackjack_game = Game()
        self.blackjack_game.server = self
        self.roulette_game = RouletteGame(self)
        # self.roulette_game = RouletteGame(self) # to be implemented

        self.clients = {} # {client_socket: pid}

    def start(self):
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            client, address = self.server.accept()
            threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()

    def broadcast_state(self):
        # We broadcast the blackjack state to all clients in blackjack room,
        # and a general lobby state to lobby clients
        bj_state = self.blackjack_game.get_state()

        # Override the players list in bj_state to use global balance
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
                elif room == "lobby":
                    lobby_state = {
                        "state": "lobby",
                        "players": {pid: {"name": self.global_players[pid]["name"], "balance": self.global_players[pid]["balance"]}}
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

                # Register globally if new
                if player_id not in self.global_players:
                    self.global_players[player_id] = {"name": name, "balance": 1000, "room": "lobby"}

                self.global_players[player_id]["room"] = "lobby"
                self.broadcast_state()

            while True:
                data = client.recv(1024)
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
                                # update local game balance
                                self.blackjack_game.players[pid].balance = self.global_players[pid]["balance"]

                        elif action == "leave_room":
                            room_name = self.global_players[pid]["room"]
                            if room_name == "blackjack":
                                self.blackjack_game.remove_player(pid)
                            self.global_players[pid]["room"] = "lobby"

                        # Route Blackjack actions
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

                            # broadcast roulette state is handled below

                            # Sync balances back to global from game
                            for p in self.blackjack_game.players.values():
                                self.global_players[p.player_id]["balance"] = p.balance

                        self.broadcast_state()
        except Exception as e:
            print("Client error:", e)
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
        elif self.room == "roulette":
            state = self.server.roulette_game.get_state()
            state["players"] = {self.player_id: {"name": self.name, "balance": self.server.global_players[self.player_id]["balance"]}}
        else:
            state = {"state": "unknown", "players": {}}

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

        elif self.room == "roulette":
            game = self.server.roulette_game
            if action == "r_bet":
                amount = int(kwargs.get("amount", 10))
                bet_type = kwargs.get("bet_type")
                game.place_bet(pid, amount, bet_type)
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
        self.active_chip = 10 # Default chip selection
        self.hand_history = []
        self.prev_state = None
        self.animated_cards = set()
        self.animating_count = 0

        self.setup_start_screen()

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

        tk.Button(frame, text="Singleplayer", font=("Arial", 16), command=self.start_singleplayer, width=20, bg="#228B22", fg="white").pack(pady=10)

        tk.Frame(frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=15)
        tk.Label(frame, text="Multiplayer", font=("Arial", 18, "bold"), bg="#006600", fg="white").pack()

        tk.Button(frame, text="Host Game", font=("Arial", 16), command=self.host_game, width=20).pack(pady=10)

        tk.Label(frame, text="Or Join via IP:", font=("Arial", 14), bg="#006600", fg="white").pack(pady=(10, 5))
        self.ip_entry = tk.Entry(frame, font=("Arial", 14))
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack()
        tk.Button(frame, text="Join Game", font=("Arial", 16), command=self.join_game, width=20).pack(pady=10)

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
        ip = self.ip_entry.get()
        self.connect_client(ip)

    def connect_client(self, ip):
        name = self.name_entry.get()
        self.client = Client(ip, self.player_id, name)
        self.client.on_state_update = self.on_state_update
        try:
            self.client.connect()
            self.setup_game_screen()
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

        tk.Button(games_frame, text="Blackjack", font=("Arial", 20), bg="#006600", fg="white", width=15, height=3, command=self.join_blackjack).pack(side=tk.LEFT, padx=20)
        tk.Button(games_frame, text="Roulette", font=("Arial", 20), bg="#660000", fg="white", width=15, height=3, command=self.join_roulette).pack(side=tk.LEFT, padx=20)

    def join_blackjack(self):
        self.client.send_action("join_room", room="blackjack")
        self.current_view = "blackjack"
        self.setup_game_screen()

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
        tk.Button(top_bar, text="⬅ Lobby", command=self.leave_room, bg="#D4AF37", fg="black", relief=tk.RAISED, borderwidth=3, font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10, pady=5)
        self.r_balance_label = tk.Label(top_bar, text="Balance: $", fg="gold", bg="#333", font=("Arial", 14, "bold"))
        self.r_balance_label.pack(side=tk.RIGHT, padx=20)

        self.r_canvas = tk.Canvas(self.r_frame, bg="#006600", width=1000, height=450, highlightthickness=0)
        self.r_canvas.pack(pady=10)

        bottom_frame = tk.Frame(self.r_frame, bg="#005500")
        bottom_frame.pack(fill=tk.X, pady=10)

        # Chip Bank Canvas
        self.r_chip_canvas = tk.Canvas(bottom_frame, bg="#005500", width=800, height=80, highlightthickness=0)
        self.r_chip_canvas.pack(side=tk.LEFT, padx=20)
        self.r_chip_canvas.bind("<Button-1>", self.on_chip_select)

        tk.Button(bottom_frame, text="Spin Wheel!", bg="gold", fg="black", font=("Arial", 16, "bold"), command=self.trigger_spin).pack(side=tk.RIGHT, padx=20)
        self.draw_chip_bank(self.r_chip_canvas)

        self.r_canvas.bind("<Button-1>", self.on_roulette_click)
        self.r_canvas.bind("<Motion>", self.on_roulette_hover)
        self.r_canvas.bind("<Leave>", self.on_roulette_leave)
        self.roulette_grid_coords = {}
        self.hovered_bet_key = None
        self.is_spinning = False
        self.spin_angle = 0

    def draw_chip_bank(self, canvas):
        canvas.delete("all")
        all_denoms = [1, 5, 10, 25, 100, 500, 1000, 5000, 10000]
        all_colors = ["#FFFFFF", "#FF0000", "#0000FF", "#008000", "#1a1a1a", "#800080", "#00FFFF", "#FF00FF", "#D4AF37"]

        # Determine player balance
        balance = 0
        if self.game_state and "players" in self.game_state and self.player_id in self.game_state["players"]:
            balance = self.game_state["players"][self.player_id]["balance"]

        # Filter available denoms
        denoms = []
        colors = []
        for d, c in zip(all_denoms, all_colors):
            if d <= balance or d == 1: # Always show at least 1
                denoms.append(d)
                colors.append(c)

        for i, (denom, color) in enumerate(zip(denoms, colors)):
            x = 40 + (i * 80)
            y = 40

            # Highlight active chip
            if denom == self.active_chip:
                canvas.create_oval(x-25, y-25, x+25, y+25, outline="yellow", width=4)

            text_color = "black" if denom == 1 else "white"
            canvas.create_oval(x-20, y-20, x+20, y+20, fill=color, outline="white", width=2, tags=f"chip_{denom}")
            canvas.create_oval(x-15, y-15, x+15, y+15, outline="white", width=1, tags=f"chip_{denom}")
            canvas.create_text(x, y, text=str(denom), fill=text_color, font=("Arial", 10, "bold"), tags=f"chip_{denom}")

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
                # the actual state update will draw the final chip
                self.update_ui()

        move(0)

    def on_chip_select(self, event):
        x = event.x
        all_denoms = [1, 5, 10, 25, 100, 500, 1000, 5000, 10000]

        balance = 0
        if getattr(self, 'game_state', None) and "players" in self.game_state and self.player_id in self.game_state["players"]:
            balance = self.game_state["players"][self.player_id]["balance"]

        denoms = [d for d in all_denoms if d <= balance or d == 1]

        idx = int((x - 15) // 80)
        if 0 <= idx < len(denoms):
            self.active_chip = denoms[idx]
            if hasattr(self, 'r_chip_canvas'): self.draw_chip_bank(self.r_chip_canvas)
            if hasattr(self, 'bj_chip_canvas'): self.draw_chip_bank(self.bj_chip_canvas)

    def trigger_spin(self):
        if self.is_spinning: return
        self.is_spinning = True
        self.spin_angle = 0
        self.client.send_action("r_spin")
        self.animate_spin()

    def animate_spin(self):
        if not self.is_spinning: return
        self.spin_angle += 20
        if self.spin_angle >= 360 * 3: # 3 full rotations
            self.is_spinning = False
            self.update_ui() # Force final draw
            return

        # Draw spinning ball
        self.r_canvas.delete("ball")
        import math
        rad = math.radians(self.spin_angle)
        ball_x = 200 + (125 * math.cos(rad))
        ball_y = 225 - (125 * math.sin(rad))
        self.r_canvas.create_oval(ball_x-5, ball_y-5, ball_x+5, ball_y+5, fill="white", tags="ball")

        self.root.after(30, self.animate_spin)

    def draw_roulette_table(self):
        self.r_canvas.delete("all")

        self.r_canvas.create_rectangle(0, 0, 1000, 450, outline="#5c3a21", width=20)

        # 1. Draw Wheel (Left side)
        import math
        wheel_cx, wheel_cy = 200, 225
        r_outer, r_inner = 170, 110
        self.r_canvas.create_oval(wheel_cx - r_outer, wheel_cy - r_outer, wheel_cx + r_outer, wheel_cy + r_outer, outline="#b8860b", width=10, fill="#2a1b12")
        self.r_canvas.create_oval(wheel_cx - r_inner, wheel_cy - r_inner, wheel_cx + r_inner, wheel_cy + r_inner, outline="#b8860b", width=4, fill="#1a1a1a")

        # Draw wheel sectors
        wheel_nums = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        angle_step = 360 / 37
        red_nums = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]

        for i, num in enumerate(wheel_nums):
            start_angle = i * angle_step
            color = "#008000" if num == 0 else ("#cc0000" if num in red_nums else "#1a1a1a")
            self.r_canvas.create_arc(wheel_cx - r_outer, wheel_cy - r_outer, wheel_cx + r_outer, wheel_cy + r_outer, start=start_angle, extent=angle_step, fill=color, outline="white")

            # Draw number text
            mid_angle = math.radians(start_angle + (angle_step / 2))
            text_x = wheel_cx + (140 * math.cos(mid_angle))
            text_y = wheel_cy - (140 * math.sin(mid_angle)) # Tkinter y is inverted
            self.r_canvas.create_text(text_x, text_y, text=str(num), fill="white", font=("Arial", 8, "bold"))

        self.r_canvas.create_oval(wheel_cx - r_inner, wheel_cy - r_inner, wheel_cx + r_inner, wheel_cy + r_inner, outline="#b8860b", width=4, fill="#1a1a1a")
        self.r_canvas.create_text(wheel_cx, wheel_cy, text="ROULETTE", fill="#b8860b", font=("Arial", 16, "bold"))

        # Draw ball if last_result exists
        if self.game_state and self.game_state.get("last_result"):
            wheel_nums_local = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
            angle_step_local = 360 / 37
            res_num = self.game_state["last_result"]["number"]
            if res_num in wheel_nums_local:
                idx = wheel_nums_local.index(res_num)
                angle = idx * angle_step_local
                mid_angle = math.radians(angle + (angle_step_local / 2))
                ball_x = wheel_cx + (140 * math.cos(mid_angle))
                ball_y = wheel_cy - (140 * math.sin(mid_angle))
                self.r_canvas.create_oval(ball_x-4, ball_y-4, ball_x+4, ball_y+4, fill="white", tags="ball")

        # 2. Draw Betting Grid (Right side)
        grid_start_x = 420
        grid_start_y = 50
        cell_w, cell_h = 35, 50

        # Zero (Green)
        zx1, zy1, zx2, zy2 = grid_start_x, grid_start_y, grid_start_x + 40, grid_start_y + (cell_h * 3)
        self.r_canvas.create_rectangle(zx1, zy1, zx2, zy2, fill="#008000", outline="white")
        self.r_canvas.create_text((zx1+zx2)/2, (zy1+zy2)/2, text="0", fill="white", font=("Arial", 20, "bold"))
        self.roulette_grid_coords["number_0"] = (zx1, zy1, zx2, zy2)

        # Numbers 1-36
        num = 1
        for col in range(12):
            for row in range(2, -1, -1):
                x1 = grid_start_x + 40 + (col * cell_w)
                y1 = grid_start_y + (row * cell_h)
                x2 = x1 + cell_w
                y2 = y1 + cell_h

                color = "#cc0000" if num in red_nums else "#1a1a1a"
                self.r_canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="white")
                self.r_canvas.create_text(x1 + cell_w/2, y1 + cell_h/2, text=str(num), fill="white", font=("Arial", 14, "bold"))

                self.roulette_grid_coords[f"number_{num}"] = (x1, y1, x2, y2)
                num += 1

        # 2 to 1 columns
        col_x = grid_start_x + 40 + (12 * cell_w)
        for row in range(2, -1, -1):
            x1 = col_x
            y1 = grid_start_y + (row * cell_h)
            x2 = x1 + 50
            y2 = y1 + cell_h
            self.r_canvas.create_rectangle(x1, y1, x2, y2, fill="#005500", outline="white")
            self.r_canvas.create_text((x1+x2)/2, (y1+y2)/2, text="2 to 1", fill="white", font=("Arial", 10, "bold"))
            self.roulette_grid_coords[f"col_{3-row}"] = (x1, y1, x2, y2)

        # Outside Bets
        ox1 = grid_start_x + 40
        oy1 = grid_start_y + (cell_h * 3)

        for i, text in enumerate(["1st 12", "2nd 12", "3rd 12"]):
            x1 = ox1 + (i * cell_w * 4)
            x2 = x1 + (cell_w * 4)
            y2 = oy1 + 40
            self.r_canvas.create_rectangle(x1, oy1, x2, y2, fill="#005500", outline="white")
            self.r_canvas.create_text((x1+x2)/2, (oy1+y2)/2, text=text, fill="white", font=("Arial", 12, "bold"))
            self.roulette_grid_coords[f"dozen_{i+1}"] = (x1, oy1, x2, y2)

        oy2 = oy1 + 40
        halves = [("1 to 18", "#005500"), ("EVEN", "#005500"), ("RED", "#cc0000"), ("BLACK", "#1a1a1a"), ("ODD", "#005500"), ("19 to 36", "#005500")]
        for i, (text, color) in enumerate(halves):
            x1 = ox1 + (i * cell_w * 2)
            x2 = x1 + (cell_w * 2)
            y2 = oy2 + 40
            self.r_canvas.create_rectangle(x1, oy2, x2, y2, fill=color, outline="white")
            self.r_canvas.create_text((x1+x2)/2, (oy2+y2)/2, text=text, fill="white", font=("Arial", 12, "bold"))
            self.roulette_grid_coords[f"half_{text.replace(' ', '_')}"] = (x1, oy2, x2, y2)


    def on_roulette_hover(self, event):
        x, y = event.x, event.y
        new_hover = None
        for bet_key, (x1, y1, x2, y2) in self.roulette_grid_coords.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                new_hover = bet_key
                break

        if new_hover != self.hovered_bet_key:
            self.hovered_bet_key = new_hover
            self.update_ui() # force redraw to show/hide highlight

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
                # Trigger action
                self.client.send_action("r_bet", bet_type=bet_key, amount=amount)

                # Determine color for chip
                denoms = [5, 10, 25, 50, 100, 500, 1000]
                colors = ["#FF0000", "#0000FF", "#008000", "#FFA500", "#1a1a1a", "#800080", "#00FFFF"]
                color = colors[denoms.index(amount)] if amount in denoms else "blue"

                # Animate from bottom to click pos
                # Since chip bank is in a different frame, we approximate start coords relative to canvas
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

        tk.Button(self.top_frame, text="⬅ Lobby", command=self.leave_room, bg="#D4AF37", fg="black", relief=tk.RAISED, borderwidth=3, font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)

        self.canvas = tk.Canvas(self.root, bg="#006600", width=1000, height=500, highlightthickness=0)
        self.canvas.pack(expand=True, fill=tk.BOTH)

        self.draw_static_table()

        self.bottom_frame = tk.Frame(self.root, bg="#006600")
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

        self.avatar_frame = tk.Frame(self.top_frame, bg="#006600")
        self.avatar_frame.pack(side=tk.LEFT, padx=20)

        self.avatar_canvas = tk.Canvas(self.avatar_frame, bg="#006600", width=40, height=40, highlightthickness=0)
        self.avatar_canvas.pack(side=tk.LEFT)
        self.avatar_canvas.create_oval(2, 2, 38, 38, fill="#D4AF37", outline="white", width=2)
        self.avatar_canvas.create_text(20, 20, text="👤", fill="black", font=("Arial", 16))

        self.balance_label = tk.Label(self.avatar_frame, text="", bg="#006600", fg="gold", font=("Arial", 14, "bold"))
        self.balance_label.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(self.top_frame, text="Waiting for state...", bg="#006600", fg="yellow", font=("Arial", 14))
        self.status_label.pack(side=tk.RIGHT, padx=20)

        self.bj_chip_canvas = tk.Canvas(self.bottom_frame, bg="#006600", width=800, height=80, highlightthickness=0)
        self.bj_chip_canvas.bind("<Button-1>", self.on_chip_select)
        self.draw_chip_bank(self.bj_chip_canvas)

        self.bet_button = tk.Button(self.bottom_frame, text="Place Bet", font=("Arial", 16, "bold"), bg="gold", command=self.on_bj_bet)

        button_style = {"font": ("Arial", 14, "bold"), "bg": "#1a1a1a", "fg": "white", "relief": tk.RAISED, "borderwidth": 3, "width": 8}
        self.hit_btn = tk.Button(self.bottom_frame, text="Hit", command=lambda: self.client.send_action("hit"), **button_style)
        self.stand_btn = tk.Button(self.bottom_frame, text="Stand", command=lambda: self.client.send_action("stand"), **button_style)
        self.double_btn = tk.Button(self.bottom_frame, text="Double", command=lambda: self.client.send_action("double"), **button_style)
        self.split_btn = tk.Button(self.bottom_frame, text="Split", command=lambda: self.client.send_action("split"), **button_style)
        self.ins_btn = tk.Button(self.bottom_frame, text="Insurance", command=lambda: self.client.send_action("insurance"), **button_style)

        self.start_round_btn = tk.Button(self.bottom_frame, text="Start New Round", font=("Arial", 12), command=lambda: self.client.send_action("start_round"))

    def on_bj_bet(self):
        amount = getattr(self, 'active_chip', 10)
        self.client.send_action("bet", amount=amount)

        # Animate chip flight to center
        denoms = [1, 5, 10, 25, 100, 500, 1000, 5000, 10000]
        colors = ["#FFFFFF", "#FF0000", "#0000FF", "#008000", "#1a1a1a", "#800080", "#00FFFF", "#FF00FF", "#D4AF37"]
        color = colors[denoms.index(amount)] if amount in denoms else "blue"

        # Approx start from bottom center, end at canvas center
        self.animate_chip_throw(self.canvas, 500, 500, 500, 250, amount, color)

    def draw_static_table(self):
        # Wooden floor background
        self.canvas.create_rectangle(0, 0, 1000, 500, fill="#3d2314", outline="", tags="bg_table")

        # Green casino table oval
        self.canvas.create_oval(50, -250, 950, 480, fill="#006600", outline="#b8860b", width=10, tags="bg_table")

        # Felt texture
        import random
        random.seed(42) # Consistent texture
        for _ in range(500):
            x = random.randint(60, 940)
            y = random.randint(10, 470)
            # Only draw dots roughly inside the lower half of the oval visible on screen
            self.canvas.create_oval(x, y, x+2, y+2, fill="#007700", outline="", tags="bg_table")
        random.seed() # Reset seed

        # Insurance line (Draw this FIRST so it's under the plates)
        self.canvas.create_arc(200, -100, 800, 300, start=180, extent=180, style=tk.ARC, outline="#b8860b", width=2, tags="bg_table")
        self.canvas.create_text(500, 280, text="INSURANCE PAYS 2 TO 1", fill="#b8860b", font=("Arial", 14, "bold"), tags="bg_table")

        # Dealer area curved text
        # Draw a small placard to the side (Draw AFTER line so it covers it)
        self.canvas.create_rectangle(700, 50, 950, 120, fill="#1a1a1a", outline="#b8860b", width=2, tags="ui_plate")
        self.canvas.create_text(825, 70, text="BLACKJACK PAYS 3 TO 2", fill="#b8860b", font=("Arial", 12, "bold"), tags="ui_text")
        self.canvas.create_text(825, 95, text="Dealer must draw to 16,\nand stand on all 17s", fill="#b8860b", font=("Arial", 10), justify=tk.CENTER, tags="ui_text")

    def draw_chips(self, x, y, amount):
        if amount <= 0: return

        chip_denominations = [
            (10000, "#D4AF37"), # Gold
            (5000, "#FF00FF"),  # Magenta
            (1000, "#00FFFF"),  # Cyan
            (500, "#800080"),   # Purple
            (100, "#1a1a1a"),   # Black
            (25, "#008000"),    # Green
            (10, "#0000FF"),    # Blue
            (5, "#FF0000"),     # Red
            (1, "#FFFFFF")      # White
        ]

        chips_to_draw = []
        remaining = amount
        for denom, color in chip_denominations:
            count = int(remaining // denom)
            for _ in range(count):
                chips_to_draw.append((denom, color))
            remaining %= denom

        # Draw maximum 10 chips to not clutter the screen
        # We want to keep the largest denominations (which are added first)
        if len(chips_to_draw) > 10:
            chips_to_draw = chips_to_draw[:10]

        # Draw from bottom to top, meaning largest chips should be drawn first
        chips_to_draw.reverse()

        chip_width = 40
        chip_height = 20
        offset_y = 5

        for i, (denom, color) in enumerate(chips_to_draw):
            cy = y - (i * offset_y)
            text_color = "black" if denom == 1 else "white"

            # Drop shadow
            self.canvas.create_oval(x, cy+2, x + chip_width, cy + chip_height+2, fill="#111111", outline="", stipple="gray50", tags="dynamic")
            # Outer ring
            self.canvas.create_oval(x, cy, x + chip_width, cy + chip_height, fill=color, outline="black", width=1, tags="dynamic")
            # Inner ring
            self.canvas.create_oval(x + 5, cy + 3, x + chip_width - 5, cy + chip_height - 3, outline="black", width=1, tags="dynamic")
            # Dash pattern on the edge
            self.canvas.create_line(x+5, cy+chip_height/2, x+10, cy+chip_height/2, fill="white", width=2, tags="dynamic")
            self.canvas.create_line(x+chip_width-10, cy+chip_height/2, x+chip_width-5, cy+chip_height/2, fill="white", width=2, tags="dynamic")

            # Value text
            self.canvas.create_text(x + chip_width/2, cy + chip_height/2, text=str(denom), fill=text_color, font=("Arial", 8, "bold"), tags=("dynamic", "chip_text"))

        # Fix Text Disappearing
        self.canvas.tag_raise("chip_text")

    def draw_card(self, x, y, card_dict, hidden=False):
        width, height = 65, 95
        # Card shadow - multiple layers for softer shadow
        self.canvas.create_rectangle(x+5, y+5, x+width+5, y+height+5, fill="#0d1f0d", outline="", stipple="gray50", tags=("dynamic", "card"))
        self.canvas.create_rectangle(x+2, y+2, x+width+2, y+height+2, fill="#111111", outline="", tags=("dynamic", "card"))

        if hidden:
            # Card back
            self.canvas.create_rectangle(x, y, x+width, y+height, fill="#003366", outline="white", width=2, tags=("dynamic", "card"))
            # Pattern on back
            for i in range(5, width-5, 10):
                self.canvas.create_line(x+i, y+5, x+i, y+height-5, fill="#005599", width=2, tags=("dynamic", "card"))
            self.canvas.create_oval(x+15, y+30, x+width-15, y+height-30, outline="white", width=2, tags=("dynamic", "card"))
        else:
            # Card face
            self.canvas.create_rectangle(x, y, x+width, y+height, fill="white", outline="#333333", width=1, tags=("dynamic", "card"))
            # Subtle paper texture
            for i in range(2, width, 4):
                self.canvas.create_line(x+i, y+1, x+i, y+height-1, fill="#f9f9f9", width=1, tags=("dynamic", "card"))
            color = "#cc0000" if card_dict["suit"] in ['♥', '♦'] else "black"

            # Rank top-left
            self.canvas.create_text(x+12, y+15, text=card_dict["rank"], fill=color, font=("Arial", 12, "bold"), tags=("dynamic", "card"))
            self.canvas.create_text(x+12, y+30, text=card_dict["suit"], fill=color, font=("Arial", 12), tags=("dynamic", "card"))

            # Center suit (large)
            self.canvas.create_text(x+width/2, y+height/2, text=card_dict["suit"], fill=color, font=("Arial", 28), tags=("dynamic", "card"))

            # Rank bottom-right
            self.canvas.create_text(x+width-12, y+height-30, text=card_dict["suit"], fill=color, font=("Arial", 12), tags=("dynamic", "card"))
            self.canvas.create_text(x+width-12, y+height-15, text=card_dict["rank"], fill=color, font=("Arial", 12, "bold"), tags=("dynamic", "card"))



    def animate_card_deal(self, start_x, start_y, end_x, end_y, card_dict):
        # We draw a temporary back card and slide it
        temp_card = self.canvas.create_rectangle(start_x, start_y, start_x+65, start_y+95, fill="#003366", outline="white", width=2, tags="anim_card")
        self.animating_count += 1

        steps = 10
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps

        def move(step):
            if step < steps:
                self.canvas.move(temp_card, dx, dy)
                self.root.after(15, lambda: move(step+1))
            else:
                self.canvas.delete(temp_card)
                self.animating_count -= 1
                if self.animating_count <= 0:
                    self.animating_count = 0
                    self.update_ui() # Full redraw

        move(0)

    def update_ui(self):
        if getattr(self, 'animating_count', 0) > 0: return
        if not self.game_state: return

        state = self.game_state["state"]
        players = self.game_state["players"]
        me = players.get(self.player_id)

        if self.current_view == "lobby":
            if me and hasattr(self, 'lobby_balance_label'):
                self.lobby_balance_label.config(text=f"Balance: ${me['balance']}")
            return


        if self.current_view == "roulette":
            if me and hasattr(self, 'r_balance_label'):
                self.r_balance_label.config(text=f"Balance: ${me['balance']}")

            if not getattr(self, 'is_spinning', False):
                self.draw_roulette_table()

                # Draw hover highlight
                if getattr(self, 'hovered_bet_key', None) and self.hovered_bet_key in self.roulette_grid_coords:
                    x1, y1, x2, y2 = self.roulette_grid_coords[self.hovered_bet_key]
                    self.r_canvas.create_rectangle(x1, y1, x2, y2, outline="yellow", width=4, tags="hover_box")

                if self.game_state.get("last_result"):
                    res = self.game_state["last_result"]
                    self.r_canvas.create_text(200, 225, text=str(res['number']), fill="white", font=("Arial", 36, "bold"))
                    self.r_canvas.create_text(200, 260, text=res['color'].upper(), fill=res['color'], font=("Arial", 14, "bold"))

                    # Highlight winning number cell
                    if f"number_{res['number']}" in self.roulette_grid_coords:
                        x1, y1, x2, y2 = self.roulette_grid_coords[f"number_{res['number']}"]
                        self.r_canvas.create_rectangle(x1, y1, x2, y2, outline="yellow", width=4)

                if "active_bets" in self.game_state:
                    for pid, player_bets in self.game_state["active_bets"].items():
                        for bet in player_bets:
                            if bet["type"] in self.roulette_grid_coords:
                                x1, y1, x2, y2 = self.roulette_grid_coords[bet["type"]]
                                cx, cy = (x1+x2)/2, (y1+y2)/2

                                # Draw chip
                                self.r_canvas.create_oval(cx-15, cy-15, cx+15, cy+15, fill="blue", outline="white", width=2)
                                self.r_canvas.create_oval(cx-10, cy-10, cx+10, cy+10, outline="white", width=1)
                                self.r_canvas.create_text(cx, cy, text=str(bet["amount"]), fill="white", font=("Arial", 8, "bold"))
            return

        if self.current_view != "blackjack":
            return

        self.canvas.delete("dynamic")

        for widget in self.bottom_frame.winfo_children():
            widget.pack_forget()


        state = self.game_state["state"]
        players = self.game_state["players"]
        me = players.get(self.player_id)

        if me:
            self.balance_label.config(text=f"{me['name']} | Balance: ${me['balance']}")
            if self.status_label:
                self.status_label.config(text="")

        if state == "waiting_for_players" or state == "game_over":
            self.start_round_btn.pack(side=tk.LEFT, padx=10)

        # --- BETTING STATE LOGIC ---
        if state == "betting":
            if me and me["state"] == "betting":
                self.canvas.create_text(500, 250, text="Place your bet", fill="white", font=("Arial", 24, "bold"), tags=("dynamic", "ui_panel"))
                self.bj_chip_canvas.pack(side=tk.LEFT, padx=10)
                self.draw_chip_bank(self.bj_chip_canvas)
                self.bet_button.pack(side=tk.LEFT, padx=10)
            else:
                self.canvas.create_text(500, 250, text="Waiting for others to bet...", fill="white", font=("Arial", 24), tags=("dynamic", "ui_panel"))
                self.bj_chip_canvas.pack_forget()
                self.bet_button.pack_forget()
        else:
            # FORCE HIDE when game is playing, dealer turn, or game over
            if hasattr(self, 'bj_chip_canvas'):
                self.bj_chip_canvas.pack_forget()
            if hasattr(self, 'bet_button'):
                self.bet_button.pack_forget()

        if state in ["playing", "dealer_turn", "game_over"]:
            self.canvas.create_text(500, 30, text="Dealer", fill="white", font=("Arial", 16), tags=("dynamic", "ui_panel"))
            dealer = self.game_state["dealer"]
            dealer_cards = dealer["hand"]["cards"]
            dealer_x = 500 - (len(dealer_cards) * 35)

            for i, c in enumerate(dealer_cards):
                hidden = (i == 1 and not dealer["show_hidden"])
                self.draw_card(dealer_x + i*70, 50, c, hidden)

            if dealer["show_hidden"]:
                self.canvas.create_text(500, 160, text=f"Score: {dealer['hand']['score']}", fill="white", tags=("dynamic", "ui_panel"))
            else:
                if dealer_cards:
                    visible_card = dealer_cards[0]
                    rank = visible_card["rank"]
                    val = 11 if rank == "A" else (10 if rank in ["J", "Q", "K"] else int(rank))
                    self.canvas.create_text(500, 160, text=f"Dealer (Show {val})", fill="white", font=("Arial", 14), tags=("dynamic", "ui_panel"))

            num_players = len(self.game_state["player_order"])
            if num_players > 0:
                spacing = 1000 / (num_players + 1)
                for i, pid in enumerate(self.game_state["player_order"]):
                    p = players[pid]
                    center_x = spacing * (i + 1)

                    is_current = (self.game_state["current_player_id"] == pid and state == "playing")
                    if is_current:
                        # Soft glow effect
                        self.canvas.create_rectangle(center_x-124, 196, center_x+124, 454, outline="#ffffaa", width=1, dash=(2, 4), tags=("dynamic", "selection_border"))
                        self.canvas.create_rectangle(center_x-122, 198, center_x+122, 452, outline="#ffff55", width=1, tags=("dynamic", "selection_border"))
                        self.canvas.create_rectangle(center_x-120, 200, center_x+120, 450, outline="yellow", width=2, tags=("dynamic", "selection_border"))

                        # AI Advisor
                        adv_x = 850
                        adv_y = 150
                        self.canvas.create_rectangle(adv_x, adv_y, adv_x+130, adv_y+80, fill="#1a1a1a", outline="#b8860b", width=2, tags=("dynamic", "ui_panel"))
                        self.canvas.create_text(adv_x+65, adv_y+20, text="🤖 AI Advisor", fill="#b8860b", font=("Arial", 12, "bold"), tags=("dynamic", "ui_panel"))

                        suggestion = "STAND"
                        try:
                            if not p.get("hands") or len(p["hands"]) == 0 or not dealer["hand"].get("cards"):
                                raise Exception("Cards missing")
                            player_score = p["hands"][p["current_hand_idx"]]["score"]
                            dealer_visible_card = dealer["hand"]["cards"][0]
                            d_rank = dealer_visible_card["rank"]
                            d_val = 11 if d_rank == "A" else (10 if d_rank in ["J", "Q", "K"] else int(d_rank))

                            if player_score < 12:
                                suggestion = "HIT"
                            elif player_score == 12 and d_val in [2,3,4,5,6]:
                                suggestion = "STAND"
                            elif player_score in [13, 14, 15, 16] and d_val in [2,3,4,5,6]:
                                suggestion = "STAND"
                            elif player_score >= 17:
                                suggestion = "STAND"
                            else:
                                suggestion = "HIT"
                        except:
                            pass

                        self.canvas.create_text(adv_x+65, adv_y+50, text=f"Suggested: {suggestion}", fill="white", font=("Arial", 10), tags=("dynamic", "ui_panel"))

                    self.canvas.create_text(center_x, 220, text=f"{p['name']} (${p['balance']})", tags="dynamic", fill="white", font=("Arial", 14, "bold"))

                    if p["message"]:
                        msg_color = "gold" if "Win" in p["message"] or "Blackjack" in p["message"] else ("red" if "Lose" in p["message"] or "Bust" in p["message"] else "white")
                        self.canvas.create_text(center_x, 350, text=p["message"], fill=msg_color, font=("Arial", 28, "bold"), tags=("dynamic", "result_msg"))

                    for h_idx, h in enumerate(p["hands"]):
                        hy = 250 + (h_idx * 110)
                        self.canvas.create_text(center_x, hy-15, text=f"Bet: ${h['bet']} | Score: {h['score']}", fill="white", tags=("dynamic", "ui_panel"))

                        if h['bet'] > 0:
                            # Draw chips significantly to the left of the cards
                            self.draw_chips(center_x - 100, hy + 40, h['bet'])

                        # Draw cards centered
                        cards_x = center_x - (len(h["cards"]) * 20)
                        for c_idx, c in enumerate(h["cards"]):
                            target_x = cards_x + c_idx*40
                            target_y = hy
                            card_id = f"{pid}_{h_idx}_{c_idx}"

                            if card_id not in self.animated_cards:
                                self.animated_cards.add(card_id)
                                # Trigger animation from deck position
                                self.animate_card_deal(800, 50, target_x, target_y, c)
                                # The animation handles drawing a flying card. We won't draw the final card face right now,
                                # but we WON'T return so the rest of the UI continues to draw.
                            else:
                                self.draw_card(target_x, target_y, c)

            # Hand History logic
            if state == "betting":
                self.animated_cards.clear()
            if self.prev_state in ["playing", "dealer_turn"] and state == "game_over":
                if me and me.get("message"):
                    # Clean up message and grab first significant word
                    msg = me.get("message", "").strip()
                    if "Win" in msg or "Blackjack" in msg: outcome = "Win"
                    elif "Lose" in msg or "Bust" in msg: outcome = "Loss"
                    else: outcome = "Push"
                    self.hand_history.insert(0, outcome)
                    self.hand_history = self.hand_history[:5]

            self.prev_state = state

            # Draw History Panel
            hist_x = 20
            hist_y = 150
            self.canvas.create_rectangle(hist_x, hist_y, hist_x+100, hist_y+150, fill="#1a1a1a", outline="#b8860b", width=2, tags=("dynamic", "ui_panel"))
            self.canvas.create_text(hist_x+50, hist_y+20, text="HISTORY", fill="#b8860b", font=("Arial", 10, "bold"), tags=("dynamic", "ui_panel"))
            for i, res in enumerate(self.hand_history):
                color = "green" if res == "Win" else ("red" if res == "Loss" else "white")
                self.canvas.create_text(hist_x+50, hist_y+50 + (i*20), text=res, fill=color, font=("Arial", 10, "bold"), tags=("dynamic", "ui_panel"))

            if state == "playing" and self.game_state["current_player_id"] == self.player_id:
                h = me["hands"][me["current_hand_idx"]]

                # Double down logic
                if len(h["cards"]) == 2:
                    self.double_btn.config(state=tk.NORMAL, bg="#1a1a1a")
                else:
                    self.double_btn.config(state=tk.DISABLED, bg="#555555")

                # Split logic
                if len(h["cards"]) == 2 and h["cards"][0]["rank"] == h["cards"][1]["rank"]:
                    self.split_btn.config(state=tk.NORMAL, bg="#1a1a1a")
                else:
                    self.split_btn.config(state=tk.DISABLED, bg="#555555")

                # Insurance logic
                dealer_up_card = dealer["hand"]["cards"][0] if dealer["hand"]["cards"] else None
                if dealer_up_card and dealer_up_card["rank"] == "A" and len(me["hands"]) == 1 and len(h["cards"]) == 2 and me.get("insurance_bet", 0) == 0:
                    self.ins_btn.config(state=tk.NORMAL, bg="#1a1a1a")
                else:
                    self.ins_btn.config(state=tk.DISABLED, bg="#555555")

                self.hit_btn.pack(side=tk.LEFT, padx=5)
                self.stand_btn.pack(side=tk.LEFT, padx=5)
                self.double_btn.pack(side=tk.LEFT, padx=5)
                self.split_btn.pack(side=tk.LEFT, padx=5)
                self.ins_btn.pack(side=tk.LEFT, padx=5)

        self.canvas.tag_lower("bg_table")
        self.canvas.tag_raise("card")
        self.canvas.tag_raise("dynamic")
        if self.canvas.find_withtag("result_msg"):
            self.canvas.tag_raise("result_msg")

def main():
    root = tk.Tk()
    app = BlackjackGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
