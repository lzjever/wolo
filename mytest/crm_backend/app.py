"""
Flask应用主入口
"""
from database import init_db
from flask import Flask, jsonify
from flask_cors import CORS


def create_app():
    """应用工厂函数"""
    app = Flask(__name__)

    # 配置
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

    # 启用CORS
    CORS(app)

    # 导入模型（必须先导入才能创建表）

    # 初始化数据库
    init_db(app)

    # 注册蓝图
    from api.customer_routes import customer_bp
    from api.interaction_routes import interaction_bp
    from api.opportunity_routes import opportunity_bp

    app.register_blueprint(customer_bp, url_prefix='/api/customers')
    app.register_blueprint(interaction_bp, url_prefix='/api/interactions')
    app.register_blueprint(opportunity_bp, url_prefix='/api/opportunities')

    # 健康检查端点
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'message': 'CRM API is running'
        })

    @app.route('/')
    def index():
        return jsonify({
            'message': '欢迎使用简易CRM系统',
            'version': '1.0.0',
            'endpoints': {
                'health': '/api/health',
                'customers': '/api/customers',
                'interactions': '/api/interactions',
                'opportunities': '/api/opportunities'
            }
        })

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
