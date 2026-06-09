#!/usr/bin/env python3
"""Debug API issues"""
import requests
import json

BASE = "http://localhost:8765"

# Login
r = requests.post(BASE + "/api/auth/login", data={"username": "admin", "password": "admin123"})
token = r.json()["access_token"]
headers = {"Authorization": "Bearer " + token}

print("=== CRM 创建客户 ===")
r = requests.post(BASE + "/api/crm/customers", headers=headers, json={
    "name": "测试客户", "company": "Test Co", "email": "test@test.com",
    "country": "美国", "source": "linkedin", "status": "lead"
})
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:300]}")

print("\n=== CRM 查询列表 ===")
r = requests.get(BASE + "/api/crm/customers", headers=headers)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:300]}")

print("\n=== AI Config ===")
for path in ["/api/ai-config/configs", "/api/ai-config", "/api/ai-config/"]:
    r = requests.get(BASE + path, headers=headers)
    print(f"{path}: {r.status_code} {r.text[:100]}")

print("\n=== Materials ===")
for path in ["/api/materials/materials", "/api/materials", "/api/materials/"]:
    r = requests.get(BASE + path, headers=headers)
    print(f"{path}: {r.status_code} {r.text[:100]}")
