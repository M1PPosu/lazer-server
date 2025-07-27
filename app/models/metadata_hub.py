from __future__ import annotations

from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _UserActivity(BaseModel):
    model_config = ConfigDict(serialize_by_alias=True)
    type: Literal[
        "ChoosingBeatmap",
        "InSoloGame",
        "WatchingReplay",
        "SpectatingUser",
        "SearchingForLobby",
        "InLobby",
        "InMultiplayerGame",
        "SpectatingMultiplayerGame",
        "InPlaylistGame",
        "EditingBeatmap",
        "ModdingBeatmap",
        "TestingBeatmap",
        "InDailyChallengeLobby",
        "PlayingDailyChallenge",
    ] = Field(alias="$dtype")
    value: Any | None = Field(alias="$value")


class ChoosingBeatmap(_UserActivity):
    type: Literal["ChoosingBeatmap"] = "ChoosingBeatmap"
    value: Literal[None] = None


class InGameValue(BaseModel):
    beatmap_id: int = Field(alias="BeatmapID")
    beatmap_display_title: str = Field(alias="BeatmapDisplayTitle")
    ruleset_id: int = Field(alias="RulesetID")
    ruleset_playing_verb: str = Field(alias="RulesetPlayingVerb")


class _InGame(_UserActivity):
    value: InGameValue = Field(alias="$value")


class InSoloGame(_InGame):
    type: Literal["InSoloGame"] = "InSoloGame"


class InMultiplayerGame(_InGame):
    type: Literal["InMultiplayerGame"] = "InMultiplayerGame"


class SpectatingMultiplayerGame(_InGame):
    type: Literal["SpectatingMultiplayerGame"] = "SpectatingMultiplayerGame"


class InPlaylistGame(_InGame):
    type: Literal["InPlaylistGame"] = "InPlaylistGame"


class EditingBeatmapValue(BaseModel):
    beatmap_id: int = Field(alias="BeatmapID")
    beatmap_display_title: str = Field(alias="BeatmapDisplayTitle")


class EditingBeatmap(_UserActivity):
    type: Literal["EditingBeatmap"] = "EditingBeatmap"
    value: EditingBeatmapValue = Field(alias="$value")


class TestingBeatmap(_UserActivity):
    type: Literal["TestingBeatmap"] = "TestingBeatmap"


class ModdingBeatmap(_UserActivity):
    type: Literal["ModdingBeatmap"] = "ModdingBeatmap"


class WatchingReplayValue(BaseModel):
    score_id: int = Field(alias="ScoreID")
    player_name: str = Field(alias="PlayerName")
    beatmap_id: int = Field(alias="BeatmapID")
    beatmap_display_title: str = Field(alias="BeatmapDisplayTitle")


class WatchingReplay(_UserActivity):
    type: Literal["WatchingReplay"] = "WatchingReplay"
    value: int | None = Field(alias="$value")  # Replay ID


class SpectatingUser(WatchingReplay):
    type: Literal["SpectatingUser"] = "SpectatingUser"


class SearchingForLobby(_UserActivity):
    type: Literal["SearchingForLobby"] = "SearchingForLobby"
    value: None = Field(alias="$value")


class InLobbyValue(BaseModel):
    room_id: int = Field(alias="RoomID")
    room_name: str = Field(alias="RoomName")


class InLobby(_UserActivity):
    type: Literal["InLobby"] = "InLobby"
    value: None = Field(alias="$value")


class InDailyChallengeLobby(_UserActivity):
    type: Literal["InDailyChallengeLobby"] = "InDailyChallengeLobby"
    value: None = Field(alias="$value")


UserActivity = (
    ChoosingBeatmap
    | InSoloGame
    | WatchingReplay
    | SpectatingUser
    | SearchingForLobby
    | InLobby
    | InMultiplayerGame
    | SpectatingMultiplayerGame
    | InPlaylistGame
    | EditingBeatmap
    | ModdingBeatmap
    | TestingBeatmap
    | InDailyChallengeLobby
)


class MetadataClientState(BaseModel):
    user_activity: UserActivity | None = None
    status: OnlineStatus | None = None

    def to_dict(self) -> dict[str, Any] | None:
        if self.status is None or self.status == OnlineStatus.OFFLINE:
            return None
        dumped = self.model_dump(by_alias=True, exclude_none=True)
        return {
            "Activity": dumped.get("user_activity"),
            "Status": dumped.get("status"),
        }

    @property
    def pushable(self) -> bool:
        return self.status is not None and self.status != OnlineStatus.OFFLINE


class OnlineStatus(IntEnum):
    OFFLINE = 0  # 隐身
    DO_NOT_DISTURB = 1
    ONLINE = 2
