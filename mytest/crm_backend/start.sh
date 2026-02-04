#!/bin/bash

echo "================================="
echo "  CRM后端系统 - 快速启动脚本"
echo "================================="
echo ""

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python -m venv venv
    echo "✅ 虚拟环境创建成功"
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 检查依赖是否已安装
echo "📋 检查依赖..."
python -c "import flask, sqlalchemy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⏳ 安装依赖..."
    pip install -q -r requirements.txt
    echo "✅ 依赖安装完成"
else
    echo "✅ 依赖已就绪"
fi

echo ""
echo "================================="
echo "  请选择操作："
echo "================================="
echo "1. 启动应用 (开发模式)"
echo "2. 运行测试"
echo "3. 查看API文档"
echo ""
read -p "请输入选项 (1/2/3): " choice

case $choice in
    1)
        echo ""
        echo "🚀 启动CRM应用..."
        echo "📍 API地址: http://localhost:5000"
        echo "📍 健康检查: http://localhost:5000/api/health"
        echo ""
        echo "按 Ctrl+C 停止应用"
        echo ""
        python app.py
        ;;
    2)
        echo ""
        echo "🧪 运行测试..."
        pytest tests/test_api.py -v --tb=short
        ;;
    3)
        echo ""
        cat README.md
        ;;
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac
