import os, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"

for db_path in [os.path.join(ROOT_DIR, "database.py"), os.path.join(ROOT_DIR, "vaa", "ufm", "database.py")]:
    if not os.path.exists(db_path):
        continue
    with open(db_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Patch get_seen_activity
    old_get_seen = """def get_seen_activity(activity_id: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seen_activities WHERE activity_id = ?", (str(activity_id),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None"""

    new_get_seen = """def get_seen_activity(activity_id: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    aid = str(activity_id)
    raw = aid.replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    cursor.execute('''
        SELECT * FROM seen_activities 
        WHERE activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ?
        LIMIT 1
    ''', (aid, f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}", raw))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None"""

    if old_get_seen in content:
        content = content.replace(old_get_seen, new_get_seen)
        print(f"Patched get_seen_activity in {db_path}")

    # 2. Patch update_activity_status
    old_update = """def update_activity_status(activity_id: str, status: str, is_full: bool, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute(\"\"\"
        UPDATE seen_activities
        SET status = ?, is_full = ?, last_updated = ?
        WHERE activity_id = ?
    \"\"\", (status, 1 if is_full else 0, now_vn, str(activity_id)))
    conn.commit()
    conn.close()"""

    new_update = """def update_activity_status(activity_id: str, status: str, is_full: bool, is_sent: bool = None, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    if is_sent is not None:
        cursor.execute('''
            UPDATE seen_activities
            SET status = ?, is_full = ?, is_sent = ?, last_updated = ?
            WHERE activity_id = ?
        ''', (status, 1 if is_full else 0, 1 if is_sent else 0, now_vn, str(activity_id)))
    else:
        cursor.execute('''
            UPDATE seen_activities
            SET status = ?, is_full = ?, last_updated = ?
            WHERE activity_id = ?
        ''', (status, 1 if is_full else 0, now_vn, str(activity_id)))
    conn.commit()
    conn.close()

def update_seen_is_sent(activity_id: str, is_sent: bool = True, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute('''
        UPDATE seen_activities
        SET is_sent = ?, last_updated = ?
        WHERE activity_id = ?
    ''', (1 if is_sent else 0, now_vn, str(activity_id)))
    conn.commit()
    conn.close()"""

    if old_update in content:
        content = content.replace(old_update, new_update)
        print(f"Patched update_activity_status in {db_path}")

    with open(db_path, "w", encoding="utf-8") as f:
        f.write(content)

print("database.py patched successfully!")
