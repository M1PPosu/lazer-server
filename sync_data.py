#!/usr/bin/env python3
"""
Lazer API 数据同步脚本
用于将现有的 bancho.py 数据同步到新的 lazer 专用表中
"""

import os
import sys
import pymysql
from typing import Optional
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class DatabaseSyncer:
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        """初始化数据库连接配置"""
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
    
    def connect(self):
        """连接到数据库"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                autocommit=False
            )
            logger.info(f"成功连接到数据库 {self.database}")
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            raise
    
    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
    
    def execute_sql_file(self, file_path: str):
        """执行 SQL 文件"""
        if not os.path.exists(file_path):
            logger.error(f"SQL 文件不存在: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割SQL语句（简单实现，按分号分割）
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            cursor = self.connection.cursor()
            
            for i, statement in enumerate(statements):
                # 跳过注释和空语句
                if statement.startswith('--') or not statement:
                    continue
                
                try:
                    logger.info(f"执行第 {i+1}/{len(statements)} 条SQL语句...")
                    cursor.execute(statement)
                    
                    # 如果是SELECT语句，显示结果
                    if statement.strip().upper().startswith('SELECT'):
                        results = cursor.fetchall()
                        if results:
                            logger.info(f"查询结果: {results}")
                    
                except Exception as e:
                    logger.error(f"执行SQL语句失败: {statement[:100]}...")
                    logger.error(f"错误信息: {e}")
                    # 继续执行其他语句
                    continue
            
            self.connection.commit()
            cursor.close()
            logger.info(f"成功执行SQL文件: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"执行SQL文件失败: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def check_tables_exist(self, tables: list) -> dict:
        """检查表是否存在"""
        results = {}
        cursor = self.connection.cursor()
        
        for table in tables:
            try:
                cursor.execute(f"SHOW TABLES LIKE '{table}'")
                exists = cursor.fetchone() is not None
                results[table] = exists
                logger.info(f"表 '{table}' {'存在' if exists else '不存在'}")
            except Exception as e:
                logger.error(f"检查表 '{table}' 时出错: {e}")
                results[table] = False
        
        cursor.close()
        return results
    
    def get_table_count(self, table: str) -> int:
        """获取表的记录数"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            result = cursor.fetchone()
            count = result[0] if result else 0
            cursor.close()
            return count
        except Exception as e:
            logger.error(f"获取表 '{table}' 记录数失败: {e}")
            return -1

def main():
    """主函数"""
    print("Lazer API 数据同步工具")
    print("=" * 50)
    
    # 数据库配置
    db_config = {
        'host': input("数据库主机 [localhost]: ").strip() or 'localhost',
        'port': int(input("数据库端口 [3306]: ").strip() or '3306'),
        'user': input("数据库用户名: ").strip(),
        'password': input("数据库密码: ").strip(),
        'database': input("数据库名称: ").strip()
    }
    
    syncer = DatabaseSyncer(**db_config)
    
    try:
        # 连接数据库
        syncer.connect()
        
        # 检查必要的原始表是否存在
        required_tables = ['users', 'stats']
        table_status = syncer.check_tables_exist(required_tables)
        
        missing_tables = [table for table, exists in table_status.items() if not exists]
        if missing_tables:
            logger.error(f"缺少必要的原始表: {missing_tables}")
            return
        
        # 显示原始表的记录数
        for table in required_tables:
            count = syncer.get_table_count(table)
            logger.info(f"表 '{table}' 当前有 {count} 条记录")
        
        # 确认是否执行同步
        print("\n准备执行数据同步...")
        print("这将会:")
        print("1. 创建 lazer 专用表结构 (如果不存在)")
        print("2. 从现有表同步数据到新表")
        print("3. 不会修改或删除现有数据")
        
        confirm = input("\n是否继续? (y/N): ").strip().lower()
        if confirm != 'y':
            print("操作已取消")
            return
        
        # 执行表结构创建
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        
        print("\n步骤 1: 创建表结构...")
        add_fields_sql = os.path.join(migrations_dir, 'add_missing_fields.sql')
        if os.path.exists(add_fields_sql):
            success = syncer.execute_sql_file(add_fields_sql)
            if not success:
                logger.error("创建表结构失败")
                return
        else:
            logger.warning(f"表结构文件不存在: {add_fields_sql}")
        
        # 执行数据同步
        print("\n步骤 2: 同步数据...")
        sync_sql = os.path.join(migrations_dir, 'sync_legacy_data.sql')
        if os.path.exists(sync_sql):
            success = syncer.execute_sql_file(sync_sql)
            if not success:
                logger.error("数据同步失败")
                return
        else:
            logger.error(f"同步脚本不存在: {sync_sql}")
            return
        
        # 显示同步后的统计信息
        print("\n步骤 3: 同步完成统计...")
        lazer_tables = [
            'lazer_user_profiles',
            'lazer_user_countries', 
            'lazer_user_statistics',
            'lazer_user_kudosu',
            'lazer_user_counts'
        ]
        
        for table in lazer_tables:
            count = syncer.get_table_count(table)
            if count >= 0:
                logger.info(f"表 '{table}' 现在有 {count} 条记录")
        
        print("\n数据同步完成!")
        
    except KeyboardInterrupt:
        print("\n\n操作被用户中断")
    except Exception as e:
        logger.error(f"同步过程中发生错误: {e}")
    finally:
        syncer.disconnect()

if __name__ == "__main__":
    main()
