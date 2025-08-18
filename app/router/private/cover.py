from __future__ import annotations

import hashlib
from io import BytesIO

from app.database.lazer_user import User, UserProfileCover
from app.dependencies.database import Database
from app.dependencies.storage import get_storage_service
from app.dependencies.user import get_client_user
from app.storage.base import StorageService

from .router import router

from fastapi import Depends, File, HTTPException, Security
from PIL import Image


@router.post(
    "/cover/upload",
    name="上传头图",
)
async def upload_cover(
    session: Database,
    content: bytes = File(...),
    current_user: User = Security(get_client_user),
    storage: StorageService = Depends(get_storage_service),
):
    """上传用户头图

    接收图片数据，验证图片格式和大小后存储到存储服务，并更新用户的头图 URL

    限制条件:
    - 支持的图片格式: PNG、JPEG、GIF
    - 最大文件大小: 10MB
    - 最大图片尺寸: 3000x2000 像素

    返回:
    - 头图 URL 和文件哈希值
    """

    # check file
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    elif len(content) == 0:
        raise HTTPException(status_code=400, detail="File cannot be empty")
    try:
        with Image.open(BytesIO(content)) as img:
            if img.format not in ["PNG", "JPEG", "GIF"]:
                raise HTTPException(status_code=400, detail="Invalid image format")
            if img.size[0] > 3000 or img.size[1] > 2000:
                raise HTTPException(
                    status_code=400, detail="Image size exceeds 3000x2000 pixels"
                )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {e}")

    filehash = hashlib.sha256(content).hexdigest()
    storage_path = f"cover/{current_user.id}_{filehash}.png"
    if not await storage.is_exists(storage_path):
        await storage.write_file(storage_path, content)
    url = await storage.get_file_url(storage_path)
    current_user.cover = UserProfileCover(url=url)
    await session.commit()

    return {
        "url": url,
        "filehash": filehash,
    }
