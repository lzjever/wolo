"""
数据库连接和初始化模块
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

# 数据库文件路径
DB_PATH = 'crm.db'


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 允许以字典方式访问行数据
    return conn


@contextmanager
def get_db():
    """数据库上下文管理器"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """初始化数据库，创建所有表"""
    # 创建客户表
    create_customers_table = """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company TEXT,
        email TEXT,
        phone TEXT,
        industry TEXT,
        status TEXT DEFAULT 'active',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    # 创建联系人表
    create_contacts_table = """
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        title TEXT,
        email TEXT,
        phone TEXT,
        is_primary INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """

    # 创建商机表
    create_opportunities_table = """
    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        amount REAL,
        stage TEXT DEFAULT 'prospecting',
        expected_close_date TEXT,
        probability INTEGER DEFAULT 50,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """

    with get_db() as conn:
        conn.execute(create_customers_table)
        conn.execute(create_contacts_table)
        conn.execute(create_opportunities_table)

    print("✓ 数据库初始化完成")


def row_to_dict(row):
    """将数据库行转换为字典"""
    if row:
        return dict(row)
    return None


def update_timestamp():
    """获取当前时间戳"""
    return datetime.now().isoformat()
