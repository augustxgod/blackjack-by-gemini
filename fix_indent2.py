with open("blackjack.py", "r") as f:
    lines = f.readlines()

with open("blackjack.py", "w") as f:
    for line in lines:
        if line == "    def draw_roulette_table(self):\n":
            line = "    def draw_roulette_table(self):\n"
        # I just realized maybe on_roulette_click has bad indents?
        f.write(line)
