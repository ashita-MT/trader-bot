# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

QQ Bot 多插件平台，基于 `botpy` 框架，采用插件化架构。包含三个插件：admin（后台管理面板）、trader（虚拟股市+彩票）、arena（银河战力党卡牌对战）。

## 启动命令

```bash
python main.py
```

- Bot 连接 QQ 官方 WebSocket
- Admin 面板在 `http://localhost:{web_port}`（默认 6662，端口被占自动 +1）

## 依赖安装

```bash
pip install -r requirements.txt
```

## 架构

```
main.py          # 入口：启动 bot + admin 面板（uvicorn 线程）
config.py        # 配置管理（bot_config.json 读写，线程安全）
core/            # Bot 框架核心
  bot.py         # PluginBot：继承 botpy.Client，事件分发、指令路由
  base.py        # BasePlugin 抽象基类（setup/teardown/get_commands）
  plugin_loader.py  # 扫描 plugins/ 目录，动态加载 Plugin 类
  command_parser.py # 指令解析（支持 @提及 去除）
  utils.py       # get_user_id、MentionMessage
  adapter.py     # InteractionMessage 适配器
  keyboard.py    # QQ 消息按钮构建
plugins/         # 插件目录
  admin/         # 后台管理面板（FastAPI + SQLite 指令日志）
  trader/        # 虚拟股市 + 彩票
  arena/         # 银河战力党卡牌对战
```

## 插件开发规范

新建插件：
1. 在 `plugins/` 下创建目录，包含 `plugin.py`
2. 定义 `Plugin` 类继承 `core.base.BasePlugin`
3. 实现 `setup(bot)`、`teardown()`、`get_commands()`
4. `get_commands()` 返回 `{指令名: handler}` 字典
5. handler 签名：`async def handler(message, args)`

所有插件必须在 `setup(bot)` 中调用 `register_plugin()` 向管理后台注册自身。

## 配置

- `bot_config.json` 运行时配置（含 appid/secret，不提交 git）
- `bot_config.example.json` 配置模板
- `config.get(key)` / `config.set(key, value)` 统一配置读写

## 用户 ID 规则

统一使用 `core.utils.get_user_id()` 获取用户 ID：
- 频道：`author.id`
- 私聊(C2C)：`author.user_openid`
- 群聊：`author.member_openid`

## 编码规范

- 中文内容直接写在 Python 字符串中（UTF-8）
- 金额计算精确到小数点后两位，50% 计算用 `//` 向下取整
- 文件编码统一 UTF-8（JSON 读取用 `utf-8-sig` 处理 BOM）
- 不要用 PowerShell 的 `Set-Content` 处理含中文的 Python 文件

## 注意事项

- `trader-bot/` 是发布到 GitHub 的镜像，修改代码时注意同步
- 端口被占用时自动递增寻找可用端口
- `handlers/lottery.py` 是旧文件，已被 `number_lottery.py` 和 `pool_lottery.py` 替代
