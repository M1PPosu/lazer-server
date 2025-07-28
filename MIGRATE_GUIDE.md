# 数据库迁移指南

## 连接

使用默认的环境变量（`DATABASE_URL`）连接，如果不存在会从 `alembic.ini` 里读取 `sqlalchemy.url`。

## 创建迁移

修改数据库模型定义后，使用以下命令创建新的迁移脚本：

```bash
alembic revision --autogenerate -m "描述你的迁移"
```

请注意，以下修改操作无法生成自动迁移，请手动修改生成的迁移文件

- 修改表名
- 修改列名
- 匿名命名的约束

## 升级/回滚迁移

要应用所有未应用的迁移脚本，请运行：

```bash
alembic upgrade head
```

要升级/回滚版本，可以使用以下命令：

```bash 
# 回滚一个版本
alembic downgrade -1
# 升级两个版本
alembic upgrade +2
# 回滚到最初版本
alembic downgrade base
# 升级到特定版本
alembic upgrade <revision>
```

详情参考：[alembic 文档](https://alembic.sqlalchemy.org/en/latest/tutorial.html).