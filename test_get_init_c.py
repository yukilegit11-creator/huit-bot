import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import bot
init_c = bot.get_initial_cycle()
print("get_initial_cycle() returned:", init_c)
