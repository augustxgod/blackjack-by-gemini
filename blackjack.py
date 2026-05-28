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

# ==========================================
# NETWORK
# ==========================================

class Server:
    def __init__(self, host='0.0.0.0'):
        self.host = host
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, HOST_PORT))
        self.server.listen()

        self.game = Game()
        self.clients = {}

    def start(self):
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            client, address = self.server.accept()
            threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()

    def broadcast_state(self):
        state = self.game.get_state()
        data = json.dumps({"type": "state", "data": state}).encode('utf-8')
        for client in self.clients:
            try:
                client.sendall(data + b'\n')
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
                self.game.add_player(player_id, name)
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
                        if action == "bet":
                            self.game.place_bet(pid, msg["amount"])
                        elif action == "hit":
                            self.game.hit(pid)
                        elif action == "stand":
                            self.game.stand(pid)
                        elif action == "double":
                            self.game.double_down(pid)
                        elif action == "split":
                            self.game.split(pid)
                        elif action == "insurance":
                            self.game.buy_insurance(pid)
                        elif action == "start_round":
                            self.game.start_betting_phase()

                        self.broadcast_state()
        except:
            pass
        finally:
            if client in self.clients:
                pid = self.clients[client]
                self.game.remove_player(pid)
                del self.clients[client]
                self.broadcast_state()
            client.close()

class Client:
    def __init__(self, host, player_id, name):
        self.host = host
        self.player_id = player_id
        self.name = name
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.on_state_update = None

    def connect(self):
        self.client.connect((self.host, HOST_PORT))
        join_msg = json.dumps({"type": "join", "player_id": self.player_id, "name": self.name})
        self.client.sendall(join_msg.encode('utf-8') + b'\n')
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def receive_loop(self):
        buffer = ""
        while True:
            try:
                data = self.client.recv(4096)
                if not data: break
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        msg = json.loads(line)
                        if msg["type"] == "state" and self.on_state_update:
                            self.on_state_update(msg["data"])
            except:
                break

    def send_action(self, action, **kwargs):
        msg = {"type": "action", "action": action, "player_id": self.player_id}
        msg.update(kwargs)
        self.client.sendall(json.dumps(msg).encode('utf-8') + b'\n')

class LocalClient:
    def __init__(self, player_id, name):
        self.player_id = player_id
        self.name = name
        self.game = Game()
        self.on_state_update = None

    def connect(self):
        self.game.add_player(self.player_id, self.name)
        self._trigger_update()

    def _trigger_update(self):
        if self.on_state_update:
            state = self.game.get_state()
            self.on_state_update(state)

    def send_action(self, action, **kwargs):
        pid = self.player_id
        if action == "bet":
            self.game.place_bet(pid, kwargs.get("amount", 0))
        elif action == "hit":
            self.game.hit(pid)
        elif action == "stand":
            self.game.stand(pid)
        elif action == "double":
            self.game.double_down(pid)
        elif action == "split":
            self.game.split(pid)
        elif action == "insurance":
            self.game.buy_insurance(pid)
        elif action == "start_round":
            self.game.start_betting_phase()
        self._trigger_update()

# ==========================================
# GUI
# ==========================================

class BlackjackGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Blackjack")
        self.root.geometry("1000x700")
        self.root.configure(bg="#006600")

        self.player_id = str(uuid.uuid4())
        self.client = None
        self.server = None
        self.game_state = None

        self.setup_start_screen()

    def setup_start_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        frame = tk.Frame(self.root, bg="#006600")
        frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(frame, text="Blackjack", font=("Arial", 36, "bold"), bg="#006600", fg="white").pack(pady=20)

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
        self.setup_game_screen()

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

    def on_state_update(self, state):
        self.game_state = state
        self.root.after(0, self.update_ui)

    def setup_game_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.top_frame = tk.Frame(self.root, bg="#006600")
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        self.canvas = tk.Canvas(self.root, bg="#006600", width=1000, height=500, highlightthickness=0)
        self.canvas.pack(expand=True, fill=tk.BOTH)

        self.bottom_frame = tk.Frame(self.root, bg="#006600")
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

        self.balance_label = tk.Label(self.top_frame, text="", bg="#006600", fg="white", font=("Arial", 14, "bold"))
        self.balance_label.pack(side=tk.LEFT, padx=20)

        self.status_label = tk.Label(self.top_frame, text="Waiting for state...", bg="#006600", fg="yellow", font=("Arial", 14))
        self.status_label.pack(side=tk.RIGHT, padx=20)

        self.bet_entry = tk.Entry(self.bottom_frame, width=10, font=("Arial", 14))
        self.bet_button = tk.Button(self.bottom_frame, text="Place Bet", font=("Arial", 12), command=lambda: self.client.send_action("bet", amount=int(self.bet_entry.get() or 0)))

        self.hit_btn = tk.Button(self.bottom_frame, text="Hit", font=("Arial", 12), command=lambda: self.client.send_action("hit"))
        self.stand_btn = tk.Button(self.bottom_frame, text="Stand", font=("Arial", 12), command=lambda: self.client.send_action("stand"))
        self.double_btn = tk.Button(self.bottom_frame, text="Double", font=("Arial", 12), command=lambda: self.client.send_action("double"))
        self.split_btn = tk.Button(self.bottom_frame, text="Split", font=("Arial", 12), command=lambda: self.client.send_action("split"))
        self.ins_btn = tk.Button(self.bottom_frame, text="Insurance", font=("Arial", 12), command=lambda: self.client.send_action("insurance"))

        self.start_round_btn = tk.Button(self.bottom_frame, text="Start New Round", font=("Arial", 12), command=lambda: self.client.send_action("start_round"))

    def draw_table(self):
        # Wooden floor background
        self.canvas.create_rectangle(0, 0, 1000, 500, fill="#3d2314", outline="")

        # Green casino table oval
        self.canvas.create_oval(50, -250, 950, 480, fill="#006600", outline="#b8860b", width=10)

        # Dealer area curved text
        self.canvas.create_text(500, 170, text="BLACKJACK PAYS 3 TO 2", fill="#b8860b", font=("Arial", 16, "bold"))
        self.canvas.create_text(500, 195, text="Dealer must draw to 16, and stand on all 17s", fill="#b8860b", font=("Arial", 12))

        # Insurance line
        self.canvas.create_arc(200, -100, 800, 300, start=180, extent=180, style=tk.ARC, outline="#b8860b", width=2)
        self.canvas.create_text(500, 280, text="INSURANCE PAYS 2 TO 1", fill="#b8860b", font=("Arial", 14, "bold"))

    def draw_chips(self, x, y, amount):
        if amount <= 0: return

        chip_denominations = [
            (500, "#800080"), # Purple
            (100, "#1a1a1a"), # Black
            (25, "#008000"),  # Green
            (10, "#0000FF"),  # Blue
            (5, "#FF0000"),   # Red
            (1, "#FFFFFF")    # White
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

            # Outer ring
            self.canvas.create_oval(x, cy, x + chip_width, cy + chip_height, fill=color, outline="black", width=1)
            # Inner ring
            self.canvas.create_oval(x + 5, cy + 3, x + chip_width - 5, cy + chip_height - 3, outline="black", width=1)
            # Dash pattern on the edge
            self.canvas.create_line(x+5, cy+chip_height/2, x+10, cy+chip_height/2, fill="white", width=2)
            self.canvas.create_line(x+chip_width-10, cy+chip_height/2, x+chip_width-5, cy+chip_height/2, fill="white", width=2)

            # Value text
            self.canvas.create_text(x + chip_width/2, cy + chip_height/2, text=str(denom), fill=text_color, font=("Arial", 8, "bold"))

    def draw_card(self, x, y, card_dict, hidden=False):
        width, height = 65, 95
        # Card shadow
        self.canvas.create_rectangle(x+3, y+3, x+width+3, y+height+3, fill="#111111", outline="")

        if hidden:
            # Card back
            self.canvas.create_rectangle(x, y, x+width, y+height, fill="#003366", outline="white", width=2)
            # Pattern on back
            for i in range(5, width-5, 10):
                self.canvas.create_line(x+i, y+5, x+i, y+height-5, fill="#005599", width=2)
            self.canvas.create_oval(x+15, y+30, x+width-15, y+height-30, outline="white", width=2)
        else:
            # Card face
            self.canvas.create_rectangle(x, y, x+width, y+height, fill="white", outline="#333333", width=1)
            color = "#cc0000" if card_dict["suit"] in ['♥', '♦'] else "black"

            # Rank top-left
            self.canvas.create_text(x+12, y+15, text=card_dict["rank"], fill=color, font=("Arial", 12, "bold"))
            self.canvas.create_text(x+12, y+30, text=card_dict["suit"], fill=color, font=("Arial", 12))

            # Center suit (large)
            self.canvas.create_text(x+width/2, y+height/2, text=card_dict["suit"], fill=color, font=("Arial", 28))

            # Rank bottom-right
            self.canvas.create_text(x+width-12, y+height-30, text=card_dict["suit"], fill=color, font=("Arial", 12))
            self.canvas.create_text(x+width-12, y+height-15, text=card_dict["rank"], fill=color, font=("Arial", 12, "bold"))

    def update_ui(self):
        if not self.game_state: return

        self.canvas.delete("all")
        self.draw_table()

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

        if state == "betting":
            if me and me["state"] == "betting":
                self.canvas.create_text(500, 250, text="Place your bet", fill="white", font=("Arial", 24, "bold"))
                self.bet_entry.pack(side=tk.LEFT, padx=10)
                self.bet_entry.delete(0, tk.END)
                self.bet_entry.insert(0, "10")
                self.bet_button.pack(side=tk.LEFT, padx=10)
            else:
                self.canvas.create_text(500, 250, text="Waiting for others to bet...", fill="white", font=("Arial", 24))

        if state in ["playing", "dealer_turn", "game_over"]:
            self.canvas.create_text(500, 30, text="Dealer", fill="white", font=("Arial", 16))
            dealer = self.game_state["dealer"]
            dealer_cards = dealer["hand"]["cards"]
            dealer_x = 500 - (len(dealer_cards) * 35)

            for i, c in enumerate(dealer_cards):
                hidden = (i == 1 and not dealer["show_hidden"])
                self.draw_card(dealer_x + i*70, 50, c, hidden)

            if dealer["show_hidden"]:
                self.canvas.create_text(500, 160, text=f"Score: {dealer['hand']['score']}", fill="white")

            num_players = len(self.game_state["player_order"])
            if num_players > 0:
                spacing = 1000 / (num_players + 1)
                for i, pid in enumerate(self.game_state["player_order"]):
                    p = players[pid]
                    center_x = spacing * (i + 1)

                    is_current = (self.game_state["current_player_id"] == pid and state == "playing")
                    if is_current:
                        self.canvas.create_rectangle(center_x-100, 180, center_x+100, 480, outline="yellow", width=3)

                    self.canvas.create_text(center_x, 200, text=f"{p['name']} (${p['balance']})", fill="white", font=("Arial", 14, "bold"))

                    if p["message"]:
                        self.canvas.create_text(center_x, 220, text=p["message"], fill="yellow")

                    for h_idx, h in enumerate(p["hands"]):
                        hy = 250 + (h_idx * 100)
                        self.canvas.create_text(center_x, hy-15, text=f"Bet: ${h['bet']} | Score: {h['score']}", fill="white")

                        if h['bet'] > 0:
                            self.draw_chips(center_x - 60, hy + 20, h['bet'])

                        cards_x = center_x - (len(h["cards"]) * 20)
                        for c_idx, c in enumerate(h["cards"]):
                            self.draw_card(cards_x + c_idx*40, hy, c)

            if state == "playing" and self.game_state["current_player_id"] == self.player_id:
                self.hit_btn.pack(side=tk.LEFT, padx=5)
                self.stand_btn.pack(side=tk.LEFT, padx=5)
                self.double_btn.pack(side=tk.LEFT, padx=5)
                self.split_btn.pack(side=tk.LEFT, padx=5)
                self.ins_btn.pack(side=tk.LEFT, padx=5)

def main():
    root = tk.Tk()
    app = BlackjackGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
