from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from app.config import settings
from app.dependencies import get_db, get_redis, engine
from app.models import TokenRequest, TokenResponse, User as ApiUser
from app.database import Base, User as DBUser
from app.auth import authenticate_user, create_access_token, generate_refresh_token, store_token
from app.auth import get_token_by_access_token, get_token_by_refresh_token, verify_token
from app.utils import convert_db_user_to_api_user

# 注意: 表结构现在通过 migrations 管理，不再自动创建
# 如需创建表，请运行: python quick_sync.py

app = FastAPI(title="osu! API 模拟服务器", version="1.0.0")

security = HTTPBearer()


@app.post("/oauth/token", response_model=TokenResponse)
async def oauth_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form("*"),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """OAuth 令牌端点"""
    # 验证客户端凭据
    if client_id != settings.OSU_CLIENT_ID or client_secret != settings.OSU_CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    
    if grant_type == "password":
        # 密码授权流程
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")
        
        # 验证用户
        user = authenticate_user(db, username, password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # 生成令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        refresh_token_str = generate_refresh_token()
        
        # 存储令牌
        store_token(
            db, 
            user.id, 
            access_token, 
            refresh_token_str, 
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token_str,
            scope=scope
        )
    
    elif grant_type == "refresh_token":
        # 刷新令牌流程
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required")
        
        # 验证刷新令牌
        token_record = get_token_by_refresh_token(db, refresh_token)
        if not token_record:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # 生成新的访问令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(token_record.user_id)}, expires_delta=access_token_expires
        )
        new_refresh_token = generate_refresh_token()
        
        # 更新令牌
        store_token(
            db,
            token_record.user_id,
            access_token,
            new_refresh_token,
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=new_refresh_token,
            scope=scope
        )
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported grant type")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> DBUser:
    """获取当前认证用户"""
    token = credentials.credentials
    
    # 验证令牌
    token_record = get_token_by_access_token(db, token)
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # 获取用户
    user = db.query(DBUser).filter(DBUser.id == token_record.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@app.get("/api/v2/me", response_model=ApiUser)
@app.get("/api/v2/me/", response_model=ApiUser)
async def get_user_info_default(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户信息（默认使用osu模式）"""
    # 默认使用osu模式
    api_user = convert_db_user_to_api_user(current_user, "osu", db)
    return api_user


@app.get("/api/v2/me/{ruleset}", response_model=ApiUser)
async def get_user_info(
    ruleset: str = "osu",
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    
    # 验证游戏模式
    valid_rulesets = ["osu", "taiko", "fruits", "mania"]
    if ruleset not in valid_rulesets:
        raise HTTPException(status_code=400, detail=f"Invalid ruleset. Must be one of: {valid_rulesets}")
    
    # 转换用户数据
    api_user = convert_db_user_to_api_user(current_user, ruleset, db)
    return api_user


@app.get("/")
async def root():
    """根端点"""
    return {"message": "osu! API 模拟服务器正在运行"}


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}



@app.get("/api/v2/friends")
async def get_friends():
    return JSONResponse(content=[
        {
            "id": 123456,
            "username": "BestFriend",
            "is_online": True,
            "is_supporter": False,
            "country": {"code": "US", "name": "United States"}
        }
    ])


@app.get("/api/v2/notifications")
async def get_notifications():
    return JSONResponse(content={
        "notifications": [],
        "unread_count": 0
    })


@app.post("/api/v2/chat/ack")
async def chat_ack():
    return JSONResponse(content={"status": "ok"})


@app.get("/api/v2/users/{user_id}/{mode}")
async def get_user_mode(user_id: int, mode: str):
    return JSONResponse(content={
        "id": user_id,
        "username": "测试测试测",
        "statistics": {
            "level": {"current": 97, "progress": 96},
            "pp": 114514,
            "global_rank": 666,
            "country_rank": 1,
            "hit_accuracy": 100
        },
        "country": {"code": "JP", "name": "Japan"}
    })


@app.get("/api/v2/me")
async def get_me():
    return JSONResponse(content={
        "id": 15651670,
        "username": "Googujiang",
        "is_online": True,
        "country": {"code": "JP", "name": "Japan"},
        "statistics": {
            "level": {"current": 97, "progress": 96},
            "pp": 2826.26,
            "global_rank": 298026,
            "country_rank": 11220,
            "hit_accuracy": 95.7168
        }
    })


@app.post("/signalr/metadata/negotiate")
async def metadata_negotiate(negotiateVersion: int = 1):
    return JSONResponse(content={
        "connectionId": "abc123",
        "availableTransports": [
            {
                "transport": "WebSockets",
                "transferFormats": ["Text", "Binary"]
            }
        ]
    })


@app.post("/signalr/spectator/negotiate")
async def spectator_negotiate(negotiateVersion: int = 1):
    return JSONResponse(content={
        "connectionId": "spec456",
        "availableTransports": [
            {
                "transport": "WebSockets",
                "transferFormats": ["Text", "Binary"]
            }
        ]
    })


@app.post("/signalr/multiplayer/negotiate")
async def multiplayer_negotiate(negotiateVersion: int = 1):
    return JSONResponse(content={
        "connectionId": "multi789",
        "availableTransports": [
            {
                "transport": "WebSockets",
                "transferFormats": ["Text", "Binary"]
            }
        ]
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
