#!/usr/bin/env python
"""
运行测试的脚本
"""
import os
import subprocess
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 运行pytest
subprocess.run([
    sys.executable, '-m', 'pytest',
    'tests/test_api.py',
    '-v',
    '--tb=short',
    '-W', 'ignore::pytest.PytestCacheWarning'
])
