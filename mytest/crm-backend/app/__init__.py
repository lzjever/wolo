from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.database import db
from app.models import Contact, Customer, Deal


def create_app(config_class=Config):
    """应用工厂函数"""
    app = Flask(__name__)

    # 如果传入的是字典配置（用于测试），则使用update
    if isinstance(config_class, dict):
        app.config.from_object(Config)
        app.config.update(config_class)
    else:
        app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)
    CORS(app)

    # 创建数据库表
    with app.app_context():
        db.create_all()

    # 注册蓝图
    from app.routes.contacts import contact_bp
    from app.routes.customers import customer_bp
    from app.routes.deals import deal_bp

    app.register_blueprint(customer_bp, url_prefix='/api/customers')
    app.register_blueprint(contact_bp, url_prefix='/api/contacts')
    app.register_blueprint(deal_bp, url_prefix='/api/deals')

    # 根路径
    @app.route('/')
    def index():
        return {
            'message': 'CRM Backend API',
            'version': '1.0.0',
            'endpoints': {
                'customers': '/api/customers',
                'contacts': '/api/contacts',
                'deals': '/api/deals'
            }
        }

    return app
