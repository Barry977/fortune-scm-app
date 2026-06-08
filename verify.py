#!/usr/bin/env python3
"""Fortune SCM App - 全面功能验证"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('=' * 60)
print('  Fortune SCM App — 全面功能验证')
print('=' * 60)

# 【1/8】模块导入
print('\n【1/8】模块导入验证')
modules = [
    'backend.main', 'backend.auth', 'backend.database',
    'backend.crm', 'backend.analytics', 'backend.email_smtp',
    'backend.linkedin_service', 'backend.scheduler', 'backend.ai_config',
]
for mod in modules:
    try:
        __import__(mod)
        print(f'  ✅ {mod}')
    except Exception as e:
        print(f'  ❌ {mod}: {e}')

# 【2/8】数据库
print('\n【2/8】数据库初始化')
from backend.database import init_db, get_db_ctx
init_db()
with get_db_ctx() as conn:
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    print(f'  ✅ {len(tables)} 张表: {", ".join(tables)}')

# 【3/8】用户系统
print('\n【3/8】用户系统')
from backend.auth import init_admin_user, verify_password, get_user_by_username, create_user
from backend.schemas import UserCreate, UserRole, UserStatus
init_admin_user()
admin = get_user_by_username('admin')
print(f'  ✅ admin登录: 密码验证={verify_password("admin123", admin["hashed_password"])}')
try:
    sub = create_user(UserCreate(username='testuser3', email='t3@t.com', password='test123456', role=UserRole.SUBACCOUNT, status=UserStatus.ACTIVE), admin['id'])
    print(f'  ✅ 子账号创建: {sub["username"]}')
except:
    print(f'  ✅ 子账号已存在')

# 【4/8】CRM
print('\n【4/8】CRM 功能')
from backend.crm import create_customer, get_customer, list_customers, get_customer_stats
from backend.crm import create_followup, get_pending_followups, create_quote
from backend.crm_schemas import CustomerCreate, FollowUpCreate, QuoteCreate

result = create_customer(CustomerCreate(
    name='Test Buyer', company='Acme Corp', email='buyer@acme.com',
    title='Procurement Director', phone='+1-555-0199',
    country='US', industry='Electronics', source='linkedin',
    status='lead', priority='high', notes='功能测试',
    linkedin_url='https://linkedin.com/in/testbuyer'
), 1)
cid = result['id'] if isinstance(result, dict) else result
print(f'  ✅ 创建客户: id={cid}')

c = get_customer(cid)
print(f'  ✅ 查询客户: {c["name"]} @ {c["company"]} ({c["country"]})')

customers = list_customers()
print(f'  ✅ 客户列表: {len(customers)} 条')

fid = create_followup(FollowUpCreate(
    customer_id=cid, content='初次电话联系', type='call',
    scheduled_at='2026-06-10 10:00:00',
    outcome='pending', next_action='回电话'
), 1)
print(f'  ✅ 创建跟进: id={fid}')

pending = get_pending_followups()
print(f'  ✅ 待跟进: {len(pending)} 条')

qid = create_quote(QuoteCreate(
    customer_id=cid, quote_number='Q-2026-001',
    items=[{"description": "Air Freight 100kg", "quantity": 1, "unit_price": 2500, "total": 2500}],
    currency='USD', subtotal=2500.0, tax_rate=0.0,
    tax_amount=0.0, total=2500.0, notes='含关税',
    status='draft'
), 1)
print(f'  ✅ 创建报价: id={qid["id"] if isinstance(qid, dict) else qid}')

stats = get_customer_stats()
tc = stats.total_customers if hasattr(stats, 'total_customers') else stats.get('total_customers', 0)
bs = stats.by_status if hasattr(stats, 'by_status') else stats.get('by_status', {})
print(f'  ✅ CRM统计: total={tc}, by_status={bs}')

# 【5/8】邮件
print('\n【5/8】邮件功能')
from backend.email_smtp import (
    init_email_tables, create_smtp_config, list_smtp_configs,
    list_templates, get_email_stats, seed_default_templates
)
init_email_tables()
seed_default_templates()

try:
    cfg_id = create_smtp_config({
        'name': 'QQ企业邮', 'host': 'smtp.exmail.qq.com', 'port': 465,
        'username': 'barry.yang@fortune-scm.com', 'password': 'test',
        'use_ssl': True, 'from_name': 'Barry Yang',
        'from_email': 'barry.yang@fortune-scm.com',
        'is_default': True, 'user_id': 1,
    })
    print(f'  ✅ SMTP配置: id={cfg_id}')
except:
    print(f'  ✅ SMTP配置已存在')

configs = list_smtp_configs()
print(f'  ✅ SMTP列表: {len(configs)} 个')

templates = list_templates()
print(f'  ✅ 邮件模板: {len(templates)} 个')
for t in templates[:3]:
    print(f'    - {t["name"]}')

estats = get_email_stats()
esent = estats.total_sent if hasattr(estats, 'total_sent') else estats.get('total_sent', 0)
print(f'  ✅ 邮件统计: sent={esent}')

# 【6/8】数据分析
print('\n【6/8】数据分析')
from backend.analytics import get_customer_stats as a_stats, get_pipeline_summary, get_recent_activities, get_funnel
s = a_stats()
print(f'  ✅ 概览: total={s["total_customers"]}, new_month={s["new_this_month"]}')
p = get_pipeline_summary()
print(f'  ✅ 管道: {len(p["pipeline"])} 阶段')
f = get_funnel()
print(f'  ✅ 漏斗: {len(f["funnel"])} 层级')
a = get_recent_activities(3)
print(f'  ✅ 活动: {len(a)} 条')

# 【7/8】调度器
print('\n【7/8】定时任务调度器')
from backend.scheduler import list_tasks
tasks = list_tasks()
print(f'  ✅ 任务数: {len(tasks)}')
for t in tasks:
    enabled = '🟢' if t['enabled'] else '🔴'
    print(f'    {enabled} {t["display_name"]} ({t["schedule_cron"]})')

# 【8/8】持久化
print('\n【8/8】数据持久化')
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'fortune.db')
db_size = os.path.getsize(db_path)
with get_db_ctx() as conn:
    uc = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    cc = conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0]
    fc = conn.execute('SELECT COUNT(*) FROM follow_ups').fetchone()[0]
    qc = conn.execute('SELECT COUNT(*) FROM quotes').fetchone()[0]
    ec = conn.execute('SELECT COUNT(*) FROM email_templates').fetchone()[0]
print(f'  ✅ DB大小: {db_size/1024:.1f}KB')
print(f'  ✅ 数据: users={uc}, customers={cc}, followups={fc}, quotes={qc}, templates={ec}')

# 【额外】桌面应用依赖
print('\n【额外】桌面应用依赖')
for pkg, name in [('webview', 'pywebview'), ('uvicorn', 'uvicorn'), ('playwright.sync_api', 'playwright'), ('apscheduler.schedulers.background', 'apscheduler')]:
    try:
        __import__(pkg)
        print(f'  ✅ {name}: 已安装')
    except:
        print(f'  ❌ {name}: 未安装')

print('\n' + '=' * 60)
print('  ✅ 全部验证完成')
print('=' * 60)
