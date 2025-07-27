from sqlmodel import Field, SQLModel


class RoomIndex(SQLModel, table=True):
    __tablename__ = "mp_room_index"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(default=None, primary_key=True, index=True)  # pyright: ignore[reportCallIssue]
