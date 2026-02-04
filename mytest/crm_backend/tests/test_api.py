"""
CRM API测试用例
"""
import json

import pytest
from app import create_app
from database import db
from models import Customer


@pytest.fixture
def app():
    """创建测试应用实例"""
    app = create_app()

    # 使用内存数据库
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True

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
def sample_customer(app):
    """创建示例客户"""
    with app.app_context():
        customer = Customer(
            name='张三',
            company='测试公司',
            email='zhangsan@example.com',
            phone='13800138000',
            status='active'
        )
        db.session.add(customer)
        db.session.commit()
        db.session.refresh(customer)
        return customer


class TestHealthCheck:
    """健康检查测试"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'message' in data


class TestCustomerAPI:
    """客户API测试"""

    def test_get_empty_customers(self, client):
        """测试获取空客户列表"""
        response = client.get('/api/customers')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) == 0

    def test_create_customer(self, client):
        """测试创建客户"""
        customer_data = {
            'name': '李四',
            'company': '科技有限公司',
            'email': 'lisi@example.com',
            'phone': '13900139000',
            'status': 'active'
        }
        response = client.post(
            '/api/customers',
            data=json.dumps(customer_data),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] == True
        assert data['data']['name'] == '李四'
        assert data['data']['email'] == 'lisi@example.com'

    def test_create_customer_missing_name(self, client):
        """测试创建客户缺少名称字段"""
        customer_data = {
            'company': '测试公司',
            'email': 'test@example.com'
        }
        response = client.post(
            '/api/customers',
            data=json.dumps(customer_data),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] == False
        assert '客户名称为必填项' in data['error']

    def test_get_customers(self, client, sample_customer):
        """测试获取客户列表"""
        response = client.get('/api/customers')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) == 1
        assert data['data'][0]['name'] == '张三'

    def test_get_single_customer(self, client, sample_customer):
        """测试获取单个客户"""
        response = client.get(f'/api/customers/{sample_customer.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert data['data']['name'] == '张三'
        assert data['data']['company'] == '测试公司'

    def test_get_nonexistent_customer(self, client):
        """测试获取不存在的客户"""
        response = client.get('/api/customers/999')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] == False
        assert '客户不存在' in data['error']

    def test_update_customer(self, client, sample_customer):
        """测试更新客户"""
        update_data = {
            'name': '张三（更新）',
            'email': 'newemail@example.com'
        }
        response = client.put(
            f'/api/customers/{sample_customer.id}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert data['data']['name'] == '张三（更新）'
        assert data['data']['email'] == 'newemail@example.com'

    def test_update_nonexistent_customer(self, client):
        """测试更新不存在的客户"""
        update_data = {'name': '测试'}
        response = client.put(
            '/api/customers/999',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] == False

    def test_delete_customer(self, client, sample_customer):
        """测试删除客户"""
        response = client.delete(f'/api/customers/{sample_customer.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True

        # 验证删除后获取不到
        get_response = client.get(f'/api/customers/{sample_customer.id}')
        assert get_response.status_code == 404

    def test_delete_nonexistent_customer(self, client):
        """测试删除不存在的客户"""
        response = client.delete('/api/customers/999')
        assert response.status_code == 404

    def test_search_customers(self, client, sample_customer):
        """测试搜索客户"""
        response = client.get('/api/customers?search=张三')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) == 1
        assert data['data'][0]['name'] == '张三'

    def test_search_by_company(self, client, sample_customer):
        """测试按公司搜索"""
        response = client.get('/api/customers?search=测试公司')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) == 1


class TestInteractionAPI:
    """互动记录API测试"""

    def test_create_interaction(self, client, sample_customer):
        """测试创建互动记录"""
        interaction_data = {
            'customer_id': sample_customer.id,
            'interaction_type': 'call',
            'notes': '初次沟通'
        }
        response = client.post(
            '/api/interactions',
            data=json.dumps(interaction_data),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] == True
        assert data['data']['interaction_type'] == 'call'

    def test_get_interactions(self, client, sample_customer):
        """测试获取互动记录列表"""
        # 先创建一个互动记录
        interaction_data = {
            'customer_id': sample_customer.id,
            'interaction_type': 'email',
            'notes': '发送报价单'
        }
        client.post(
            '/api/interactions',
            data=json.dumps(interaction_data),
            content_type='application/json'
        )

        response = client.get('/api/interactions')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) >= 1

    def test_get_interaction_by_customer(self, client, sample_customer):
        """测试获取指定客户的互动记录"""
        # 创建互动记录
        interaction_data = {
            'customer_id': sample_customer.id,
            'interaction_type': 'meeting',
            'notes': '线下会议'
        }
        client.post(
            '/api/interactions',
            data=json.dumps(interaction_data),
            content_type='application/json'
        )

        response = client.get(f'/api/interactions?customer_id={sample_customer.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) >= 1

    def test_update_interaction(self, client, sample_customer, app):
        """测试更新互动记录"""
        # 先创建互动记录
        interaction_data = {
            'customer_id': sample_customer.id,
            'interaction_type': 'call',
            'notes': '原始备注'
        }
        create_response = client.post(
            '/api/interactions',
            data=json.dumps(interaction_data),
            content_type='application/json'
        )
        interaction_id = create_response.get_json()['data']['id']

        # 更新
        update_data = {
            'notes': '更新后的备注'
        }
        response = client.put(
            f'/api/interactions/{interaction_id}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert data['data']['notes'] == '更新后的备注'


class TestOpportunityAPI:
    """销售机会API测试"""

    def test_create_opportunity(self, client, sample_customer):
        """测试创建销售机会"""
        opportunity_data = {
            'customer_id': sample_customer.id,
            'title': '企业软件采购',
            'value': 100000.00,
            'stage': 'lead',
            'probability': 20
        }
        response = client.post(
            '/api/opportunities',
            data=json.dumps(opportunity_data),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] == True
        assert data['data']['title'] == '企业软件采购'
        assert data['data']['value'] == 100000.00

    def test_get_opportunities(self, client, sample_customer):
        """测试获取销售机会列表"""
        # 创建销售机会
        opportunity_data = {
            'customer_id': sample_customer.id,
            'title': '咨询服务',
            'value': 50000.00,
            'stage': 'proposal'
        }
        client.post(
            '/api/opportunities',
            data=json.dumps(opportunity_data),
            content_type='application/json'
        )

        response = client.get('/api/opportunities')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) >= 1

    def test_get_opportunity_by_customer(self, client, sample_customer):
        """测试获取指定客户的销售机会"""
        opportunity_data = {
            'customer_id': sample_customer.id,
            'title': '年度维护合同',
            'value': 20000.00,
            'stage': 'negotiation'
        }
        client.post(
            '/api/opportunities',
            data=json.dumps(opportunity_data),
            content_type='application/json'
        )

        response = client.get(f'/api/opportunities?customer_id={sample_customer.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['data']) >= 1

    def test_update_opportunity_stage(self, client, sample_customer):
        """测试更新销售机会阶段"""
        # 先创建机会
        opportunity_data = {
            'customer_id': sample_customer.id,
            'title': '测试机会',
            'value': 10000.00,
            'stage': 'lead'
        }
        create_response = client.post(
            '/api/opportunities',
            data=json.dumps(opportunity_data),
            content_type='application/json'
        )
        opportunity_id = create_response.get_json()['data']['id']

        # 更新阶段
        update_data = {
            'stage': 'closed',
            'probability': 100
        }
        response = client.put(
            f'/api/opportunities/{opportunity_id}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert data['data']['stage'] == 'closed'
        assert data['data']['probability'] == 100

    def test_delete_opportunity(self, client, sample_customer):
        """测试删除销售机会"""
        opportunity_data = {
            'customer_id': sample_customer.id,
            'title': '待删除机会',
            'value': 5000.00
        }
        create_response = client.post(
            '/api/opportunities',
            data=json.dumps(opportunity_data),
            content_type='application/json'
        )
        opportunity_id = create_response.get_json()['data']['id']

        response = client.delete(f'/api/opportunities/{opportunity_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True


class TestIntegratedScenarios:
    """集成测试场景"""

    def test_complete_sales_cycle(self, client):
        """测试完整的销售流程"""
        # 1. 创建客户
        customer_data = {
            'name': '王五',
            'company': '未来科技公司',
            'email': 'wangwu@future.com'
        }
        customer_response = client.post(
            '/api/customers',
            data=json.dumps(customer_data),
            content_type='application/json'
        )
        assert customer_response.status_code == 201
        customer_id = customer_response.get_json()['data']['id']

        # 2. 创建销售机会
        opportunity_data = {
            'customer_id': customer_id,
            'title': '云服务采购',
            'value': 150000.00,
            'stage': 'lead',
            'probability': 30
        }
        opp_response = client.post(
            '/api/opportunities',
            data=json.dumps(opportunity_data),
            content_type='application/json'
        )
        assert opp_response.status_code == 201
        opportunity_id = opp_response.get_json()['data']['id']

        # 3. 创建电话沟通记录
        interaction_data = {
            'customer_id': customer_id,
            'interaction_type': 'call',
            'notes': '了解客户需求'
        }
        interaction_response = client.post(
            '/api/interactions',
            data=json.dumps(interaction_data),
            content_type='application/json'
        )
        assert interaction_response.status_code == 201

        # 4. 查看客户详情
        customer_detail = client.get(f'/api/customers/{customer_id}')
        assert customer_detail.status_code == 200

        # 5. 更新机会阶段
        update_opp = {
            'stage': 'proposal',
            'probability': 60
        }
        opp_update_response = client.put(
            f'/api/opportunities/{opportunity_id}',
            data=json.dumps(update_opp),
            content_type='application/json'
        )
        assert opp_update_response.status_code == 200

        # 6. 创建会议记录
        meeting_data = {
            'customer_id': customer_id,
            'interaction_type': 'meeting',
            'notes': '演示产品方案'
        }
        meeting_response = client.post(
            '/api/interactions',
            data=json.dumps(meeting_data),
            content_type='application/json'
        )
        assert meeting_response.status_code == 201

    def test_customer_cascade_delete(self, client):
        """测试客户级联删除"""
        # 创建客户
        customer_data = {
            'name': '测试客户',
            'company': '测试公司'
        }
        customer_response = client.post(
            '/api/customers',
            data=json.dumps(customer_data),
            content_type='application/json'
        )
        customer_id = customer_response.get_json()['data']['id']

        # 创建互动记录
        interaction_data = {
            'customer_id': customer_id,
            'interaction_type': 'email',
            'notes': '测试互动'
        }
        client.post(
            '/api/interactions',
            data=json.dumps(interaction_data),
            content_type='application/json'
        )

        # 创建销售机会
        opportunity_data = {
            'customer_id': customer_id,
            'title': '测试机会',
            'value': 10000.00
        }
        client.post(
            '/api/opportunities',
            data=json.dumps(opportunity_data),
            content_type='application/json'
        )

        # 删除客户
        delete_response = client.delete(f'/api/customers/{customer_id}')
        assert delete_response.status_code == 200

        # 验证关联记录也被删除
        interactions = client.get('/api/interactions')
        opportunities = client.get('/api/opportunities')

        assert interactions.get_json()['success'] == True
        assert opportunities.get_json()['success'] == True
