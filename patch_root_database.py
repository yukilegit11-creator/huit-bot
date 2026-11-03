with open(r'C:\Users\Admin\Documents\HUIT\database.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_get_seen = '''def get_seen_activity(activity_id: str, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seen_activities WHERE activity_id = ?", (str(activity_id),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None'''

new_get_seen = '''def get_seen_activity(activity_id: str, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    aid = str(activity_id)
    raw = aid.replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    cursor.execute("""
        SELECT * FROM seen_activities 
        WHERE activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ?
        LIMIT 1
    """, (aid, f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}", raw))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None'''

old_update = '''def update_activity_status(activity_id: str, status: str, slots: str = "", db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        UPDATE seen_activities 
        SET status = ?, slots = ?, last_updated = ? 
        WHERE activity_id = ?
    """, (status, slots, now_vn, str(activity_id)))
    conn.commit()
    conn.close()'''

new_update = '''def update_activity_status(activity_id: str, status: str, slots_or_full=None, is_sent: bool = None, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("PRAGMA table_info(seen_activities)")
    cols = [c[1] for c in cursor.fetchall()]
    
    updates = ["status = ?", "last_updated = ?"]
    params = [status, now_vn]
    
    if "is_full" in cols:
        is_full_val = 1 if (isinstance(slots_or_full, bool) and slots_or_full) or (isinstance(slots_or_full, (int, str)) and str(slots_or_full) in ('1', 'True', 'true')) else 0
        updates.append("is_full = ?")
        params.append(is_full_val)
    if "slots" in cols:
        slots_val = str(slots_or_full) if slots_or_full is not None else ""
        updates.append("slots = ?")
        params.append(slots_val)
    if is_sent is not None and "is_sent" in cols:
        updates.append("is_sent = ?")
        params.append(1 if is_sent else 0)
        
    raw = str(activity_id).replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    update_str = ", ".join(updates)
    query = f"UPDATE seen_activities SET {update_str} WHERE activity_id = ? OR activity_id = ? OR activity_id = ? OR activity_id = ?"
    cursor.execute(query, tuple(params) + (str(activity_id), f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}"))
    conn.commit()
    conn.close()

def update_seen_is_sent(activity_id: str, is_sent: bool = True, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    raw = str(activity_id).replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    cursor.execute("""
        UPDATE seen_activities
        SET is_sent = ?, last_updated = ?
        WHERE activity_id = ? OR activity_id = ? OR activity_id = ? OR activity_id = ?
    """, (1 if is_sent else 0, now_vn, str(activity_id), f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}"))
    conn.commit()
    conn.close()'''

assert old_get_seen in text, 'old_get_seen not found'
assert old_update in text, 'old_update not found'

text = text.replace(old_get_seen, new_get_seen).replace(old_update, new_update)

with open(r'C:\Users\Admin\Documents\HUIT\database.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully patched database.py!')
