import sqlite3
import os
import sys
from contextlib import contextmanager

# 支持 PyInstaller 打包
IS_BUNDLED = getattr(sys, '_MEIPASS', None) is not None

if IS_BUNDLED:
    # PyInstaller 打包模式 - 数据目录在可执行文件旁边
    DB_PATH = os.path.join(os.path.dirname(sys.executable), "data", "fortune.db")
else:
    # 开发模式
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fortune.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db_ctx():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_ctx() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
                hashed_password TEXT NOT NULL,
                role TEXT DEFAULT 'subaccount',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                company TEXT,
                title TEXT,
                linkedin_url TEXT,
                email TEXT,
                phone TEXT,
                status TEXT DEFAULT 'new',
                tags TEXT,
                notes TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS follow_ups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                customer_id INTEGER,
                content TEXT NOT NULL,
                follow_up_date TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                customer_id INTEGER,
                content TEXT NOT NULL,
                amount REAL,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ai_model_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                base_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS linkedin_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                params TEXT,
                result TEXT,
                result_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS linkedin_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT NOT NULL,
                image_paths TEXT,
                status TEXT DEFAULT 'draft',
                post_url TEXT,
                likes_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                scheduled_at TEXT,
                published_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        # Default settings
        # Ensure result_count column exists for existing databases
        try:
            conn.execute("ALTER TABLE linkedin_tasks ADD COLUMN result_count INTEGER DEFAULT 0")
        except Exception:
            pass  # column already exists

        defaults = {
            "ai_provider": "openai",
            "ai_api_key": "",
            "ai_model": "gpt-4o",
            "ai_base_url": "",
            "smtp_host": "",
            "smtp_port": "587",
            "smtp_user": "",
            "smtp_password": "",
            "smtp_from": "",
        }
        for k, v in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Initialize email module tables
    from backend.email_smtp import init_email_tables, seed_default_templates
    init_email_tables()
