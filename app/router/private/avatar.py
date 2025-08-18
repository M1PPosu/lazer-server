from __future__ import annotations

import hashlib
from io import BytesIO

from app.database.lazer_user import User
from app.dependencies.database import Database
from app.dependencies.storage import get_storage_service
from app.dependencies.user import get_client_user
from app.storage.base import StorageService

from .router import router

from fastapi import Depends, File, HTTPException, Security
from PIL import Image


@router.post(
    "/avatar/upload",
    name="上传头像",
)
async def upload_avatar(
    session: Database,
    content: bytes = File(...),
    current_user: User = Security(get_client_user),
    storage: StorageService = Depends(get_storage_service),
):
    """上传用户头像

    接收图片数据，验证图片格式和大小后存储到存储服务，并更新用户的头像 URL

    限制条件:
    - 支持的图片格式: PNG、JPEG、GIF
    - 最大文件大小: 5MB
    - 最大图片尺寸: 256x256 像素

    返回:
    - 头像 URL 和文件哈希值
    """

    # check file
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    elif len(content) == 0:
        raise HTTPException(status_code=400, detail="File cannot be empty")
    try:
        with Image.open(BytesIO(content)) as img:
            if img.format not in ["PNG", "JPEG", "GIF"]:
                raise HTTPException(status_code=400, detail="Invalid image format")
            if img.size[0] > 256 or img.size[1] > 256:
                raise HTTPException(
                    status_code=400, detail="Image size exceeds 256x256 pixels"
                )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {e}")

    filehash = hashlib.sha256(content).hexdigest()
    storage_path = f"avatars/{current_user.id}_{filehash}.png"
    if not await storage.is_exists(storage_path):
        await storage.write_file(storage_path, content)
    url = await storage.get_file_url(storage_path)
    current_user.avatar_url = url
    await session.commit()

    return {
        "url": url,
        "filehash": filehash,
    }
