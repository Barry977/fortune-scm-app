#!/usr/bin/env python3
"""Upload file to Feishu and send as file message."""
import json, os, sys

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

APP_ID = "cli_aa8e2b361638dbc1"
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
CHAT_ID = "oc_2d35731e1038be55bed426166146af33"
FILE_PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/mima1111/projects/fortune-scm-app/dist/Destiny-CRM-macOS.zip"
PROXY = os.environ.get("https_proxy", os.environ.get("HTTPS_PROXY", ""))

proxies = {"https": PROXY, "http": PROXY} if PROXY else None

# 1. Get token
print("1. Getting tenant access token...")
r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}, proxies=proxies)
token = r.json().get("tenant_access_token", "")
if not token:
    print(f"Failed: {r.json()}")
    sys.exit(1)
print(f"   Token OK")

# 2. Upload file
print(f"2. Uploading {FILE_PATH} ({os.path.getsize(FILE_PATH) / 1024 / 1024:.1f}MB)...")
headers = {"Authorization": f"Bearer {token}"}
with open(FILE_PATH, "rb") as f:
    r2 = requests.post("https://open.feishu.cn/open-apis/im/v1/files",
        headers=headers,
        data={"file_type": "stream", "file_name": os.path.basename(FILE_PATH)},
        files={"file": f},
        proxies=proxies,
        timeout=120)
file_key = r2.json().get("data", {}).get("file_key", "")
if not file_key:
    print(f"Upload failed: {r2.json()}")
    sys.exit(1)
print(f"   file_key: {file_key}")

# 3. Send file message
print("3. Sending file message...")
r3 = requests.post("https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
    headers={**headers, "Content-Type": "application/json"},
    json={
        "receive_id": CHAT_ID,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key})
    },
    proxies=proxies,
    timeout=30)
if r3.json().get("code") == 0:
    print("✅ File sent successfully!")
else:
    print(f"Send failed: {r3.json()}")
