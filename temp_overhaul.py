with open('blackjack.py', 'r') as f:
    content = f.read()

# Fix LocalClient bug completely by stripping it out and replacing it
import re

clean_local_client = """
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
"""

# Try to find existing LocalClient(s) and wipe them out, replacing with clean one
content = re.sub(r'class LocalClient:.*?self\._trigger_update\(\)\n*(?=\n# =+)', clean_local_client.strip(), content, flags=re.DOTALL)


# Fix newlines in server Client reading code
content = content.replace("messages = data.decode('utf-8').split('\\n')", "messages = data.decode('utf-8').split('\\n')")
content = content.replace("client.sendall(data + b'\\\\n')", "client.sendall(data + b'\\n')")


# Update Roulette logic
new_roulette_logic = """
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
"""
content = re.sub(r'class RouletteGame:.*?def get_state\(self\):.*?        }', new_roulette_logic.strip(), content, flags=re.DOTALL)

# Also fix the server roulette route action
server_routing = """
                        elif self.global_players[pid]["room"] == "roulette":
                            if action == "r_bet":
                                self.roulette_game.place_bet(pid, msg.get("amount", 10), msg.get("bet_type"))
                            elif action == "r_spin":
                                self.roulette_game.spin()
"""
content = re.sub(r'elif self\.global_players\[pid\]\["room"\] == "roulette":.*?self\.roulette_game\.spin\(\)', server_routing.strip(), content, flags=re.DOTALL)


# Update Roulette UI (grid and wheel)
new_roulette_ui = """
    def setup_roulette_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.r_frame = tk.Frame(self.root, bg="#005500")
        self.r_frame.pack(expand=True, fill=tk.BOTH)

        top_bar = tk.Frame(self.r_frame, bg="#333")
        top_bar.pack(fill=tk.X)
        tk.Button(top_bar, text="< Back to Lobby", command=self.leave_room, bg="#333", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=10, pady=5)
        self.r_balance_label = tk.Label(top_bar, text="Balance: $", fg="gold", bg="#333", font=("Arial", 14, "bold"))
        self.r_balance_label.pack(side=tk.RIGHT, padx=20)

        self.r_canvas = tk.Canvas(self.r_frame, bg="#006600", width=1000, height=450, highlightthickness=0)
        self.r_canvas.pack(pady=10)

        bottom_frame = tk.Frame(self.r_frame, bg="#005500")
        bottom_frame.pack(fill=tk.X, pady=10)

        tk.Label(bottom_frame, text="Bet Amount:", bg="#005500", fg="white", font=("Arial", 14)).pack(side=tk.LEFT, padx=10)
        self.r_bet_entry = tk.Entry(bottom_frame, width=10, font=("Arial", 14))
        self.r_bet_entry.pack(side=tk.LEFT, padx=10)
        self.r_bet_entry.insert(0, "10")

        tk.Button(bottom_frame, text="Spin Wheel!", bg="gold", fg="black", font=("Arial", 16, "bold"), command=lambda: self.client.send_action("r_spin")).pack(side=tk.RIGHT, padx=20)

        self.r_canvas.bind("<Button-1>", self.on_roulette_click)
        self.roulette_grid_coords = {}

    def draw_roulette_table(self):
        self.r_canvas.delete("all")

        # Draw wooden border
        self.r_canvas.create_rectangle(0, 0, 1000, 450, outline="#5c3a21", width=20)

        # 1. Draw Wheel (Left side)
        wheel_cx, wheel_cy = 200, 225
        r_outer, r_inner = 150, 100
        self.r_canvas.create_oval(wheel_cx - r_outer, wheel_cy - r_outer, wheel_cx + r_outer, wheel_cy + r_outer, outline="#b8860b", width=8, fill="#2a1b12")
        self.r_canvas.create_oval(wheel_cx - r_inner, wheel_cy - r_inner, wheel_cx + r_inner, wheel_cy + r_inner, outline="#b8860b", width=3, fill="#1a1a1a")
        self.r_canvas.create_text(wheel_cx, wheel_cy, text="ROULETTE", fill="#b8860b", font=("Arial", 14, "bold"))

        # 2. Draw Betting Grid (Right side)
        grid_start_x = 400
        grid_start_y = 50
        cell_w, cell_h = 40, 60

        red_nums = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]

        # Zero (Green)
        zx1, zy1, zx2, zy2 = grid_start_x, grid_start_y, grid_start_x + 50, grid_start_y + (cell_h * 3)
        self.r_canvas.create_rectangle(zx1, zy1, zx2, zy2, fill="#008000", outline="white")
        self.r_canvas.create_text((zx1+zx2)/2, (zy1+zy2)/2, text="0", fill="white", font=("Arial", 20, "bold"))
        self.roulette_grid_coords["number_0"] = (zx1, zy1, zx2, zy2)

        # Numbers 1-36
        num = 1
        for col in range(12):
            for row in range(2, -1, -1):
                x1 = grid_start_x + 50 + (col * cell_w)
                y1 = grid_start_y + (row * cell_h)
                x2 = x1 + cell_w
                y2 = y1 + cell_h

                color = "#cc0000" if num in red_nums else "#1a1a1a"
                self.r_canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="white")
                self.r_canvas.create_text(x1 + cell_w/2, y1 + cell_h/2, text=str(num), fill="white", font=("Arial", 14, "bold"))

                self.roulette_grid_coords[f"number_{num}"] = (x1, y1, x2, y2)
                num += 1

        # Outside Bets
        ox1 = grid_start_x + 50
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

    def on_roulette_click(self, event):
        x, y = event.x, event.y
        amount = int(self.r_bet_entry.get() or 0)
        if amount <= 0: return

        for bet_key, (x1, y1, x2, y2) in self.roulette_grid_coords.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.client.send_action("r_bet", bet_type=bet_key, amount=amount)
                break

    def leave_room(self):
        self.client.send_action("leave_room")
        self.setup_lobby_screen()
"""

content = re.sub(r'    def setup_roulette_screen\(self\):.*?def leave_room\(self\):.*?self\.setup_lobby_screen\(\)', new_roulette_ui.strip(), content, flags=re.DOTALL)


# Update UI update function
update_ui_code = """
        if self.current_view == "roulette":
            if me and hasattr(self, 'r_balance_label'):
                self.r_balance_label.config(text=f"Balance: ${me['balance']}")

            self.draw_roulette_table()

            if state.get("last_result"):
                res = state["last_result"]
                self.r_canvas.create_text(200, 225, text=str(res['number']), fill="white", font=("Arial", 36, "bold"))
                self.r_canvas.create_text(200, 260, text=res['color'].upper(), fill=res['color'], font=("Arial", 14, "bold"))

            if "active_bets" in state:
                for pid, player_bets in state["active_bets"].items():
                    for bet in player_bets:
                        if bet["type"] in self.roulette_grid_coords:
                            x1, y1, x2, y2 = self.roulette_grid_coords[bet["type"]]
                            cx, cy = (x1+x2)/2, (y1+y2)/2

                            self.r_canvas.create_oval(cx-15, cy-15, cx+15, cy+15, fill="blue", outline="white", width=2)
                            self.r_canvas.create_text(cx, cy, text=str(bet["amount"]), fill="white", font=("Arial", 8, "bold"))
            return
"""
content = re.sub(r'        if self\.current_view == "roulette":.*?return', update_ui_code.strip(), content, flags=re.DOTALL)

with open('blackjack.py', 'w') as f:
    f.write(content)
