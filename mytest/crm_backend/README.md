# 简易CRM系统后端

基于Python Flask + SQLite的轻量级客户关系管理系统后端。

## 功能特性

- **客户管理**：客户的增删改查和搜索
- **互动记录**：记录与客户的互动（电话、邮件、会议等）
- **销售机会**：跟踪销售线索和机会，管理阶段和概率
- **级联删除**：删除客户时自动删除关联的互动记录和机会
- **RESTful API**：清晰的API设计
- **完整测试**：24个测试用例，覆盖所有功能和集成场景

## 技术栈

- **框架**: Flask 3.0.0
- **数据库**: SQLite (通过SQLAlchemy)
- **测试**: Pytest + pytest-flask
- **跨域**: Flask-CORS

## 项目结构

```
crm_backend/
├── app.py                 # 应用主入口
├── database.py            # 数据库配置
├── requirements.txt       # 依赖包
├── pytest.ini             # pytest配置
├── api/                   # API路由
│   ├── customer_routes.py     # 客户API
│   ├── interaction_routes.py  # 互动记录API
│   └── opportunity_routes.py  # 销售机会API
├── models/                # 数据模型
│   ├── customer.py            # 客户模型
│   ├── interaction.py         # 互动记录模型
│   └── opportunity.py         # 销售机会模型
├── services/              # 业务逻辑
│   ├── customer_service.py    # 客户服务
│   ├── interaction_service.py # 互动记录服务
│   └── opportunity_service.py # 销售机会服务
└── tests/                 # 测试用例
    ├── __init__.py
    └── test_api.py            # API测试
```

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 运行应用

```bash
python app.py
```

应用将在 `http://localhost:5000` 启动。

### 3. 测试API

访问 `http://localhost:5000/` 查看可用端点。

访问 `http://localhost:5000/api/health` 检查服务健康状态。

## API文档

### 基础端点

#### 健康检查
```
GET /api/health
```
返回：`{"status": "healthy", "message": "CRM API is running"}`

#### 根路径
```
GET /
```
返回：系统信息和使用说明

---

### 客户管理 API

#### 获取所有客户
```
GET /api/customers
```
可选参数：`?search=关键词` (按姓名、公司、邮箱搜索)

返回：
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "张三",
      "company": "测试公司",
      "email": "zhangsan@example.com",
      "phone": "13800138000",
      "status": "active",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

#### 获取单个客户
```
GET /api/customers/{id}
```

#### 创建客户
```
POST /api/customers
Content-Type: application/json

{
  "name": "张三",           // 必填
  "company": "测试公司",     // 可选
  "email": "test@example.com", // 可选
  "phone": "13800138000",  // 可选
  "status": "active"        // 可选，默认active
}
```

#### 更新客户
```
PUT /api/customers/{id}
Content-Type: application/json

{
  "name": "新名称",
  "email": "newemail@example.com"
  // 其他字段...
}
```

#### 删除客户
```
DELETE /api/customers/{id}
```

---

### 互动记录 API

#### 获取互动记录
```
GET /api/interactions
```
可选参数：`?customer_id={客户ID}`

#### 创建互动记录
```
POST /api/interactions
Content-Type: application/json

{
  "customer_id": 1,              // 必填
  "interaction_type": "call",    // 必填: call/email/meeting/other
  "notes": "初次沟通"            // 可选
}
```

#### 获取单个互动记录
```
GET /api/interactions/{id}
```

#### 更新互动记录
```
PUT /api/interactions/{id}
Content-Type: application/json

{
  "notes": "更新的备注"
}
```

#### 删除互动记录
```
DELETE /api/interactions/{id}
```

---

### 销售机会 API

#### 获取销售机会
```
GET /api/opportunities
```
可选参数：`?customer_id={客户ID}`

#### 创建销售机会
```
POST /api/opportunities
Content-Type: application/json

{
  "customer_id": 1,              // 必填
  "title": "企业软件采购",       // 必填
  "value": 100000.00,           // 可选
  "stage": "lead",              // 可选: lead/proposal/negotiation/closed/lost
  "probability": 20              // 可选: 0-100
}
```

#### 获取单个销售机会
```
GET /api/opportunities/{id}
```

#### 更新销售机会
```
PUT /api/opportunities/{id}
Content-Type: application/json

{
  "stage": "closed",
  "probability": 100
}
```

#### 删除销售机会
```
DELETE /api/opportunities/{id}
```

## 数据模型

### Customer (客户)
- `id`: 主键
- `name`: 姓名 (必填)
- `company`: 公司
- `email`: 邮箱
- `phone`: 电话
- `status`: 状态 (默认 active)
- `created_at`: 创建时间
- `updated_at`: 更新时间

### Interaction (互动记录)
- `id`: 主键
- `customer_id`: 客户ID (外键)
- `interaction_type`: 互动类型 (call/email/meeting/other)
- `notes`: 备注
- `created_at`: 创建时间

### Opportunity (销售机会)
- `id`: 主键
- `customer_id`: 客户ID (外键)
- `title`: 标题 (必填)
- `value`: 金额
- `stage`: 阶段 (lead/proposal/negotiation/closed/lost)
- `probability`: 成功概率 (0-100)
- `created_at`: 创建时间
- `updated_at`: 更新时间

## 测试

### 运行所有测试
```bash
./venv/bin/pytest tests/test_api.py -v
```

### 运行特定测试类
```bash
./venv/bin/pytest tests/test_api.py::TestCustomerAPI -v
```

### 查看测试覆盖率
```bash
pip install pytest-cov
./venv/bin/pytest tests/test_api.py --cov=. --cov-report=html
```

测试结果：
- ✅ 24个测试用例全部通过
- ✅ 覆盖健康检查、客户管理、互动记录、销售机会等所有功能
- ✅ 包含完整的集成测试和级联删除测试

## 典型使用场景

### 完整销售流程

```bash
# 1. 创建客户
curl -X POST http://localhost:5000/api/customers \
  -H "Content-Type: application/json" \
  -d '{"name":"张三","company":"ABC科技","email":"zhangsan@abc.com"}'

# 2. 创建销售机会
curl -X POST http://localhost:5000/api/opportunities \
  -H "Content-Type: application/json" \
  -d '{"customer_id":1,"title":"ERP系统","value":500000,"stage":"lead"}'

# 3. 记录初次沟通
curl -X POST http://localhost:5000/api/interactions \
  -H "Content-Type: application/json" \
  -d '{"customer_id":1,"interaction_type":"call","notes":"了解客户需求"}'

# 4. 更新机会阶段
curl -X PUT http://localhost:5000/api/opportunities/1 \
  -H "Content-Type: application/json" \
  -d '{"stage":"proposal","probability":60}'
```

### 搜索客户
```bash
# 按姓名搜索
curl http://localhost:5000/api/customers?search=张三

# 按公司搜索
curl http://localhost:5000/api/customers?search=ABC

# 按邮箱搜索
curl http://localhost:5000/api/customers?search=zhangsan@abc.com
```

## 数据存储

数据存储在 `crm.db` SQLite数据库文件中。

首次运行时，系统会自动创建数据库表结构。

### 数据库备份

```bash
# 备份数据库
cp crm.db crm_backup.db

# 恢复数据库
cp crm_backup.db crm.db
```

## 注意事项

1. 这是演示项目，生产环境使用时需要：
   - 修改 `SECRET_KEY`
   - 添加用户认证和授权
   - 实现数据验证和安全防护
   - 考虑使用更强大的数据库（PostgreSQL/MySQL）

2. 默认使用SQLite数据库，适合小型应用和演示

3. 级联删除：删除客户会自动删除所有相关的互动记录和销售机会

## 扩展建议

- 添加用户认证和权限管理
- 实现文件上传（附件、合同等）
- 添加数据分析和报表功能
- 支持多种数据库后端
- 添加WebSocket实时通知
- 实现任务和提醒功能
- 支持数据导出（Excel、PDF）

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交Issue。
