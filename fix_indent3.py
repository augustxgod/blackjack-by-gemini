import re

with open("blackjack.py", "r") as f:
    content = f.read()

# I will replace the space-mixing entirely.
content = content.replace('\t', '    ')

with open("blackjack.py", "w") as f:
    f.write(content)
