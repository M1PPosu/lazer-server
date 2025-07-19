#!/usr/bin/env python3
"""
测试密码哈希和验证逻辑
"""

import hashlib
import bcrypt
from app.auth import get_password_hash, verify_password_legacy, bcrypt_cache

def test_password_logic():
    """测试密码逻辑"""
    print("=== 测试密码哈希和验证逻辑 ===\n")
    
    # 测试密码
    password = "password123"
    print(f"原始密码: {password}")
    
    # 1. 生成哈希
    print("\n1. 生成密码哈希...")
    hashed = get_password_hash(password)
    print(f"bcrypt 哈希: {hashed}")
    
    # 2. 验证密码
    print("\n2. 验证密码...")
    is_valid = verify_password_legacy(password, hashed)
    print(f"验证结果: {'✅ 成功' if is_valid else '❌ 失败'}")
    
    # 3. 测试错误密码
    print("\n3. 测试错误密码...")
    wrong_password = "wrongpassword"
    is_valid_wrong = verify_password_legacy(wrong_password, hashed)
    print(f"错误密码验证结果: {'❌ 不应该成功' if is_valid_wrong else '✅ 正确拒绝'}")
    
    # 4. 测试缓存
    print(f"\n4. 缓存状态:")
    print(f"缓存中的条目数: {len(bcrypt_cache)}")
    if hashed in bcrypt_cache:
        print(f"缓存的 MD5: {bcrypt_cache[hashed]}")
        expected_md5 = hashlib.md5(password.encode()).hexdigest().encode()
        print(f"期望的 MD5: {expected_md5}")
        print(f"缓存匹配: {'✅' if bcrypt_cache[hashed] == expected_md5 else '❌'}")
    
    # 5. 再次验证（应该使用缓存）
    print("\n5. 再次验证（使用缓存）...")
    is_valid_cached = verify_password_legacy(password, hashed)
    print(f"缓存验证结果: {'✅ 成功' if is_valid_cached else '❌ 失败'}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_password_logic()
