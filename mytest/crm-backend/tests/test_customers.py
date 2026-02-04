import pytest
from app import create_app
from app.database import db


@pytest.fixture
def app():
    """创建测试应用"""
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """创建测试runner"""
    return app.test_cli_runner()


def test_get_empty_customers(client):
    """测试获取空客户列表"""
    response = client.get('/api/customers')
    assert response.status_code == 200
    data = response.get_json()
    assert data == []


def test_create_customer(client):
    """测试创建客户"""
    customer_data = {
        'name': 'Test Company',
        'industry': 'Technology',
        'website': 'https://test.com',
        'phone': '1234567890',
        'email': 'contact@test.com',
        'address': '123 Test St'
    }
    response = client.post('/api/customers', json=customer_data)
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Test Company'
    assert data['industry'] == 'Technology'
    assert data['id'] is not None


def test_create_customer_missing_name(client):
    """测试创建客户时缺少name字段"""
    customer_data = {
        'industry': 'Technology',
        'email': 'contact@test.com'
    }
    response = client.post('/api/customers', json=customer_data)
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_get_customer(client):
    """测试获取单个客户"""
    # 先创建客户
    customer_data = {
        'name': 'Test Company',
        'industry': 'Technology'
    }
    create_response = client.post('/api/customers', json=customer_data)
    customer_id = create_response.get_json()['id']

    # 获取客户
    response = client.get(f'/api/customers/{customer_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['name'] == 'Test Company'


def test_get_customer_not_found(client):
    """测试获取不存在的客户"""
    response = client.get('/api/customers/999')
    assert response.status_code == 404


def test_update_customer(client):
    """测试更新客户"""
    # 先创建客户
    customer_data = {
        'name': 'Test Company',
        'industry': 'Technology'
    }
    create_response = client.post('/api/customers', json=customer_data)
    customer_id = create_response.get_json()['id']

    # 更新客户
    update_data = {
        'name': 'Updated Company',
        'industry': 'Finance'
    }
    response = client.put(f'/api/customers/{customer_id}', json=update_data)
    assert response.status_code == 200
    data = response.get_json()
    assert data['name'] == 'Updated Company'
    assert data['industry'] == 'Finance'


def test_delete_customer(client):
    """测试删除客户"""
    # 先创建客户
    customer_data = {
        'name': 'Test Company',
        'industry': 'Technology'
    }
    create_response = client.post('/api/customers', json=customer_data)
    customer_id = create_response.get_json()['id']

    # 删除客户
    response = client.delete(f'/api/customers/{customer_id}')
    assert response.status_code == 200

    # 验证已删除
    get_response = client.get(f'/api/customers/{customer_id}')
    assert get_response.status_code == 404


def test_get_multiple_customers(client):
    """测试获取多个客户"""
    # 创建多个客户
    customers = [
        {'name': 'Company A', 'industry': 'Tech'},
        {'name': 'Company B', 'industry': 'Finance'},
        {'name': 'Company C', 'industry': 'Healthcare'}
    ]
    for customer_data in customers:
        client.post('/api/customers', json=customer_data)

    # 获取所有客户
    response = client.get('/api/customers')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 3
