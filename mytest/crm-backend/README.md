# 简易CRM后端系统

一个基于Python Flask + SQLite的轻量级CRM（客户关系管理）后端系统，支持客户、联系人和交易管理。

## 功能特性

- **客户管理**：创建、查看、更新、删除客户信息
- **联系人管理**：管理客户的具体联系人
- **交易管理**：跟踪销售机会和交易记录
- **RESTful API**：标准化的REST API接口
- **SQLite存储**：轻量级数据库，无需额外安装
- **完整测试**：包含单元测试覆盖

## 技术栈

- Python 3.8+
- Flask 3.0.0
- SQLAlchemy (ORM)
- SQLite
- Pytest (测试框架)

## 项目结构

```
crm-backend/
├── app/
│   ├── __init__.py          # Flask应用初始化
│   ├── config.py            # 配置文件
│   ├── models.py            # 数据库模型
│   ├── database.py          # 数据库连接
│   └── routes/              # API路由
│       ├── __init__.py
│       ├── customers.py     # 客户API
│       ├── contacts.py      # 联系人API
│       └── deals.py         # 交易API
├── tests/                   # 测试文件
│   ├── test_customers.py
│   ├── test_contacts.py
│   └── test_deals.py
├── requirements.txt         # 依赖包
├── run.py                  # 启动文件
└── README.md               # 文档
```

## 安装配置

### 1. 安装依赖

```bash
cd crm-backend
pip install -r requirements.txt
```

### 2. 运行应用

```bash
python run.py
```

服务器将在 `http://0.0.0.0:5000` 启动

### 3. 运行测试

```bash
pytest tests/ -v
```

## API文档

### 基础信息

- **Base URL**: `http://localhost:5000/api`
- **Content-Type**: `application/json`

### 1. 客户管理 (Customers)

#### 获取所有客户
```
GET /api/customers
```

**响应示例**：
```json
[
  {
    "id": 1,
    "name": "科技有限公司",
    "industry": "技术",
    "website": "https://tech.com",
    "phone": "1234567890",
    "email": "info@tech.com",
    "address": "北京市朝阳区",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
]
```

#### 获取单个客户
```
GET /api/customers/{customer_id}
```

#### 创建客户
```
POST /api/customers
Content-Type: application/json

{
  "name": "新公司",
  "industry": "技术",
  "website": "https://example.com",
  "phone": "1234567890",
  "email": "contact@example.com",
  "address": "公司地址"
}
```

**必填字段**：`name`

#### 更新客户
```
PUT /api/customers/{customer_id}
Content-Type: application/json

{
  "name": "更新后的公司名",
  "industry": "更新后的行业"
}
```

#### 删除客户
```
DELETE /api/customers/{customer_id}
```

### 2. 联系人管理 (Contacts)

#### 获取所有联系人
```
GET /api/contacts
```

#### 获取单个联系人
```
GET /api/contacts/{contact_id}
```

#### 创建联系人
```
POST /api/contacts
Content-Type: application/json

{
  "customer_id": 1,
  "name": "张三",
  "position": "CEO",
  "phone": "13800138000",
  "email": "zhangsan@example.com"
}
```

**必填字段**：`name`, `customer_id`

#### 更新联系人
```
PUT /api/contacts/{contact_id}
Content-Type: application/json

{
  "name": "李四",
  "position": "CTO"
}
```

#### 删除联系人
```
DELETE /api/contacts/{contact_id}
```

### 3. 交易管理 (Deals)

#### 获取所有交易
```
GET /api/deals
```

#### 获取单个交易
```
GET /api/deals/{deal_id}
```

#### 创建交易
```
POST /api/deals
Content-Type: application/json

{
  "customer_id": 1,
  "title": "软件许可合同",
  "description": "年度软件许可协议",
  "amount": 50000.0,
  "status": "opportunity"
}
```

**必填字段**：`title`, `customer_id`

**可选状态**：`lead`, `opportunity`, `negotiation`, `won`, `lost`

#### 更新交易
```
PUT /api/deals/{deal_id}
Content-Type: application/json

{
  "status": "won",
  "amount": 60000.0
}
```

#### 删除交易
```
DELETE /api/deals/{deal_id}
```

## 使用示例

### 使用cURL测试API

#### 1. 创建客户
```bash
curl -X POST http://localhost:5000/api/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "示例公司",
    "industry": "技术",
    "email": "info@example.com"
  }'
```

#### 2. 创建联系人
```bash
curl -X POST http://localhost:5000/api/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "name": "王五",
    "position": "销售经理",
    "email": "wangwu@example.com"
  }'
```

#### 3. 创建交易
```bash
curl -X POST http://localhost:5000/api/deals \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "title": "软件服务合同",
    "amount": 100000.0,
    "status": "opportunity"
  }'
```

#### 4. 获取所有客户
```bash
curl http://localhost:5000/api/customers
```

#### 5. 更新交易状态
```bash
curl -X PUT http://localhost:5000/api/deals/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "won"
  }'
```

### 使用Python requests库

```python
import requests

BASE_URL = 'http://localhost:5000/api'

# 创建客户
customer = {
    'name': '测试公司',
    'industry': '技术',
    'email': 'test@test.com'
}
response = requests.post(f'{BASE_URL}/customers', json=customer)
customer_id = response.json()['id']
print(f'创建客户成功, ID: {customer_id}')

# 创建联系人
contact = {
    'customer_id': customer_id,
    'name': '张三',
    'position': 'CEO',
    'email': 'zhangsan@test.com'
}
response = requests.post(f'{BASE_URL}/contacts', json=contact)
print(f'创建联系人成功: {response.json()}')

# 创建交易
deal = {
    'customer_id': customer_id,
    'title': '软件开发项目',
    'amount': 50000.0,
    'status': 'opportunity'
}
response = requests.post(f'{BASE_URL}/deals', json=deal)
print(f'创建交易成功: {response.json()}')

# 获取所有交易
response = requests.get(f'{BASE_URL}/deals')
print(f'所有交易: {response.json()}')
```

## 数据库

数据库文件位置：`crm-backend/instance/crm.db`（首次运行时自动创建）

### 数据模型

| 表名 | 说明 |
|------|------|
| customers | 客户信息表 |
| contacts | 联系人信息表 |
| deals | 交易信息表 |

### 表关系

- **customers** 与 **contacts**：一对多关系
- **customers** 与 **deals**：一对多关系

## 测试

运行所有测试：
```bash
pytest tests/ -v
```

运行特定测试文件：
```bash
pytest tests/test_customers.py -v
```

查看测试覆盖率：
```bash
pytest tests/ --cov=app --cov-report=html
```

## 开发说明

### 添加新功能

1. 在 `app/models.py` 中定义数据模型
2. 在 `app/routes/` 目录下创建对应的路由文件
3. 在 `app/__init__.py` 中注册新的蓝图
4. 编写测试用例

### 配置

修改 `app/config.py` 可配置：
- 数据库连接
- 密钥
- 分页设置

## 生产环境部署

在生产环境中，建议：

1. 修改 `SECRET_KEY` 为强随机字符串
2. 使用环境变量设置配置
3. 启用HTTPS
4. 配置日志记录
5. 使用更强大的数据库（如PostgreSQL）

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交Issue。
