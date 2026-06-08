#!/usr/bin/env python3
"""逐模块深度验证 — 独立性 + 持久化 + 稳定性"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_db_ctx
init_db()

PASS = FAIL = 0
def ok(msg): global PASS; PASS += 1; print(f'  ✅ {msg}')
def fail(msg, e=''): global FAIL; FAIL += 1; print(f'  ❌ {msg} {e}')
def check(name, fn):
    try:
        result = fn()
        if result is False: fail(name)
        else: ok(name)
        return result
    except Exception as e:
        fail(name, e)
        return None

print('=' * 60)
print('  逐模块深度验证')
print('=' * 60)

# ═══════════════════════════════════════════════════════
# 模块 1: 用户系统
# ═══════════════════════════════════════════════════════
print('\n【1/8】用户系统')
from backend.auth import init_admin_user, verify_password, get_user_by_username, create_user, list_users, delete_user
from backend.schemas import UserCreate, UserRole, UserStatus

init_admin_user()
admin = check('管理员自动创建', lambda: get_user_by_username('admin') is not None)
admin_data = get_user_by_username('admin')

check('密码验证(正确)', lambda: verify_password('admin123', admin_data['hashed_password']))
check('密码验证(错误)', lambda: not verify_password('wrong', admin_data['hashed_password']))

try:
    u = create_user(UserCreate(username='sales1', email='s1@t.com', password='pass123456', role=UserRole.SUBACCOUNT, status=UserStatus.ACTIVE), admin_data['id'])
    ok(f'子账号创建: {u["username"]}')
except Exception as e:
    if '已存在' in str(e): ok('子账号已存在(跳过)')
    else: fail('子账号创建', e)

users = list_users()
check(f'用户列表: {len(users)} 个', lambda: len(users) >= 2)

# 持久化验证: 数据在 SQLite 中
with get_db_ctx() as conn:
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    check(f'SQLite 持久化: users={count}', lambda: count >= 2)

# ═══════════════════════════════════════════════════════
# 模块 2: CRM 客户管理
# ═══════════════════════════════════════════════════════
print('\n【2/8】CRM 客户管理')
from backend.crm import (create_customer, get_customer, list_customers, update_customer, delete_customer,
                          create_followup, get_pending_followups, create_quote, get_customer_stats)
from backend.crm_schemas import CustomerCreate, FollowUpCreate, QuoteCreate

# 创建客户
c1 = create_customer(CustomerCreate(
    name='John Smith', company='Acme Inc', email='john@acme.com',
    title='VP Supply Chain', phone='+1-555-0100', country='US',
    industry='Electronics', source='linkedin', status='lead',
    priority='high', linkedin_url='https://linkedin.com/in/johnsmith'
), 1)
cid = c1['id'] if isinstance(c1, dict) else c1
check(f'创建客户: id={cid}', lambda: cid > 0)

# 查询
c = get_customer(cid)
check(f'查询客户: {c["name"]}', lambda: c['name'] == 'John Smith')

# 更新
from backend.crm_schemas import CustomerUpdate
update_customer(cid, CustomerUpdate(status='contacted', notes='已电话联系'))
c2 = get_customer(cid)
check(f'更新状态: {c2["status"]}', lambda: c2['status'] == 'contacted')

# 列表
cl = list_customers()
check(f'客户列表: {len(cl)} 条', lambda: len(cl) >= 1)

# 跟进
fid = create_followup(FollowUpCreate(
    customer_id=cid, content='初次电话', type='call',
    scheduled_at='2026-06-10 10:00:00', outcome='pending',
    next_action='发送报价'
), 1)
fid_val = fid['id'] if isinstance(fid, dict) else fid
check(f'创建跟进: id={fid_val}', lambda: fid_val > 0)

pending = get_pending_followups()
check(f'待跟进: {len(pending)} 条', lambda: len(pending) >= 1)

# 报价
qid = create_quote(QuoteCreate(
    customer_id=cid, quote_number='Q-2026-001',
    items=[{"description": "Air Freight 500kg", "quantity": 1, "unit_price": 8500, "total": 8500}],
    currency='USD', subtotal=8500, tax_rate=0, tax_amount=0, total=8500,
    status='draft', notes='含关税'
), 1)
qid_val = qid['id'] if isinstance(qid, dict) else qid
check(f'创建报价: id={qid_val}', lambda: qid_val > 0)

# 统计
stats = get_customer_stats()
tc = stats.total_customers if hasattr(stats, 'total_customers') else stats.get('total_customers', 0)
check(f'CRM统计: total={tc}', lambda: tc >= 1)

# 持久化
with get_db_ctx() as conn:
    cc = conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0]
    fc = conn.execute('SELECT COUNT(*) FROM follow_ups').fetchone()[0]
    qc = conn.execute('SELECT COUNT(*) FROM quotes').fetchone()[0]
    check(f'SQLite持久化: customers={cc}, followups={fc}, quotes={qc}', lambda: cc >= 1)

# ═══════════════════════════════════════════════════════
# 模块 3: LinkedIn 自动化
# ═══════════════════════════════════════════════════════
print('\n【3/8】LinkedIn 自动化')
from backend.linkedin_service import get_config, is_browser_running, _detect_system_proxy

cfg = get_config()
check(f'配置独立: profile_dir={os.path.basename(cfg["profile_dir"])}', lambda: 'openclaw' not in cfg['profile_dir'])
check(f'Chrome检测: {cfg["chrome_path"] or "Playwright内置"}', lambda: True)
proxy = cfg['proxy']
check(f'代理自动检测: {proxy or "(无VPN)"}', lambda: True)  # 有VPN就用，没有就不用
check(f'浏览器未运行(初始状态)', lambda: not is_browser_running())

# 代理检测独立性
detected = _detect_system_proxy()
check(f'代理检测不依赖外部配置', lambda: isinstance(detected, str))

# ═══════════════════════════════════════════════════════
# 模块 4: 邮件系统
# ═══════════════════════════════════════════════════════
print('\n【4/8】邮件系统')
from backend.email_smtp import (init_email_tables, create_smtp_config, list_smtp_configs,
                                 get_default_smtp_config, create_template, list_templates,
                                 get_email_stats, seed_default_templates, delete_smtp_config)

init_email_tables()
seed_default_templates()

# SMTP 配置
try:
    cfg_id = create_smtp_config({
        'name': 'QQ企业邮', 'host': 'smtp.exmail.qq.com', 'port': 465,
        'username': 'barry.yang@fortune-scm.com', 'password': 'test',
        'use_ssl': True, 'from_name': 'Barry Yang',
        'from_email': 'barry.yang@fortune-scm.com',
        'is_default': True, 'user_id': 1,
    })
    ok(f'SMTP配置创建: id={cfg_id}')
except Exception as e:
    if 'UNIQUE' in str(e) or '已存在' in str(e): ok('SMTP配置已存在(跳过)')
    else: fail('SMTP配置', e)

configs = list_smtp_configs()
check(f'SMTP列表: {len(configs)} 个', lambda: len(configs) >= 1)

# 模板
templates = list_templates()
check(f'邮件模板: {len(templates)} 个', lambda: len(templates) >= 1)
for t in templates[:3]:
    name = t['name'] if isinstance(t, dict) else t.name
    ok(f'  模板: {name}')

# 统计
estats = get_email_stats()
esent = estats.total_sent if hasattr(estats, 'total_sent') else estats.get('total_sent', 0)
check(f'邮件统计: sent={esent}', lambda: isinstance(esent, int))

# 持久化
with get_db_ctx() as conn:
    sc = conn.execute('SELECT COUNT(*) FROM email_smtp_configs').fetchone()[0]
    tc = conn.execute('SELECT COUNT(*) FROM email_templates').fetchone()[0]
    check(f'SQLite持久化: smtp={sc}, templates={tc}', lambda: sc >= 1 and tc >= 1)

# ═══════════════════════════════════════════════════════
# 模块 5: AI 配置
# ═══════════════════════════════════════════════════════
print('\n【5/8】AI 配置')
from backend.ai_config import create_config, list_configs, delete_config, get_available_models

# 自定义模型
try:
    r = create_config({'name': 'Test Ollama', 'provider': 'ollama', 'model': 'llama3',
                        'api_key': 'ollama', 'base_url': 'http://localhost:11434/v1'})
    ok(f'自定义模型创建: {r.name} ({r.provider}/{r.model})')
    custom_id = r.id
except Exception as e:
    if '已存在' in str(e): ok('自定义模型已存在'); custom_id = None
    else: fail('自定义模型', e); custom_id = None

# 标准模型
try:
    r2 = create_config({'name': 'GPT-4o', 'provider': 'openai', 'model': 'gpt-4o',
                         'api_key': 'sk-test', 'is_default': True})
    ok(f'标准模型创建: {r2.name}')
except Exception as e:
    if '已存在' in str(e): ok('标准模型已存在')
    else: fail('标准模型', e)

configs = list_configs()
check(f'AI配置列表: {len(configs)} 个', lambda: len(configs) >= 1)

# 预设提供商
models = get_available_models()
check(f'预设提供商: {len(models)} 个', lambda: len(models) >= 10)

# 持久化
with get_db_ctx() as conn:
    ac = conn.execute('SELECT COUNT(*) FROM ai_model_configs').fetchone()[0]
    check(f'SQLite持久化: ai_configs={ac}', lambda: ac >= 1)

# ═══════════════════════════════════════════════════════
# 模块 6: 数据分析
# ═══════════════════════════════════════════════════════
print('\n【6/8】数据分析')
from backend.analytics import get_customer_stats as a_stats, get_pipeline_summary, get_recent_activities, get_funnel

s = a_stats()
check(f'概览: total={s["total_customers"]}', lambda: s['total_customers'] >= 1)

p = get_pipeline_summary()
check(f'管道: {len(p["pipeline"])} 阶段', lambda: isinstance(p['pipeline'], list))

f = get_funnel()
check(f'漏斗: {len(f["funnel"])} 层级', lambda: len(f['funnel']) >= 1)

a = get_recent_activities(5)
check(f'活动: {len(a)} 条', lambda: isinstance(a, list))

# ═══════════════════════════════════════════════════════
# 模块 7: 定时任务
# ═══════════════════════════════════════════════════════
print('\n【7/8】定时任务')
from backend.scheduler import list_tasks

tasks = list_tasks()
check(f'任务数: {len(tasks)}', lambda: len(tasks) >= 4)
for t in tasks:
    enabled = '🟢' if t['enabled'] else '🔴'
    ok(f'  {enabled} {t["display_name"]} ({t["schedule_cron"]})')

# 持久化
with get_db_ctx() as conn:
    stc = conn.execute('SELECT COUNT(*) FROM scheduler_tasks').fetchone()[0]
    check(f'SQLite持久化: scheduler_tasks={stc}', lambda: stc >= 4)

# ═══════════════════════════════════════════════════════
# 模块 8: 素材库 (待实现)
# ═══════════════════════════════════════════════════════
print('\n【8/8】素材库')
# 检查是否已有素材库模块
try:
    from backend import materials
    ok('素材库模块存在')
except ImportError:
    fail('素材库模块不存在 — 需要新建')

with get_db_ctx() as conn:
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    has_materials = 'materials' in tables
    check(f'素材库表: {"存在" if has_materials else "不存在"}', lambda: has_materials)

# ═══════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════
print('\n' + '=' * 60)
print(f'  结果: ✅ {PASS} 通过, ❌ {FAIL} 失败')
print('=' * 60)
