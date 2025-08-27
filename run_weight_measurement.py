#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
称重测量系统启动脚本

这个脚本用于启动集成到传感器驱动系统中的称重测量界面。
"""

import os
import sys

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def main():
    """主函数"""
    try:
        # 导入并运行称重测量界面
        from interfaces.ordinary.weight_measurement_interface import main as run_interface
        run_interface()
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保所有依赖模块都已正确安装")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 运行错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 