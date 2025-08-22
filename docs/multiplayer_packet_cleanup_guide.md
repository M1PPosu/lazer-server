# 多人游戏数据包清理系统使用指南

## 概述

基于osu-server源码实现的多人游戏数据包清理系统，确保每局游戏结束后自动清理转发包和游戏状态数据，防止内存泄漏和性能问题。

## 主要改进

### 1. GameplayStateBuffer 增强功能

- **`cleanup_game_session(room_id)`**: 每局游戏结束后清理会话数据
- **`reset_user_gameplay_state(room_id, user_id)`**: 重置单个用户的游戏状态
- **保留房间结构**: 清理数据但保持房间活跃状态

### 2. MultiplayerPacketCleaner 数据包清理管理器

- **延迟清理**: 避免游戏过程中的性能影响
- **分类清理**: 按数据包类型（score、state、leaderboard）分类处理
- **强制清理**: 处理过期数据包
- **统计监控**: 提供清理统计信息

### 3. GameSessionCleaner 会话清理器

- **`cleanup_game_session(room_id, completed)`**: 游戏会话清理
- **`cleanup_user_session(room_id, user_id)`**: 用户会话清理
- **`cleanup_room_fully(room_id)`**: 房间完全清理

## 清理触发点

### 1. 每局游戏结束
```python
# 在 update_room_state() 中，当所有玩家完成游戏时
await self._cleanup_game_session(room_id, any_user_finished_playing)
```

### 2. 用户离开房间
```python
# 在 make_user_leave() 中清理用户数据
await GameSessionCleaner.cleanup_user_session(room_id, user_id)
```

### 3. 用户中断游戏
```python
# 在 AbortGameplay() 中重置用户状态
gameplay_buffer.reset_user_gameplay_state(room_id, user.user_id)
```

### 4. 主机中断比赛
```python
# 在 AbortMatch() 中清理所有玩家数据
await self._cleanup_game_session(room_id, False)  # False = 游戏被中断
```

### 5. 房间关闭
```python
# 在 end_room() 中完全清理房间
await GameSessionCleaner.cleanup_room_fully(room_id)
```

## 自动化机制

### 1. 定期清理任务
- 每分钟检查并清理过期数据包
- 防止内存泄漏

### 2. 数据包调度清理
- 5秒延迟清理（避免影响实时性能）
- 30秒强制清理（防止数据积累）

### 3. 状态感知清理
- 游戏状态变化时自动触发相应清理
- 用户状态转换时重置游戏数据

## 性能优化

### 1. 异步清理
- 所有清理操作都是异步的
- 不阻塞游戏主流程

### 2. 延迟执行
- 延迟清理避免频繁操作
- 批量处理提高效率

### 3. 分级清理
- 用户级别清理（个人数据）
- 会话级别清理（单局游戏）
- 房间级别清理（整个房间）

## 监控和调试

### 1. 清理统计
```python
stats = packet_cleaner.get_cleanup_stats()
# 返回: active_cleanup_tasks, pending_packets, rooms_with_pending_cleanup
```

### 2. 日志记录
- 详细的清理操作日志
- 错误处理和恢复机制

### 3. 错误处理
- 清理失败不影响游戏流程
- 优雅降级处理

## 与osu源码的对比

### 相似之处
1. **延迟清理机制**: 类似osu的清理调度
2. **分类数据包管理**: 按类型处理不同数据包
3. **状态感知清理**: 根据游戏状态触发清理
4. **错误隔离**: 清理错误不影响游戏

### Python特定优化
1. **异步协程**: 使用async/await提高并发性能
2. **字典缓存**: 使用defaultdict优化数据结构
3. **生成器**: 使用deque限制缓冲区大小
4. **上下文管理**: 自动资源清理

## 最佳实践

### 1. 及时清理
- 游戏结束立即触发会话清理
- 用户离开立即清理个人数据

### 2. 渐进式清理
- 先清理用户数据
- 再清理会话数据
- 最后清理房间数据

### 3. 监控资源使用
- 定期检查清理统计
- 监控内存和CPU使用

### 4. 日志分析
- 分析清理频率和效果
- 优化清理策略

## 配置选项

```python
# 数据包清理配置
cleanup_delay = 5.0  # 延迟清理时间（秒）
force_cleanup_delay = 30.0  # 强制清理时间（秒）
leaderboard_broadcast_interval = 2.0  # 排行榜广播间隔（秒）

# 缓冲区大小限制
score_buffer_maxlen = 50  # 分数帧缓冲区最大长度
```

通过这个系统，你的Python多人游戏实现现在具备了与osu源码类似的数据包清理能力，确保每局游戏结束后自动清理转发包，防止内存泄漏并保持系统性能。
