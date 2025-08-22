from __future__ import annotations

from app.database import Relationship, RelationshipResp, RelationshipType, User
from app.dependencies.database import Database
from app.dependencies.user import get_client_user, get_current_user

from .router import router

from fastapi import HTTPException, Path, Query, Request, Security
from pydantic import BaseModel
from sqlmodel import select


@router.get(
    "/friends",
    tags=["用户关系"],
    response_model=list[RelationshipResp],
    name="获取好友列表",
    description="获取当前用户的好友列表。",
)
@router.get(
    "/blocks",
    tags=["用户关系"],
    response_model=list[RelationshipResp],
    name="获取屏蔽列表",
    description="获取当前用户的屏蔽用户列表。",
)
async def get_relationship(
    db: Database,
    request: Request,
    current_user: User = Security(get_current_user, scopes=["friends.read"]),
):
    relationship_type = RelationshipType.FOLLOW if request.url.path.endswith("/friends") else RelationshipType.BLOCK
    relationships = await db.exec(
        select(Relationship).where(
            Relationship.user_id == current_user.id,
            Relationship.type == relationship_type,
        )
    )
    return [await RelationshipResp.from_db(db, rel) for rel in relationships.unique()]


class AddFriendResp(BaseModel):
    """添加好友/屏蔽 返回模型。

    - user_relation: 新的或更新后的关系对象。"""

    user_relation: RelationshipResp


@router.post(
    "/friends",
    tags=["用户关系"],
    response_model=AddFriendResp,
    name="添加或更新好友关系",
    description="**客户端专属**\n添加或更新与目标用户的好友关系。",
)
@router.post(
    "/blocks",
    tags=["用户关系"],
    name="添加或更新屏蔽关系",
    description="**客户端专属**\n添加或更新与目标用户的屏蔽关系。",
)
async def add_relationship(
    db: Database,
    request: Request,
    target: int = Query(description="目标用户 ID"),
    current_user: User = Security(get_client_user),
):
    relationship_type = RelationshipType.FOLLOW if request.url.path.endswith("/friends") else RelationshipType.BLOCK
    if target == current_user.id:
        raise HTTPException(422, "Cannot add relationship to yourself")
    relationship = (
        await db.exec(
            select(Relationship).where(
                Relationship.user_id == current_user.id,
                Relationship.target_id == target,
            )
        )
    ).first()
    if relationship:
        relationship.type = relationship_type
        # 这里原来如何是 block 也会修改为 follow
        # 与 ppy/osu-web 的行为保持一致
    else:
        relationship = Relationship(
            user_id=current_user.id,
            target_id=target,
            type=relationship_type,
        )
        db.add(relationship)
    origin_type = relationship.type
    if origin_type == RelationshipType.BLOCK:
        target_relationship = (
            await db.exec(
                select(Relationship).where(
                    Relationship.user_id == target,
                    Relationship.target_id == current_user.id,
                )
            )
        ).first()
        if target_relationship and target_relationship.type == RelationshipType.FOLLOW:
            await db.delete(target_relationship)
    current_user_id = current_user.id
    await db.commit()
    if origin_type == RelationshipType.FOLLOW:
        relationship = (
            await db.exec(
                select(Relationship).where(
                    Relationship.user_id == current_user_id,
                    Relationship.target_id == target,
                )
            )
        ).one()
        return AddFriendResp(user_relation=await RelationshipResp.from_db(db, relationship))


@router.delete(
    "/friends/{target}",
    tags=["用户关系"],
    name="取消好友关系",
    description="**客户端专属**\n删除与目标用户的好友关系。",
)
@router.delete(
    "/blocks/{target}",
    tags=["用户关系"],
    name="取消屏蔽关系",
    description="**客户端专属**\n删除与目标用户的屏蔽关系。",
)
async def delete_relationship(
    db: Database,
    request: Request,
    target: int = Path(..., description="目标用户 ID"),
    current_user: User = Security(get_client_user),
):
    relationship_type = RelationshipType.BLOCK if "/blocks/" in request.url.path else RelationshipType.FOLLOW
    relationship = (
        await db.exec(
            select(Relationship).where(
                Relationship.user_id == current_user.id,
                Relationship.target_id == target,
            )
        )
    ).first()
    if not relationship:
        raise HTTPException(404, "Relationship not found")
    if relationship.type != relationship_type:
        raise HTTPException(422, "Relationship type mismatch")
    await db.delete(relationship)
    await db.commit()
