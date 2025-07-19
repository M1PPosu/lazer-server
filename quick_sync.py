#!/usr/bin/env python3
"""
简化的数据同步执行脚本
直接使用项目配置执行数据同步
"""

import os
import sys
import subprocess
from urllib.parse import urlparse
from app.config import settings

def parse_database_url():
    """解析数据库 URL"""
    url = urlparse(settings.DATABASE_URL)
    return {
        'host': url.hostname or 'localhost',
        'port': url.port or 3306,
        'user': url.username or 'root',
        'password': url.password or '',
        'database': url.path.lstrip('/') if url.path else 'osu_api'
    }

def run_sql_script(script_path: str):
    """使用 mysql 命令行执行 SQL 脚本"""
    if not os.path.exists(script_path):
        print(f"错误: SQL 脚本不存在 - {script_path}")
        return False
    
    # 解析数据库配置
    db_config = parse_database_url()
    
    # 构建 mysql 命令
    cmd = [
        'mysql',
        f'--host={db_config["host"]}',
        f'--port={db_config["port"]}',
        f'--user={db_config["user"]}',
        db_config['database']
    ]
    
    # 添加密码（如果有的话）
    if db_config['password']:
        cmd.insert(-1, f'--password={db_config["password"]}')
    
    try:
        print(f"执行 SQL 脚本: {script_path}")
        with open(script_path, 'r', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True,
                check=True
            )
        
        if result.stdout:
            print("执行结果:")
            print(result.stdout)
        
        print(f"✓ 成功执行: {script_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ 执行失败: {script_path}")
        print(f"错误信息: {e.stderr}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 mysql 命令行工具")
        print("请确保 MySQL 客户端已安装并添加到 PATH 环境变量中")
        return False

def main():
    """主函数"""
    print("Lazer API 快速数据同步")
    print("=" * 40)
    
    db_config = parse_database_url()
    print(f"数据库: {db_config['host']}:{db_config['port']}/{db_config['database']}")
    print()
    
    # 确认是否继续
    print("这将执行以下操作:")
    print("1. 创建 lazer 专用表结构")
    print("2. 同步现有用户数据到新表")
    print("3. 不会修改现有的原始表数据")
    print()
    
    confirm = input("是否继续? (y/N): ").strip().lower()
    if confirm != 'y':
        print("操作已取消")
        return
    
    # 获取脚本路径
    script_dir = os.path.dirname(__file__)
    migrations_dir = os.path.join(script_dir, 'migrations')
    
    # 第一步: 创建表结构
    print("\n步骤 1: 创建 lazer 专用表结构...")
    add_fields_script = os.path.join(migrations_dir, 'add_missing_fields.sql')
    if not run_sql_script(add_fields_script):
        print("表结构创建失败，停止执行")
        return
    
    # 第二步: 同步数据
    print("\n步骤 2: 同步历史数据...")
    sync_script = os.path.join(migrations_dir, 'sync_legacy_data.sql')
    if not run_sql_script(sync_script):
        print("数据同步失败")
        return
    
    # 第三步: 添加缺失的字段
    print("\n步骤 3: 添加缺失的字段...")
    add_rank_fields_script = os.path.join(migrations_dir, 'add_lazer_rank_fields.sql')
    if not run_sql_script(add_rank_fields_script):
        print("添加字段失败")
        return
    
    print("\n🎉 数据同步完成!")
    print("\n现在您可以:")
    print("1. 启动 Lazer API 服务器")
    print("2. 使用现有用户账号登录")
    print("3. 查看同步后的用户数据")

if __name__ == "__main__":
    main()
