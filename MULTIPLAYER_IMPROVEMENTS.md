# 多人游戏观战和实时排行榜改进说明

## 主要改进

### 1. 游戏状态缓冲区 (GameplayStateBuffer)
- **实时分数缓冲**: 为每个房间的每个玩家维护最多50帧的分数数据
- **实时排行榜**: 自动计算和维护实时排行榜数据
- **游戏状态快照**: 为新加入的观众创建完整的游戏状态快照
- **观战者状态缓存**: 跟踪观战者状态以优化同步

### 2. 观战同步管理器 (SpectatorSyncManager)
- **跨Hub通信**: 通过Redis在MultiplayerHub和SpectatorHub之间同步状态
- **事件通知**: 游戏开始/结束、用户状态变化等事件的实时通知
- **异步消息处理**: 订阅和处理观战相关事件

### 3. 增强的MultiplayerHub功能

#### 新增方法：
- `UpdateScore(client, score_data)`: 接收实时分数更新
- `GetLeaderboard(client)`: 获取当前排行榜
- `RequestSpectatorSync(client)`: 观战者请求状态同步

#### 改进的方法：
- `JoinRoomWithPassword`: 增强新用户加入时的状态同步
- `ChangeState`: 添加观战状态处理和分数缓冲区管理
- `start_gameplay`: 启动实时排行榜广播和创建游戏快照
- `change_room_state`: 处理游戏结束时的清理工作

### 4. 实时排行榜系统
- **自动广播**: 每秒更新一次实时排行榜
- **智能启停**: 根据游戏状态自动启动/停止广播任务
- **最终排行榜**: 游戏结束时发送最终排行榜

## 客户端集成示例

### JavaScript客户端示例
```javascript
// 连接到MultiplayerHub
const connection = new signalR.HubConnectionBuilder()
    .withUrl("/multiplayer")
    .build();

// 监听实时排行榜更新
connection.on("LeaderboardUpdate", (leaderboard) => {
    updateLeaderboardUI(leaderboard);
});

// 监听游戏状态同步（观战者）
connection.on("GameplayStateSync", (snapshot) => {
    syncSpectatorUI(snapshot);
});

// 监听最终排行榜
connection.on("FinalLeaderboard", (finalLeaderboard) => {
    showFinalResults(finalLeaderboard);
});

// 发送分数更新（玩家）
async function updateScore(scoreData) {
    try {
        await connection.invoke("UpdateScore", scoreData);
    } catch (err) {
        console.error("Error updating score:", err);
    }
}

// 请求观战同步（观战者）
async function requestSpectatorSync() {
    try {
        await connection.invoke("RequestSpectatorSync");
    } catch (err) {
        console.error("Error requesting sync:", err);
    }
}

// 获取当前排行榜
async function getCurrentLeaderboard() {
    try {
        return await connection.invoke("GetLeaderboard");
    } catch (err) {
        console.error("Error getting leaderboard:", err);
        return [];
    }
}
```

### Python客户端示例
```python
import signalrcore

# 创建连接
connection = signalrcore.HubConnectionBuilder() \
    .with_url("ws://localhost:8000/multiplayer") \
    .build()

# 监听排行榜更新
def on_leaderboard_update(leaderboard):
    print("Leaderboard update:", leaderboard)
    # 更新UI显示排行榜

connection.on("LeaderboardUpdate", on_leaderboard_update)

# 监听游戏状态同步
def on_gameplay_state_sync(snapshot):
    print("Gameplay state sync:", snapshot)
    # 同步观战界面

connection.on("GameplayStateSync", on_gameplay_state_sync)

# 发送分数更新
async def send_score_update(score, combo, accuracy):
    await connection.send("UpdateScore", {
        "score": score,
        "combo": combo,
        "accuracy": accuracy,
        "completed": False
    })

# 启动连接
connection.start()
```

## 配置要求

### Redis配置
确保Redis服务器运行并配置正确的连接参数：
```python
# 在app/dependencies/database.py中
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True
}
```

### 数据库表结构
确保`multiplayer_event`表包含以下字段：
- `event_detail`: JSON字段，用于存储事件详细信息

## 性能优化建议

1. **缓冲区大小调整**: 根据实际需求调整分数帧缓冲区大小（默认50帧）
2. **广播频率调整**: 可以根据网络条件调整排行榜广播频率（默认1秒）
3. **内存清理**: 定期清理过期的游戏状态快照和观战者状态
4. **连接池优化**: 配置Redis连接池以处理高并发请求

## 故障排除

### 常见问题
1. **排行榜不更新**: 检查Redis连接和广播任务状态
2. **观战者状态不同步**: 确认SpectatorSyncManager已正确初始化
3. **分数数据丢失**: 检查缓冲区大小和清理逻辑

### 日志监控
关键日志点：
- `[MultiplayerHub] Synced gameplay state for user X`
- `[MultiplayerHub] Broadcasted leaderboard update to room X`
- `Error updating score for user X`
- `Error in leaderboard broadcast loop`

### 调试模式
在开发环境中启用详细日志：
```python
import logging
logging.getLogger("app.signalr.hub.multiplayer").setLevel(logging.DEBUG)
```
