from __future__ import annotations

import base64
import hashlib
from io import BytesIO

from app.database.lazer_user import User
from app.dependencies.database import get_db
from app.dependencies.storage import get_storage_service
from app.storage.base import StorageService

from .router import router

from fastapi import Body, Depends, HTTPException
from PIL import Image
from sqlmodel.ext.asyncio.session import AsyncSession


@router.post("/avatar/upload", tags=["avatar"])
async def upload_avatar(
    file: str = Body(...),
    user_id: int = Body(...),
    storage: StorageService = Depends(get_storage_service),
    session: AsyncSession = Depends(get_db),
):
    content = base64.b64decode(file)

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # check file
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    elif len(content) == 0:
        raise HTTPException(status_code=400, detail="File cannot be empty")
    with Image.open(BytesIO(content)) as img:
        if img.format not in ["PNG", "JPEG", "GIF"]:
            raise HTTPException(status_code=400, detail="Invalid image format")
        if img.size[0] > 256 or img.size[1] > 256:
            raise HTTPException(
                status_code=400, detail="Image size exceeds 256x256 pixels"
            )

    filehash = hashlib.sha256(content).hexdigest()
    storage_path = f"avatars/{user_id}_{filehash}.png"
    if not await storage.is_exists(storage_path):
        await storage.write_file(storage_path, content)
    url = await storage.get_file_url(storage_path)
    user.avatar_url = url
    await session.commit()

    return {
        "url": url,
        "filehash": filehash,
    }
