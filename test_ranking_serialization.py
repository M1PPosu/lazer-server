#!/usr/bin/env python3
"""测试排行榜缓存序列化修复"""

import asyncio
import warnings
from datetime import datetime, UTC
from app.service.ranking_cache_service import DateTimeEncoder, safe_json_dumps


def test_datetime_serialization():
    """测试 datetime 序列化"""
    print("🧪 测试 datetime 序列化...")
    
    test_data = {
        "id": 1,
        "username": "test_user",
        "last_updated": datetime.now(UTC),
        "join_date": datetime(2020, 1, 1, tzinfo=UTC),
        "stats": {
            "pp": 1000.0,
            "accuracy": 95.5,
            "last_played": datetime.now(UTC)
        }
    }
    
    try:
        # 测试自定义编码器
        json_result = safe_json_dumps(test_data)
        print("✅ datetime 序列化成功")
        print(f"   序列化结果长度: {len(json_result)}")
        
        # 验证可以重新解析
        import json
        parsed = json.loads(json_result)
        assert "last_updated" in parsed
        assert isinstance(parsed["last_updated"], str)
        print("✅ 序列化的 JSON 可以正确解析")
        
    except Exception as e:
        print(f"❌ datetime 序列化测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_boolean_serialization():
    """测试布尔值序列化"""
    print("\n🧪 测试布尔值序列化...")
    
    test_data = {
        "user": {
            "is_active": 1,        # 数据库中的整数布尔值
            "is_supporter": 0,     # 数据库中的整数布尔值  
            "has_profile": True,   # 正常布尔值
        },
        "stats": {
            "is_ranked": 1,        # 数据库中的整数布尔值
            "verified": False,     # 正常布尔值
        }
    }
    
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            json_result = safe_json_dumps(test_data)
            
            # 检查是否有 Pydantic 序列化警告
            pydantic_warnings = [warning for warning in w if 'PydanticSerializationUnexpectedValue' in str(warning.message)]
            if pydantic_warnings:
                print(f"⚠️  仍有 {len(pydantic_warnings)} 个布尔值序列化警告")
                for warning in pydantic_warnings:
                    print(f"   {warning.message}")
            else:
                print("✅ 布尔值序列化无警告")
        
        # 验证序列化结果
        import json
        parsed = json.loads(json_result)
        print(f"✅ 布尔值序列化成功，结果: {parsed}")
        
    except Exception as e:
        print(f"❌ 布尔值序列化测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_complex_ranking_data():
    """测试复杂的排行榜数据序列化"""
    print("\n🧪 测试复杂排行榜数据序列化...")
    
    # 模拟排行榜数据结构
    ranking_data = [
        {
            "id": 1,
            "user": {
                "id": 1,
                "username": "player1",
                "country_code": "US",
                "is_active": 1,        # 整数布尔值
                "is_supporter": 0,     # 整数布尔值
                "join_date": datetime(2020, 1, 1, tzinfo=UTC),
                "last_visit": datetime.now(UTC),
            },
            "statistics": {
                "pp": 8000.0,
                "accuracy": 98.5,
                "play_count": 5000,
                "is_ranked": 1,        # 整数布尔值
                "last_updated": datetime.now(UTC),
            }
        },
        {
            "id": 2,
            "user": {
                "id": 2,
                "username": "player2",
                "country_code": "JP",
                "is_active": 1,
                "is_supporter": 1,
                "join_date": datetime(2019, 6, 15, tzinfo=UTC),
                "last_visit": datetime.now(UTC),
            },
            "statistics": {
                "pp": 7500.0,
                "accuracy": 97.8,
                "play_count": 4500,
                "is_ranked": 1,
                "last_updated": datetime.now(UTC),
            }
        }
    ]
    
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            json_result = safe_json_dumps(ranking_data)
            
            pydantic_warnings = [warning for warning in w if 'PydanticSerializationUnexpectedValue' in str(warning.message)]
            if pydantic_warnings:
                print(f"⚠️  仍有 {len(pydantic_warnings)} 个序列化警告")
                for warning in pydantic_warnings:
                    print(f"   {warning.message}")
            else:
                print("✅ 复杂排行榜数据序列化无警告")
        
        # 验证序列化结果
        import json
        parsed = json.loads(json_result)
        assert len(parsed) == 2
        assert parsed[0]["user"]["username"] == "player1"
        print(f"✅ 复杂排行榜数据序列化成功，包含 {len(parsed)} 个条目")
        
    except Exception as e:
        print(f"❌ 复杂排行榜数据序列化测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 开始排行榜缓存序列化测试\n")
    
    test_datetime_serialization()
    test_boolean_serialization()  
    test_complex_ranking_data()
    
    print("\n🎉 排行榜缓存序列化测试完成！")
