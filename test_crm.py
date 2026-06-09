#!/usr/bin/env python3
"""Test CRM API"""
import requests
import json

BASE = "http://127.0.0.1:8765"

# Login
print("=== 测试登录 ===")
r = requests.post(f"{BASE}/api/auth/login", data={"username": "admin", "password": "admin123"})
if r.status_code != 200:
    print(f"❌ 登录失败: {r.text}")
    exit(1)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ 登录成功")

print("\n=== 测试 CRM API ===")

# 1. 创建客户
print("\n1. 创建客户...")
r = requests.post(f"{BASE}/api/crm/contacts", headers=headers, json={
    "name": "测试客户",
    "company": "测试公司",
    "email": "test@example.com",
    "country": "中国",
    "source": "linkedin",
    "status": "lead"
})
if r.status_code == 200:
    customer = r.json()
    customer_id = customer["id"]
    print(f"✅ 创建成功: ID={customer_id}, 名称={customer['name']}")
else:
    print(f"❌ 创建失败 ({r.status_code}): {r.text}")
    customer_id = None

# 2. 获取客户列表
print("\n2. 获取客户列表...")
r = requests.get(f"{BASE}/api/crm/contacts", headers=headers)
if r.status_code == 200:
    customers = r.json()
    print(f"✅ 获取成功: {len(customers)} 个客户")
else:
    print(f"❌ 获取失败 ({r.status_code}): {r.text}")

# 3. 获取单个客户
if customer_id:
    print(f"\n3. 获取单个客户 (ID={customer_id})...")
    r = requests.get(f"{BASE}/api/crm/contacts/{customer_id}", headers=headers)
    if r.status_code == 200:
        c = r.json()
        print(f"✅ 获取成功: {c['name']} - {c['company']}")
    else:
        print(f"❌ 获取失败 ({r.status_code}): {r.text}")

    # 4. 更新客户
    print(f"\n4. 更新客户...")
    r = requests.put(f"{BASE}/api/crm/contacts/{customer_id}", headers=headers, json={
        "name": "测试客户-已更新",
        "company": "新公司"
    })
    if r.status_code == 200:
        c = r.json()
        print(f"✅ 更新成功: {c['name']} - {c['company']}")
    else:
        print(f"❌ 更新失败 ({r.status_code}): {r.text}")

    # 5. 删除客户
    print(f"\n5. 删除客户...")
    r = requests.delete(f"{BASE}/api/crm/contacts/{customer_id}", headers=headers)
    if r.status_code == 200:
        print(f"✅ 删除成功")
    else:
        print(f"❌ 删除失败 ({r.status_code}): {r.text}")

print("\n=== CRM API 测试完成 ===")
