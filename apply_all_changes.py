import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"
WEB_APP_PATH = os.path.join(ROOT_DIR, "web_app.py")
UFM_WEB_APP_PATH = os.path.join(ROOT_DIR, "vaa", "ufm", "web_app.py")
VAA_WEB_APP_PATH = os.path.join(ROOT_DIR, "vaa", "web_app.py")

print("=== 1. ADDING NEW FACEBOOK TARGET (YU KI) TO CONFIGS ===")

new_target_huit = {
    "id": "target_14",
    "name": "Yu Ki (FB Profile)",
    "url": "https://www.facebook.com/profile.php?id=61595329828799"
}

# Update config.json
with open(os.path.join(ROOT_DIR, "config.json"), "r", encoding="utf-8") as f:
    cfg1 = json.load(f)

existing_urls = {t["url"] for t in cfg1.get("targets", [])}
if new_target_huit["url"] not in existing_urls:
    cfg1["targets"].append(new_target_huit)
    with open(os.path.join(ROOT_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg1, f, ensure_ascii=False, indent=2)
    print("Added Yu Ki target to config.json!")
else:
    print("Yu Ki target already in config.json.")

# Update config_bot2.json & vaabot.json
new_target_vaa = {
    "id": "target_12",
    "name": "Yu Ki (FB Profile)",
    "url": "https://www.facebook.com/profile.php?id=61595329828799"
}

for cfg_name in ["config_bot2.json", "vaabot.json"]:
    p = os.path.join(ROOT_DIR, cfg_name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            c = json.load(f)
        u_set = {t["url"] for t in c.get("targets", [])}
        if new_target_vaa["url"] not in u_set:
            c["targets"].append(new_target_vaa)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
            print(f"Added Yu Ki target to {cfg_name}!")

# Update vaa/config.json & vaa/vaabot.json
for sub_cfg in [os.path.join(ROOT_DIR, "vaa", "config.json"), os.path.join(ROOT_DIR, "vaa", "vaabot.json")]:
    if os.path.exists(sub_cfg):
        with open(sub_cfg, "r", encoding="utf-8") as f:
            c = json.load(f)
        u_set = {t["url"] for t in c.get("targets", [])}
        if new_target_vaa["url"] not in u_set:
            c["targets"].append(new_target_vaa)
            with open(sub_cfg, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
            print(f"Added Yu Ki target to {sub_cfg}!")

print("\n=== 2. PATCHING UI BUTTONS IN web_app.py ===")

with open(WEB_APP_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# Bot 1 row button
old_b1 = """          <div class="flex items-center gap-3">
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">"""

new_b1 = """          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot1')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">"""

if old_b1 in code:
    code = code.replace(old_b1, new_b1, 1)
    print("Patched Bot 1 renderTargetGroups test button!")
else:
    print("Bot 1 row button already patched or pattern differs.")

# Bot 2 row button
if old_b1 in code:  # After replacing the first occurrence, the second occurrence is Bot 2!
    new_b2 = """          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot2')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">"""
    code = code.replace(old_b1, new_b2, 1)
    print("Patched Bot 2 renderTargetGroups test button!")
else:
    print("Bot 2 row button already patched or pattern differs.")

# Bot 3 row button
old_b3 = """            <div class="flex items-center gap-2">
              <button onclick="toggleTargetGroup('${{g.id}}', ${{!g.enabled}})" class="px-2.5 py-1 rounded-lg text-[11px] font-bold ${{g.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}}">"""

new_b3 = """            <div class="flex items-center gap-2">
              <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot3')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 flex items-center gap-1" title="Gửi tin nhắn test riêng vào nhóm này">
                <i class="fa-solid fa-paper-plane text-[10px]"></i> Test
              </button>
              <button onclick="toggleTargetGroup('${{g.id}}', ${{!g.enabled}})" class="px-2.5 py-1 rounded-lg text-[11px] font-bold ${{g.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}}">"""

if old_b3 in code:
    code = code.replace(old_b3, new_b3, 1)
    print("Patched Bot 3 renderTargetGroups test button!")
else:
    print("Bot 3 row button already patched or pattern differs.")

with open(WEB_APP_PATH, "w", encoding="utf-8") as f:
    f.write(code)

if os.path.exists(VAA_WEB_APP_PATH):
    with open(VAA_WEB_APP_PATH, "w", encoding="utf-8") as f:
        f.write(code)

print("web_app.py and vaa/web_app.py updated successfully!")
