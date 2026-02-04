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


def test_create_contact(client, test_customer):
    """测试创建联系人"""
    contact_data = {
        'customer_id': test_customer,
        'name': 'John Doe',
        'position': 'CEO',
        'phone': '1234567890',
        'email': 'john@test.com'
    }
    response = client.post('/api/contacts', json=contact_data)
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'John Doe'
    assert data['customer_id'] == test_customer


def test_create_contact_missing_fields(client):
    """测试创建联系人时缺少必填字段"""
    contact_data = {
        'name': 'John Doe'
        # 缺少 customer_id
    }
    response = client.post('/api/contacts', json=contact_data)
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_create_contact_invalid_customer(client):
    """测试创建联系人时使用不存在的客户ID"""
    contact_data = {
        'customer_id': 999,
        'name': 'John Doe'
    }
    response = client.post('/api/contacts', json=contact_data)
    assert response.status_code == 404


def test_get_contact(client, test_customer):
    """测试获取单个联系人"""
    # 先创建联系人
    contact_data = {
        'customer_id': test_customer,
        'name': 'John Doe',
        'position': 'CEO'
    }
    create_response = client.post('/api/contacts', json=contact_data)
    contact_id = create_response.get_json()['id']

    # 获取联系人
    response = client.get(f'/api/contacts/{contact_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['name'] == 'John Doe'


def test_update_contact(client, test_customer):
    """测试更新联系人"""
    # 先创建联系人
    contact_data = {
        'customer_id': test_customer,
        'name': 'John Doe',
        'position': 'CEO'
    }
    create_response = client.post('/api/contacts', json=contact_data)
    contact_id = create_response.get_json()['id']

    # 更新联系人
    update_data = {
        'name': 'John Smith',
        'position': 'CTO'
    }
    response = client.put(f'/api/contacts/{contact_id}', json=update_data)
    assert response.status_code == 200
    data = response.get_json()
    assert data['name'] == 'John Smith'
    assert data['position'] == 'CTO'


def test_delete_contact(client, test_customer):
    """测试删除联系人"""
    # 先创建联系人
    contact_data = {
        'customer_id': test_customer,
        'name': 'John Doe'
    }
    create_response = client.post('/api/contacts', json=contact_data)
    contact_id = create_response.get_json()['id']

    # 删除联系人
    response = client.delete(f'/api/contacts/{contact_id}')
    assert response.status_code == 200

    # 验证已删除
    get_response = client.get(f'/api/contacts/{contact_id}')
    assert get_response.status_code == 404


def test_get_contacts_by_customer(client, test_customer):
    """测试获取属于特定客户的联系人不"""
    # 为同一客户创建多个联系人
    contacts = [
        {'customer_id': test_customer, 'name': 'John Doe'},
        {'customer_id': test_customer, 'name': 'Jane Smith'}
    ]
    for contact_data in contacts:
        client.post('/api/contacts', json=contact_data)

    # 获取所有联系人
    response = client.get('/api/contacts')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
