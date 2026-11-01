import os
import sys
import json
import base64
import threading
import requests
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TOKEN = "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"
REPO_NAME = "huit-bot"
DEFAULT_BRANCH = "main"

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

_sync_lock = threading.Lock()
_last_sync_status = {
    "status": "idle",
    "last_sync_time": "",
    "commit_sha": "",
    "message": "Sẵn sàng đồng bộ",
    "error": ""
}

def get_sync_status():
    return _last_sync_status

def push_to_github(source_dir: str = None, commit_message: str = "🔄 Auto-sync from Web Dashboard", repo_name: str = REPO_NAME) -> tuple:
    """
    Đẩy toàn bộ thay đổi trong source_dir lên GitHub bằng Git Database Trees/Blobs/Commits API.
    Không yêu cầu git CLI.
    """
    global _last_sync_status
    if not source_dir:
        source_dir = os.path.dirname(os.path.abspath(__file__))

    acquired = _sync_lock.acquire(blocking=False)
    if not acquired:
        return False, "Đang có tiến trình đồng bộ khác chạy nền. Vui lòng thử lại sau vài giây."

    try:
        _last_sync_status["status"] = "syncing"
        _last_sync_status["message"] = f"Đang đồng bộ: {commit_message}..."

        # 1. Lấy thông tin user
        u_res = requests.get("https://api.github.com/user", headers=HEADERS, timeout=15)
        if u_res.status_code != 200:
            err = f"Token không hợp lệ: {u_res.text}"
            _last_sync_status.update({"status": "error", "error": err, "message": "Lỗi xác thực GitHub"})
            return False, err
        username = u_res.json()["login"]
        repo_url = f"https://api.github.com/repos/{username}/{repo_name}"

        # 2. Lấy parent commit SHA
        ref_res = requests.get(f"{repo_url}/git/refs/heads/{DEFAULT_BRANCH}", headers=HEADERS, timeout=15)
        branch = DEFAULT_BRANCH
        if ref_res.status_code != 200:
            ref_res = requests.get(f"{repo_url}/git/refs/heads/master", headers=HEADERS, timeout=15)
            branch = "master"
        
        parent_commit_sha = ref_res.json()["object"]["sha"] if ref_res.status_code == 200 else None

        # 3. Tạo Blobs cho các tệp
        ignore_files = {".git", "__pycache__", ".vercel", "node_modules"}
        ignore_exts = {".db", ".sqlite", ".pyc", ".log", ".tmp"}
        tree_entries = []

        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in ignore_files]
            for file in files:
                if file in ignore_files or any(file.endswith(ext) for ext in ignore_exts):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, source_dir).replace("\\", "/")

                try:
                    with open(full_path, "rb") as f:
                        content_bytes = f.read()
                    
                    b64_content = base64.b64encode(content_bytes).decode("utf-8")
                    blob_res = requests.post(
                        f"{repo_url}/git/blobs",
                        headers=HEADERS,
                        json={"content": b64_content, "encoding": "base64"},
                        timeout=20
                    )
                    if blob_res.status_code in (200, 201):
                        tree_entries.append({
                            "path": rel_path,
                            "mode": "100755" if rel_path.endswith(".sh") or rel_path.endswith(".bat") else "100644",
                            "type": "blob",
                            "sha": blob_res.json()["sha"]
                        })
                except Exception as ex:
                    print(f"Bỏ qua file {rel_path} do lỗi: {ex}")

        if not tree_entries:
            _last_sync_status.update({"status": "idle", "message": "Không có tệp nào cần đồng bộ."})
            return True, "Không có tệp nào cần tải lên."

        # 4. Tạo Tree
        tree_payload = {"tree": tree_entries}
        if parent_commit_sha:
            tree_payload["base_tree"] = parent_commit_sha

        tree_res = requests.post(f"{repo_url}/git/trees", headers=HEADERS, json=tree_payload, timeout=20)
        if tree_res.status_code not in (200, 201):
            err = f"Lỗi tạo Tree: {tree_res.text}"
            _last_sync_status.update({"status": "error", "error": err})
            return False, err
        new_tree_sha = tree_res.json()["sha"]

        # 5. Tạo Commit
        commit_payload = {
            "message": commit_message,
            "tree": new_tree_sha,
            "parents": [parent_commit_sha] if parent_commit_sha else []
        }
        commit_res = requests.post(f"{repo_url}/git/commits", headers=HEADERS, json=commit_payload, timeout=20)
        if commit_res.status_code not in (200, 201):
            err = f"Lỗi tạo Commit: {commit_res.text}"
            _last_sync_status.update({"status": "error", "error": err})
            return False, err
        new_commit_sha = commit_res.json()["sha"]

        # 6. Cập nhật nhánh
        ref_update = requests.patch(
            f"{repo_url}/git/refs/heads/{branch}",
            headers=HEADERS,
            json={"sha": new_commit_sha, "force": True},
            timeout=20
        )
        if ref_update.status_code in (200, 201):
            now_str = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")
            _last_sync_status.update({
                "status": "success",
                "last_sync_time": now_str,
                "commit_sha": new_commit_sha[:7],
                "message": f"Đồng bộ thành công lúc {now_str} (Commit {new_commit_sha[:7]})",
                "error": ""
            })
            print(f"✅ [GitHub Sync] Đã đồng bộ lên GitHub thành công: Commit {new_commit_sha[:7]} - {commit_message}")
            return True, f"Thành công! Commit {new_commit_sha[:7]}"
        else:
            err = f"Lỗi cập nhật nhánh: {ref_update.text}"
            _last_sync_status.update({"status": "error", "error": err})
            return False, err

    except Exception as e:
        err = f"Ngoại lệ khi đồng bộ GitHub: {e}"
        _last_sync_status.update({"status": "error", "error": err, "message": "Lỗi kết nối GitHub"})
        return False, err
    finally:
        _sync_lock.release()

def push_async(source_dir: str = None, commit_message: str = "🔄 Auto-sync from Web Dashboard"):
    """
    Kích hoạt đồng bộ GitHub trong luồng chạy ngầm để không chặn request của Web Dashboard.
    """
    t = threading.Thread(target=push_to_github, args=(source_dir, commit_message), daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    msg = sys.argv[2] if len(sys.argv) > 2 else "🚀 Thủ công đồng bộ lên GitHub"
    ok, text = push_to_github(src, msg)
    print(text)
