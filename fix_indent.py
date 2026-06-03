with open("blackjack.py", "r") as f:
    lines = f.readlines()

with open("blackjack.py", "w") as f:
    for line in lines:
        if line.startswith("        def leave_room(self):"):
            f.write("    def leave_room(self):\n")
        elif line.startswith("            self.client.send_action(\"leave_room\")"):
            f.write("        self.client.send_action(\"leave_room\")\n")
        elif line.startswith("            self.setup_lobby_screen()"):
            f.write("        self.setup_lobby_screen()\n")
        else:
            f.write(line)
