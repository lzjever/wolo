#!/usr/bin/env python
"""
CRM API 快速演示
演示如何使用CRM系统的各种API
"""
import json
import time

import requests

BASE_URL = "http://localhost:5000"

def print_json(data, title=""):
    """格式化打印JSON"""
    if title:
        print(f"\n{'='*50}")
        print(f"  {title}")
        print('='*50)
    print(json.dumps(data, indent=2, ensure_ascii=False))

def test_health_check():
    """测试健康检查"""
    print("\n🏥 测试健康检查...")
    response = requests.get(f"{BASE_URL}/api/health")
    print_json(response.json(), "健康检查响应")
    return response.json()['status'] == 'healthy'

def test_create_customer():
    """创建客户"""
    print("\n👤 创建客户...")
    customer_data = {
        "name": "张三",
        "company": "科技创新有限公司",
        "email": "zhangsan@tech.com",
        "phone": "13800138000",
        "status": "active"
    }
    response = requests.post(f"{BASE_URL}/api/customers", json=customer_data)
    print_json(response.json(), "创建客户")
    return response.json()['data']['id']

def test_create_customer_2():
    """创建第二个客户"""
    customer_data = {
        "name": "李四",
        "company": "未来科技公司",
        "email": "lisi@future.com",
        "phone": "13900139000"
    }
    response = requests.post(f"{BASE_URL}/api/customers", json=customer_data)
    print_json(response.json(), "创建第二个客户")
    return response.json()['data']['id']

def test_get_customers():
    """获取所有客户"""
    print("\n📋 获取所有客户...")
    response = requests.get(f"{BASE_URL}/api/customers")
    print_json(response.json(), "客户列表")

def test_search_customers():
    """搜索客户"""
    print("\n🔍 搜索客户（关键词：科技）...")
    response = requests.get(f"{BASE_URL}/api/customers?search=科技")
    print_json(response.json(), "搜索结果")

def test_get_customer(customer_id):
    """获取单个客户详情"""
    print(f"\n👤 获取客户详情（ID: {customer_id}）...")
    response = requests.get(f"{BASE_URL}/api/customers/{customer_id}")
    print_json(response.json(), "客户详情")

def test_create_opportunity(customer_id):
    """创建销售机会"""
    print(f"\n💰 创建销售机会（客户ID: {customer_id}）...")
    opportunity_data = {
        "customer_id": customer_id,
        "title": "企业ERP系统采购",
        "value": 500000.00,
        "stage": "lead",
        "probability": 30
    }
    response = requests.post(f"{BASE_URL}/api/opportunities", json=opportunity_data)
    print_json(response.json(), "创建销售机会")
    return response.json()['data']['id']

def test_create_interaction(customer_id):
    """创建互动记录"""
    print(f"\n📞 创建互动记录（客户ID: {customer_id}）...")
    interaction_data = {
        "customer_id": customer_id,
        "interaction_type": "call",
        "notes": "初步了解客户需求，对ERP系统感兴趣"
    }
    response = requests.post(f"{BASE_URL}/api/interactions", json=interaction_data)
    print_json(response.json(), "创建互动记录")
    return response.json()['data']['id']

def test_update_opportunity(opportunity_id):
    """更新销售机会"""
    print(f"\n✏️  更新销售机会（ID: {opportunity_id}）...")
    update_data = {
        "stage": "proposal",
        "probability": 60
    }
    response = requests.put(f"{BASE_URL}/api/opportunities/{opportunity_id}", json=update_data)
    print_json(response.json(), "更新销售机会")

def test_get_interactions(customer_id=None):
    """获取互动记录"""
    url = f"{BASE_URL}/api/interactions"
    if customer_id:
        url += f"?customer_id={customer_id}"
        print(f"\n📞 获取客户的互动记录（ID: {customer_id}）...")
    else:
        print("\n📞 获取所有互动记录...")

    response = requests.get(url)
    print_json(response.json(), "互动记录列表")

def test_get_opportunities(customer_id=None):
    """获取销售机会"""
    url = f"{BASE_URL}/api/opportunities"
    if customer_id:
        url += f"?customer_id={customer_id}"
        print(f"\n💰 获取客户的销售机会（ID: {customer_id}）...")
    else:
        print("\n💰 获取所有销售机会...")

    response = requests.get(url)
    print_json(response.json(), "销售机会列表")

def test_update_customer(customer_id):
    """更新客户信息"""
    print(f"\n✏️  更新客户信息（ID: {customer_id}）...")
    update_data = {
        "email": "newemail@tech.com",
        "status": "premium"
    }
    response = requests.put(f"{BASE_URL}/api/customers/{customer_id}", json=update_data)
    print_json(response.json(), "更新客户信息")

def test_delete_customer(customer_id):
    """删除客户"""
    print(f"\n🗑️  删除客户（ID: {customer_id}）...")
    print("注意：这将删除所有关联的互动记录和销售机会")
    response = requests.delete(f"{BASE_URL}/api/customers/{customer_id}")
    print_json(response.json(), "删除客户")

def main():
    """主函数"""
    print("="*60)
    print("       CRM系统API演示")
    print("="*60)

    try:
        # 1. 健康检查
        if not test_health_check():
            print("\n❌ 服务未运行，请先启动应用: python app.py")
            return

        # 2. 创建客户
        customer_id_1 = test_create_customer()
        customer_id_2 = test_create_customer_2()

        time.sleep(0.5)

        # 3. 获取所有客户
        test_get_customers()

        time.sleep(0.5)

        # 4. 搜索客户
        test_search_customers()

        time.sleep(0.5)

        # 5. 获取单个客户详情
        test_get_customer(customer_id_1)

        time.sleep(0.5)

        # 6. 创建销售机会
        opportunity_id = test_create_opportunity(customer_id_1)

        time.sleep(0.5)

        # 7. 创建互动记录
        test_create_interaction(customer_id_1)

        time.sleep(0.5)

        # 8. 再次创建互动记录
        interaction_data = {
            "customer_id": customer_id_1,
            "interaction_type": "email",
            "notes": "发送产品方案和报价"
        }
        response = requests.post(f"{BASE_URL}/api/interactions", json=interaction_data)
        print_json(response.json(), "创建第二个互动记录")

        time.sleep(0.5)

        # 9. 获取销售机会
        test_get_opportunities()

        time.sleep(0.5)

        # 10. 获取客户的销售机会
        test_get_opportunities(customer_id_1)

        time.sleep(0.5)

        # 11. 获取互动记录
        test_get_interactions()

        time.sleep(0.5)

        # 12. 获取客户的互动记录
        test_get_interactions(customer_id_1)

        time.sleep(0.5)

        # 13. 更新销售机会
        test_update_opportunity(opportunity_id)

        time.sleep(0.5)

        # 14. 更新客户信息
        test_update_customer(customer_id_1)

        time.sleep(0.5)

        # 15. 获取更新后的客户信息
        test_get_customer(customer_id_1)

        time.sleep(0.5)

        # 16. 删除第二个客户（演示级联删除）
        test_delete_customer(customer_id_2)

        time.sleep(0.5)

        # 17. 验证只包含删除的数据
        print("\n📋 验证删除后的客户列表...")
        test_get_customers()

        print("\n" + "="*60)
        print("  ✅ API演示完成！")
        print("="*60)

    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器，请确保应用正在运行")
        print("   启动命令: python app.py")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
