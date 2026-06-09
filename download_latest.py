#!/usr/bin/env python3
import subprocess, re, os, shutil

os.environ["https_proxy"] = "http://127.0.0.1:8001"

# Get token
url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"]).decode().strip()
m = re.search(r"ghp_[^@]+", url)
if not m:
    print("No token found")
    exit(1)

os.environ["GH_TOKEN"] = m.group()

# Get latest successful run
result = subprocess.run(
    ["gh", "run", "list", "--limit", "1", "--json", "databaseId,conclusion"],
    capture_output=True, text=True, env=os.environ
)
print("Latest run:", result.stdout)

import json
runs = json.loads(result.stdout)
if not runs or runs[0]["conclusion"] != "success":
    print("No successful build found")
    exit(1)

run_id = runs[0]["databaseId"]
print(f"Downloading run {run_id}...")

# Download artifacts
dest = "/tmp/destiny-latest"
if os.path.exists(dest):
    shutil.rmtree(dest)

result = subprocess.run(
    ["gh", "run", "download", str(run_id), "--dir", dest],
    capture_output=True, text=True, env=os.environ, timeout=120
)
print(result.stdout)
if result.stderr:
    print("ERR:", result.stderr)

# List files
for root, dirs, files in os.walk(dest):
    for f in files:
        path = os.path.join(root, f)
        size = os.path.getsize(path) / 1024 / 1024
        print(f"  {path} ({size:.1f} MB)")
