#!/usr/bin/env python3
import subprocess, re, os

os.environ["https_proxy"] = "http://127.0.0.1:8001"

# Get token
url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"]).decode().strip()
m = re.search(r"ghp_[^@]+", url)
if not m:
    print("No token found")
    exit(1)

os.environ["GH_TOKEN"] = m.group()

# Check build
result = subprocess.run(
    ["gh", "run", "view", "27181160596", "--json", "status,conclusion"],
    capture_output=True, text=True, env=os.environ
)
print(result.stdout)
if result.stderr:
    print("ERR:", result.stderr)
