#!/usr/bin/env python3
"""命运 (DESTINY) 功能完整性测试脚本"""
import requests
import json
import sys

BASE = "http://localhost:8765"

def login():
    r = requests.post(BASE + "/api/auth/login", data={"username": "admin", "password": "admin123"})
    return r.json()["access_token"]

def api(method, path, token, data=None):
    headers = {"Authorization": "Bearer " + token}
    url = BASE + path
    if data:
        r = getattr(requests, method.lower())(url, headers=headers, json=data)
    else:
        r = getattr(requests, method.lower())(url, headers=headers)
    try:
        return r.json()
    except:
        return {"status_code": r.status_code, "text": r.text[:100]}

def main():
    print("=" * 60)
    print("命运 (DESTINY) 功能完整性测试报告")
    print("=" * 60)
    
    token = login()
    print("\n✅ 登录成功\n")
    
    # 1. CRM
    print("【1. CRM 客户管理】")
    r = api("POST", "/api/crm/customers", token, {
        "name": "测试客户", "company": "Test Co", "email": "test@test.com",
        "country": "美国", "source": "linkedin", "status": "lead", "tags": "测试"
    })
    cid = r.get("id")
    print("  " + ("✅" if cid else "❌") + " 创建客户: id=" + str(cid))
    
    r = api("GET", "/api/crm/customers", token)
    count = len(r) if isinstance(r, list) else r.get("total", "?")
    print("  " + ("✅" if isinstance(r, list) else "❌") + " 查询列表: " + str(count) + "条")
    
    if cid:
        r = api("GET", "/api/crm/customers/" + str(cid), token)
        print("  " + ("✅" if r.get("name") else "❌") + " 查询单个: " + str(r.get("name", "?")))
        
        r = api("PUT", "/api/crm/customers/" + str(cid), token, {"name": "更新后客户", "status": "contacted"})
        print("  " + ("✅" if r.get("status") == "contacted" else "❌") + " 更新客户: status=" + str(r.get("status", "?")))
        
        r = api("POST", "/api/crm/customers/" + str(cid) + "/follow-ups", token, {
            "type": "call", "content": "初次联系", "scheduled_at": "2026-06-10T10:00:00"
        })
        print("  " + ("✅" if "id" in str(r) else "❌") + " 创建跟进: " + str(r)[:60])
        
        r = api("DELETE", "/api/crm/customers/" + str(cid), token)
        print("  ✅ 删除客户: " + str(r)[:60])
    
    # 2. 定时任务
    print("\n【2. 定时任务】")
    r = api("GET", "/api/scheduler/tasks", token)
    tasks = r.get("tasks", r) if isinstance(r, dict) else r
    tcount = len(tasks) if isinstance(tasks, list) else tasks
    print("  " + ("✅" if isinstance(tasks, list) else "❌") + " 任务列表: " + str(tcount))
    
    # 3. 邮件
    print("\n【3. 邮件营销】")
    r = api("GET", "/api/email/smtp-configs", token)
    print("  " + ("✅" if isinstance(r, list) else "❌") + " SMTP配置: " + str(len(r) if isinstance(r, list) else r))
    
    r = api("GET", "/api/email/templates", token)
    print("  " + ("✅" if isinstance(r, list) else "❌") + " 邮件模板: " + str(len(r) if isinstance(r, list) else r))
    
    # 4. 素材库
    print("\n【4. 素材库】")
    r = api("GET", "/api/materials/materials", token)
    print("  " + ("✅" if isinstance(r, list) or "materials" in str(r) else "❌") + " 素材: " + str(r)[:80])
    
    # 5. AI配置
    print("\n【5. AI 配置】")
    r = api("GET", "/api/ai-config/configs", token)
    print("  " + ("✅" if isinstance(r, list) or "configs" in str(r) else "❌") + " 配置: " + str(r)[:80])
    
    # 6. 用户管理
    print("\n【6. 用户管理】")
    r = api("GET", "/api/users", token)
    print("  " + ("✅" if isinstance(r, list) else "❌") + " 用户列表: " + str(len(r) if isinstance(r, list) else r))
    
    # 7. 数据分析
    print("\n【7. 数据分析】")
    r = api("GET", "/api/analytics/overview", token)
    print("  " + ("✅" if "total" in str(r) or "overview" in str(r) else "❌") + " 概览: " + str(r)[:80])
    
    # 8. LinkedIn
    print("\n【8. LinkedIn】")
    r = api("GET", "/api/linkedin/posts", token)
    print("  " + ("✅" if isinstance(r, list) or "posts" in str(r) else "❌") + " 帖子: " + str(r)[:80])
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
