#!/bin/bash
# mc-search 初始化脚本
# 用于自动安装和验证 mc-search 工具

set -e

echo "=== mc-search 初始化 ==="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查 curl
if ! command -v curl &> /dev/null; then
    echo "错误: 未找到 curl，请先安装 curl"
    exit 1
fi

# 安装 mc-search
echo "正在安装 mc-search..."
pip install -e . -q 2>/dev/null || pip install -e .

# 验证安装
echo "验证安装..."
if mc-search --help &> /dev/null; then
    echo "✅ mc-search 安装成功！"
    echo ""
    echo "快速测试:"
    echo "  mc-search --json search 钠"
else
    echo "❌ 安装失败，请检查错误信息"
    exit 1
fi
