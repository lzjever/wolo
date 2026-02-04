import os


class Config:
    """应用配置类"""
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///crm.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 分页配置
    ITEMS_PER_PAGE = 20
