import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"
VPS_BASE = os.path.join(ROOT_DIR, "web_app_vps.py")
DEST_ROOT = os.path.join(ROOT_DIR, "web_app.py")
DEST_VAA = os.path.join(ROOT_DIR, "vaa", "web_app.py")
DEST_UFM = os.path.join(ROOT_DIR, "vaa", "ufm", "web_app.py")

with open(VPS_BASE, "r", encoding="utf-8") as f:
    base = f.read()

# 1. Add time, asyncio imports
base = base.replace(
    "import sqlite3\n",
    "import sqlite3\nimport time\nimport asyncio\n",
    1
)

# 2. Add quad target groups and testing endpoints
api_endpoints_block = '''
# ==================== QUAD BOT ZALO TESTING ENDPOINTS ====================

@app.get("/api/zalo/quad-target-groups")
def api_quad_target_groups():
    """Lấy danh sách toàn bộ các nhóm mục tiêu Zalo của cả 4 Bot để phục vụ kiểm tra/bắn tin."""
    bots_cfg = [
        {"bot_id": "bot1", "name": "Bot 1 - HUIT (Yuki 1)", "cfg_path": CONFIG_FILE},
        {"bot_id": "bot2", "name": "Bot 2 - VAA (Yuki 2)", "cfg_path": os.path.join(SCRIPT_DIR, "vaabot.json")},
        {"bot_id": "bot3", "name": "Bot 3 - IUH (Yuki 3 ĐRL)", "cfg_path": os.path.join(SCRIPT_DIR, "config_iuh.json")},
        {"bot_id": "bot4", "name": "Bot 4 - UFM (Yuki 4 ĐRL)", "cfg_path": os.path.join(SCRIPT_DIR, "config_ufm.json")},
    ]
    result = []
    for b in bots_cfg:
        cfg_p = b["cfg_path"]
        groups = []
        if os.path.exists(cfg_p):
            try:
                with open(cfg_p, "r", encoding="utf-8") as fp:
                    cdata = json.load(fp)
                    groups = cdata.get("zalo", {}).get("target_groups", [])
            except Exception as e:
                print(f"Lỗi đọc config {cfg_p}: {e}")
        result.append({
            "bot_id": b["bot_id"],
            "bot_name": b["name"],
            "config_path": cfg_p,
            "groups": groups
        })
    return {"status": "ok", "bots": result}

@app.post("/api/zalo/send-test-target")
async def api_send_test_target(req: Request):
    """Bắn tin nhắn thử nghiệm tới 1 nhóm hoặc người nhận cụ thể của bất kỳ Bot nào trong 4 Bot."""
    try:
        data = await req.json()
    except Exception:
        data = {}

    bot_id = data.get("bot_id", "bot1")
    target_id = str(data.get("target_id", "")).strip()
    target_type = data.get("target_type", "GROUP")
    target_name = data.get("target_name", target_id)
    custom_msg = data.get("custom_message", None)

    if not target_id:
        raise HTTPException(status_code=400, detail="Thiếu target_id (ID nhóm hoặc người nhận)!")

    bot_map = {
        "bot1": {"name": "Bot 1 - HUIT (Yuki 1)", "cfg": CONFIG_FILE, "db": database.DB_FILE},
        "bot2": {"name": "Bot 2 - VAA (Yuki 2)", "cfg": os.path.join(SCRIPT_DIR, "vaabot.json"), "db": database.BOT2_DB_FILE},
        "bot3": {"name": "Bot 3 - IUH (Yuki 3 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_iuh.json"), "db": database.IUH_DB_FILE},
        "bot4": {"name": "Bot 4 - UFM (Yuki 4 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_ufm.json"), "db": database.UFM_DB_FILE},
    }

    bot_info = bot_map.get(bot_id, bot_map["bot1"])
    from zalo_sender import ZaloDispatcher
    dispatcher = ZaloDispatcher(bot_info["cfg"], db_file=bot_info["db"])
    dispatcher.bot_name = bot_info["name"]

    ok, msg = dispatcher.send_test_message_to_target(
        target_id=target_id,
        target_type=target_type,
        custom_text=custom_msg,
        db_file=bot_info["db"]
    )
    if ok:
        return {
            "status": "ok",
            "success": True,
            "message": msg,
            "target_name": target_name,
            "target_id": target_id,
            "bot_name": bot_info["name"]
        }
    else:
        raise HTTPException(status_code=500, detail=f"[{bot_info['name']}] {msg}")

@app.post("/api/zalo/send-test-all-groups")
async def api_send_test_all_groups(req: Request):
    """Bắn tin nhắn thử nghiệm tới toàn bộ các nhóm đang bật của 1 Bot."""
    try:
        data = await req.json()
    except Exception:
        data = {}

    bot_id = data.get("bot_id", "bot1")
    bot_map = {
        "bot1": {"name": "Bot 1 - HUIT (Yuki 1)", "cfg": CONFIG_FILE, "db": database.DB_FILE},
        "bot2": {"name": "Bot 2 - VAA (Yuki 2)", "cfg": os.path.join(SCRIPT_DIR, "vaabot.json"), "db": database.BOT2_DB_FILE},
        "bot3": {"name": "Bot 3 - IUH (Yuki 3 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_iuh.json"), "db": database.IUH_DB_FILE},
        "bot4": {"name": "Bot 4 - UFM (Yuki 4 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_ufm.json"), "db": database.UFM_DB_FILE},
    }

    bot_info = bot_map.get(bot_id, bot_map["bot1"])
    from zalo_sender import ZaloDispatcher
    dispatcher = ZaloDispatcher(bot_info["cfg"], db_file=bot_info["db"])
    dispatcher.bot_name = bot_info["name"]

    with open(bot_info["cfg"], "r", encoding="utf-8") as fp:
        cfg_data = json.load(fp)

    tgs = [g for g in cfg_data.get("zalo", {}).get("target_groups", []) if g.get("enabled", True)]
    results = []
    for g in tgs:
        ok, msg = dispatcher.send_test_message_to_target(
            target_id=str(g["id"]),
            target_type=g.get("type", "GROUP"),
            db_file=bot_info["db"]
        )
        results.append({
            "id": g["id"],
            "name": g.get("name"),
            "success": ok,
            "message": msg
        })
        await asyncio.sleep(1)

    succ_count = sum(1 for r in results if r["success"])
    return {
        "status": "ok",
        "bot_name": bot_info["name"],
        "total": len(tgs),
        "success_count": succ_count,
        "details": results
    }

@app.post("/api/zalo/send-demo-alert")
@app.post("/api/ufm/send-demo-alert")
def api_master_send_demo_alert():
    """Gửi bài viết/hoạt động thông báo vào nhóm demo (ID: 7456361874031804652)."""
    # 1. Ưu tiên gửi từ UFM Dispatcher
    try:
        from vaa.ufm.zalo_sender import ZaloDispatcher as UFMDispatcher
        ufm_cfg = os.path.join(SCRIPT_DIR, "config_ufm.json")
        ufm_db = os.path.join(SCRIPT_DIR, "vaa", "ufm", "ufm_bot.db")
        dispatcher = UFMDispatcher(ufm_cfg, db_file=ufm_db)
        ok, msg = dispatcher.send_demo_group_alert(db_file=ufm_db)
        if ok:
            return {"status": "ok", "success": True, "message": msg}
    except Exception as e:
        print(f"⚠️ [UFM Demo Alert] Lỗi Dispatcher UFM: {e}")

    # 2. Thử gửi từ Master Dispatcher
    try:
        dispatcher = ZaloDispatcher(CONFIG_FILE)
        if hasattr(dispatcher, "send_demo_group_alert"):
            ok, msg = dispatcher.send_demo_group_alert()
            return {"status": "ok" if ok else "error", "success": ok, "message": msg}
        else:
            return api_test_zalo_alert()
    except Exception as e:
        return {"status": "error", "success": False, "message": str(e)}
'''

# Insert the endpoints block right before @app.get("/api/messenger/status")
pos_insert = base.find('@app.get("/api/messenger/status")')
if pos_insert != -1:
    base = base[:pos_insert] + api_endpoints_block + "\n" + base[pos_insert:]
    print("Inserted Quad Test endpoints!")

# 3. Add Top Navbar button for Quad Test Modal across Bot 1, Bot 2, Bot 3
nav_btn_html = """        <!-- TEST ZALO 4 BOT MODAL BUTTON -->
        <button onclick="openQuadTestModal()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-xs transition flex items-center gap-1.5" title="Mở bảng kiểm tra & bắn tin nhắn test cho từng nhóm Zalo của 4 Bot">
          <i class="fa-solid fa-vial-circle-check"></i>
          <span>Test Nhóm Zalo (4 Bot)</span>
        </button>
"""

# Replace in Bot 1 navbar
base = base.replace(
    '<button id="btn-sync-github-bot1"',
    nav_btn_html + '        <button id="btn-sync-github-bot1"',
    1
)

# Replace in Bot 2 navbar
base = base.replace(
    '<button id="btn-sync-github-bot2"',
    nav_btn_html + '        <button id="btn-sync-github-bot2"',
    1
)

# Replace in Bot 3 navbar
base = base.replace(
    '<button id="btn-sync-github-bot3"',
    nav_btn_html + '        <button id="btn-sync-github-bot3"',
    1
)
print("Added navbar buttons across Bot 1, 2, 3!")

# 4. Add row Test button to Bot 1, Bot 2, Bot 3
row_btn_bot1 = """          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot1')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">"""

row_btn_bot2 = """          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot2')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">"""

old_row_btn_b1_b2 = """          <div class="flex items-center gap-3">
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">"""

base = base.replace(old_row_btn_b1_b2, row_btn_bot1, 1)
base = base.replace(old_row_btn_b1_b2, row_btn_bot2, 1)

old_row_btn_b3 = """            <div class="flex items-center gap-2">
              <button onclick="toggleTargetGroup('${{g.id}}', ${{!g.enabled}})" class="px-2.5 py-1 rounded-lg text-[11px] font-bold ${{g.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}}">"""

row_btn_bot3 = """            <div class="flex items-center gap-2">
              <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot3')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 flex items-center gap-1" title="Gửi tin nhắn test riêng vào nhóm này">
                <i class="fa-solid fa-paper-plane text-[10px]"></i> Test
              </button>
              <button onclick="toggleTargetGroup('${{g.id}}', ${{!g.enabled}})" class="px-2.5 py-1 rounded-lg text-[11px] font-bold ${{g.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}}">"""

base = base.replace(old_row_btn_b3, row_btn_bot3, 1)
print("Replaced row buttons for Bot 1, Bot 2, Bot 3!")

# 5. Add the Modal & Script before </body>
with open(os.path.join(ROOT_DIR, "test_fstring_modal.py"), "r", encoding="utf-8") as mf:
    modal_script_src = mf.read()

# Extract fstring_modal_html
fstring_modal_html = modal_script_src.split('fstring_modal_html = raw_modal_html.replace("{", "{{").replace("}", "}}")')[0]
# Actually, let's just generate fstring_modal_html directly
import test_fstring_modal
modal_fstring = test_fstring_modal.fstring_modal_html

# Inject before </body>
base = base.replace("</body>", modal_fstring + "\n</body>")
print("Injected quad test modal before all </body> tags!")

# 6. Test compilation
print("Testing compilation of reconstructed web_app...")
compile(base, 'web_app.py', 'exec')
print("Compilation SUCCESSFUL! ZERO SYNTAX ERRORS!")

# 7. Write to web_app.py and vaa/web_app.py
with open(DEST_ROOT, "w", encoding="utf-8") as f:
    f.write(base)
print("Saved C:\\Users\\Admin\\Documents\\HUIT\\web_app.py")

if os.path.exists(DEST_VAA):
    with open(DEST_VAA, "w", encoding="utf-8") as f:
        f.write(base)
    print("Saved C:\\Users\\Admin\\Documents\\HUIT\\vaa\\web_app.py")

# 8. Check UFM web_app compilation
with open(DEST_UFM, "r", encoding="utf-8") as f:
    ufm_code = f.read()

compile(ufm_code, 'ufm_web_app.py', 'exec')
print("Compilation of vaa/ufm/web_app.py SUCCESSFUL!")
print("ALL DONE PERFECTLY!")
