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
def test_customer(client):
    """创建测试客户"""
    customer_data = {
        'name': 'Test Company',
        'industry': 'Technology'
    }
    response = client.post('/api/customers', json=customer_data)
    return response.get_json()['id']


def test_create_deal(client, test_customer):
    """测试创建交易"""
    deal_data = {
        'customer_id': test_customer,
        'title': 'Software License',
        'description': 'Annual software license contract',
        'amount': 50000.0,
        'status': 'opportunity'
    }
    response = client.post('/api/deals', json=deal_data)
    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'Software License'
    assert data['amount'] == 50000.0
    assert data['status'] == 'opportunity'


def test_create_deal_missing_fields(client):
    """测试创建交易时缺少必填字段"""
    deal_data = {
        'title': 'Software License'
        # 缺少 customer_id
    }
    response = client.post('/api/deals', json=deal_data)
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_create_deal_invalid_customer(client):
    """测试创建交易时使用不存在的客户ID"""
    deal_data = {
        'customer_id': 999,
        'title': 'Software License'
    }
    response = client.post('/api/deals', json=deal_data)
    assert response.status_code == 404


def test_create_deal_invalid_status(client, test_customer):
    """测试创建交易时使用无效的状态"""
    deal_data = {
        'customer_id': test_customer,
        'title': 'Software License',
        'status': 'invalid_status'
    }
    response = client.post('/api/deals', json=deal_data)
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_create_deal_default_status(client, test_customer):
    """测试创建交易时使用默认状态"""
    deal_data = {
        'customer_id': test_customer,
        'title': 'Software License',
        'amount': 10000.0
    }
    response = client.post('/api/deals', json=deal_data)
    assert response.status_code == 201
    data = response.get_json()
    assert data['status'] == 'lead'


def test_get_deal(client, test_customer):
    """测试获取单个交易"""
    # 先创建交易
    deal_data = {
        'customer_id': test_customer,
        'title': 'Software License',
        'status': 'opportunity'
    }
    create_response = client.post('/api/deals', json=deal_data)
    deal_id = create_response.get_json()['id']

    # 获取交易
    response = client.get(f'/api/deals/{deal_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Software License'


def test_update_deal(client, test_customer):
    """测试更新交易"""
    # 先创建交易
    deal_data = {
        'customer_id': test_customer,
        'title': 'Software License',
        'status': 'opportunity'
    }
    create_response = client.post('/api/deals', json=deal_data)
    deal_id = create_response.get_json()['id']

    # 更新交易
    update_data = {
        'status': 'won',
        'amount': 60000.0
    }
    response = client.put(f'/api/deals/{deal_id}', json=update_data)
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'won'
    assert data['amount'] == 60000.0


def test_update_deal_invalid_status(client, test_customer):
    """测试更新交易时使用无效的状态"""
    # 先创建交易
    deal_data = {
        'customer_id': test_customer,
        'title': 'Software License'
    }
    create_response = client.post('/api/deals', json=deal_data)
    deal_id = create_response.get_json()['id']

    # 使用无效状态更新
    update_data = {
        'status': 'invalid_status'
    }
    response = client.put(f'/api/deals/{deal_id}', json=update_data)
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_delete_deal(client, test_customer):
    """测试删除交易"""
    # 先创建交易
    deal_data = {
        'customer_id': test_customer,
        'title': 'Software License'
    }
    create_response = client.post('/api/deals', json=deal_data)
    deal_id = create_response.get_json()['id']

    # 删除交易
    response = client.delete(f'/api/deals/{deal_id}')
    assert response.status_code == 200

    # 验证已删除
    get_response = client.get(f'/api/deals/{deal_id}')
    assert get_response.status_code == 404


def test_get_multiple_deals(client, test_customer):
    """测试获取多个交易"""
    # 创建多个交易
    deals = [
        {'customer_id': test_customer, 'title': 'Deal A', 'amount': 10000.0, 'status': 'lead'},
        {'customer_id': test_customer, 'title': 'Deal B', 'amount': 20000.0, 'status': 'opportunity'},
        {'customer_id': test_customer, 'title': 'Deal C', 'amount': 30000.0, 'status': 'won'}
    ]
    for deal_data in deals:
        client.post('/api/deals', json=deal_data)

    # 获取所有交易
    response = client.get('/api/deals')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 3
