#!/usr/bin/env python3
"""
测试 osu! API 模拟服务器的脚本
"""

import requests
import os
from dotenv import load_dotenv
import json

# 加载 .env 文件
load_dotenv()

CLIENT_ID = os.environ.get('OSU_CLIENT_ID', '5')
CLIENT_SECRET = os.environ.get('OSU_CLIENT_SECRET', 'FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk')
API_URL = os.environ.get('OSU_API_URL', 'http://localhost:8000')

def test_server_health():
    """测试服务器健康状态"""
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            print("✅ 服务器健康检查通过")
            return True
        else:
            print(f"❌ 服务器健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return False

def authenticate(username: str, password: str):
    """通过 OAuth 密码流进行身份验证并返回令牌字典"""
    url = f"{API_URL}/oauth/token"
    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "*",
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ 身份验证成功")
            return response.json()
        else:
            print(f"❌ 身份验证失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 身份验证请求失败: {e}")
        return None

def refresh_token(refresh_token: str):
    """刷新 OAuth 令牌"""
    url = f"{API_URL}/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "*",
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ 令牌刷新成功")
            return response.json()
        else:
            print(f"❌ 令牌刷新失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 令牌刷新请求失败: {e}")
        return None

def get_current_user(access_token: str, ruleset: str = "osu"):
    """获取认证用户的数据"""
    url = f"{API_URL}/api/v2/me/{ruleset}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print(f"✅ 成功获取 {ruleset} 模式的用户数据")
            return response.json()
        else:
            print(f"❌ 获取用户数据失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 获取用户数据请求失败: {e}")
        return None

def main():
    """主测试函数"""
    print("=== osu! API 模拟服务器测试 ===\n")
    
    # 1. 测试服务器健康状态
    print("1. 检查服务器状态...")
    if not test_server_health():
        print("请确保服务器正在运行: uvicorn main:app --reload")
        return
    
    print()
    
    # 2. 获取用户凭据
    print("2. 用户身份验证...")
    username = input("请输入用户名 (默认: Googujiang): ").strip() or "Googujiang"
    
    import getpass
    password = getpass.getpass("请输入密码 (默认: password123): ") or "password123"
    
    # 3. 身份验证
    print(f"\n3. 正在验证用户 '{username}'...")
    token_data = authenticate(username, password)
    if not token_data:
        print("身份验证失败，请检查用户名和密码")
        return
    
    print(f"访问令牌: {token_data['access_token'][:50]}...")
    print(f"刷新令牌: {token_data['refresh_token'][:30]}...")
    print(f"令牌有效期: {token_data['expires_in']} 秒")
    
    # 4. 获取用户数据
    print(f"\n4. 获取用户数据...")
    for ruleset in ["osu", "taiko", "fruits", "mania"]:
        print(f"\n--- {ruleset.upper()} 模式 ---")
        user_data = get_current_user(token_data["access_token"], ruleset)
        if user_data:
            print(f"用户名: {user_data['username']}")
            print(f"国家: {user_data['country']['name']} ({user_data['country_code']})")
            print(f"全球排名: {user_data['statistics']['global_rank']}")
            print(f"PP: {user_data['statistics']['pp']}")
            print(f"游戏次数: {user_data['statistics']['play_count']}")
            print(f"命中精度: {user_data['statistics']['hit_accuracy']:.2f}%")
    
    # 5. 测试令牌刷新
    print(f"\n5. 测试令牌刷新...")
    new_token_data = refresh_token(token_data["refresh_token"])
    if new_token_data:
        print(f"新访问令牌: {new_token_data['access_token'][:50]}...")
        
        # 使用新令牌获取用户数据
        print("\n6. 使用新令牌获取用户数据...")
        user_data = get_current_user(new_token_data["access_token"])
        if user_data:
            print(f"✅ 新令牌有效，用户: {user_data['username']}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()
