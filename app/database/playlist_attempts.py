from sqlmodel import Field, SQLModel


class ItemAttemptsCount(SQLModel, table=True):
    __tablename__ = "item_attempts_count"  # pyright: ignore[reportAssignmentType]
    id: int = Field(foreign_key="room_playlists.db_id", primary_key=True, index=True)
    room_id: int = Field(foreign_key="rooms.id", index=True)
    attempts: int = Field(default=0)
    passed: int = Field(default=0)
