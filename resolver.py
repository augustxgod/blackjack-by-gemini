import re

with open("blackjack.py", "r") as f:
    content = f.read()

# Мы сейчас находимся в rebase, значит HEAD это ветка main,
# а то что мы добавляем - это наши изменения (Add visual chips for bets).
# Конфликты в ребейзе выглядят так:
# <<<<<<< HEAD
# (код из main)
# =======
# (наш код)
# >>>>>>> 31195e8... Add visual chips for bets

def resolve_conflict(match):
    # возвращаем наш код, удаляя маркеры
    return match.group(2)

# Регулярка для поиска конфликтов
pattern = re.compile(r'<<<<<<< HEAD\n(.*?)\n=======\n(.*?)\n>>>>>>> [a-f0-9\.]+.*?$', re.MULTILINE | re.DOTALL)
new_content = pattern.sub(resolve_conflict, content)

with open("blackjack.py", "w") as f:
    f.write(new_content)
