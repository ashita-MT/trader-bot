# AGENTS.md

## Project Overview

QQ Bot 虚拟股市 + 彩票系统，基于 `botpy` 框架，采用插件化架构。
核心仓库：https://github.com/ashita-MT/trader-bot (test 分支)

## 项目结构

```
F:\Code\BOT\
├── main.py                     # 入口：启动 bot + admin 面板
├── config.py                   # 配置管理（bot_config.json 读写，线程安全）
├── bot_config.json             # 运行时配置（含 appid/secret，不提交 git）
├── bot_config.example.json     # 配置模板
├── requirements.txt            # 全局依赖
├── core/                       # Bot 框架核心
│   ├── bot.py                  # PluginBot：事件分发、指令路由
│   ├── plugin_loader.py        # 插件加载器（扫描 plugins/ 目录）
│   ├── base.py                 # BasePlugin 抽象基类
│   ├── command_parser.py       # 指令解析（支持 @提及 去除）
│   ├── keyboard.py             # QQ 消息按钮构建
│   ├── adapter.py              # InteractionMessage 适配器
│   └── utils.py                # get_user_id、MentionMessage
├── plugins/
│   └── trader/                 # 交易员插件（核心功能）
│       ├── plugin.py           # 插件入口 v1.8.0，注册所有指令
│       ├── plugin.json         # 插件元信息
│       ├── db.py               # SQLite schema + 自动迁移
│       ├── seed.py             # 初始化 8 只现实股票
│       ├── admin.py            # FastAPI 后台 API
│       ├── templates/index.html# 后台前端（单页 SPA）
│       ├── data/
│       │   ├── local_cache.py  # 股价本地缓存（每股票独立目录）
│       │   └── stocks/{code}/  # JSON 价格快照（最多保留 10 天）
│       ├── engine/
│       │   ├── real_market.py  # 腾讯财经 API 获取现实股价
│       │   ├── market.py       # 现实刷新 + 哈希虚拟股价刷新
│       │   ├── trading.py      # 买卖撮合、持仓、手续费
│       │   └── scheduler.py    # APScheduler 定时任务
│       ├── handlers/
│       │   ├── account.py      # 开户、查余额
│       │   ├── trade.py        # 买入、卖出、持仓
│       │   ├── market_view.py  # 行情
│       │   ├── work.py         # 打工（每日一次，1000-10000）
│       │   ├── number_lottery.py   # 号码彩（固定奖金）
│       │   └── pool_lottery.py     # 奖池彩（奖金池分配）
│       └── models/__init__.py
├── data/                       # 根级价格缓存（与 plugins/trader/data 同结构）
├── templates/index.html        # 根级后台模板（可能过时，以 plugins/trader/templates 为准）
└── trader-bot/                 # GitHub 发布用的镜像目录
```

## 启动方式

```bash
python main.py
```

- Bot 连接 QQ 官方 WebSocket
- Admin 面板在 `http://localhost:{web_port}`（默认 6662，端口被占自动 +1）
- 日志输出到 stdout/stderr

## 插件开发规范

### 新建插件

1. 在 `plugins/` 下创建目录，包含 `plugin.py`
2. `plugin.py` 中定义 `Plugin` 类继承 `core.base.BasePlugin`
3. 实现 `setup(bot)`、`teardown()`、`get_commands()` 三个方法
4. `get_commands()` 返回 `{指令名: handler}` 字典
5. handler 签名：`async def handler(message, args)`

### 添加新指令

1. 在 `plugins/trader/plugin.py` 的 `get_commands()` 中注册
2. 在 `plugins/trader/handlers/` 下实现 handler 函数
3. handler 通过 `message.reply(content=...)` 回复
4. 更新 `HELP_TEXT` 帮助文本

## 事件处理

| 事件 | 解析方式 | 是否需要@ | 回复是否@ |
|------|---------|----------|----------|
| `on_at_message_create` | `parse_with_at` | 是 | 是 |
| `on_group_at_message_create` | `parse_with_at` | 是 | 是 |
| `on_c2c_message_create` | `parse_raw` | 否 | 否 |
| `on_direct_message_create` | `parse_raw` | 否 | 否 |
| `on_interaction_create` | 按钮 data | - | 否 |
| `on_message_create` | 仅日志 | - | - |

## 用户 ID 规则

QQ 官方对不同场景返回不同 ID：
- 频道：`author.id`
- 私聊(C2C)：`author.user_openid`
- 群聊：`author.member_openid`

统一使用 `core.utils.get_user_id()` 获取。

## 数据库

- SQLite，路径：`plugins/trader/trader.db`
- 自动迁移：启动时检测并添加缺失列
- 表结构：users、stocks、holdings、orders、price_history、number_lottery_draws/tickets、pool_lottery_draws/tickets

## 现实股票

8 只固定股票（腾讯财经 API）：
- 港股：腾讯控股(00700)、阿里巴巴(09988)、京东集团(09618)、哔哩哔哩(09626)、美团(03690)
- A股：招商银行(600036)、贵州茅台(600519)、五粮液(000858)

## 虚拟股票

- 通过后台创建，默认关闭（需手动启用）
- 价格刷新：MD5 哈希算法，`hash(code + timestamp)` 生成随机涨跌幅
- 每只股票独立波动率（0-100%），为 0 则跳过涨跌

## Admin 后台 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取配置 |
| POST | `/api/config` | 保存配置 |
| GET | `/api/stats` | 仪表盘统计 |
| GET | `/api/stocks/real` | 现实股票列表 |
| GET | `/api/stocks/virtual` | 虚拟股票列表 |
| POST | `/api/stocks/virtual` | 创建虚拟股票 |
| PUT | `/api/stocks/virtual/{code}` | 修改虚拟股票 |
| DELETE | `/api/stocks/virtual/{code}` | 删除虚拟股票 |
| GET | `/api/lottery` | 彩票数据 |
| GET | `/api/users` | 用户列表 |
| GET | `/api/users/{qq_id}` | 用户详情+持仓 |

## 编码规范

- 所有中文内容直接写在 Python 字符串中（UTF-8）
- 金额计算精确到小数点后两位（`round(x, 2)`）
- 不要用 PowerShell 的 `Set-Content` 处理含中文的 Python 文件（会破坏编码），用 Python 脚本操作
- 文件编码统一 UTF-8

## 已知注意事项

- 端口被占用时自动递增寻找可用端口
- `trader-bot/` 是发布到 GitHub 的镜像，修改代码时注意同步
- `data/local_cache.py` 在根目录和 `plugins/trader/data/` 各有一份，实际使用的是插件内的
- `handlers/lottery.py` 是旧文件，已被 `number_lottery.py` 和 `pool_lottery.py` 替代

## 依赖

```
qq-botpy>=1.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
apscheduler>=3.10.0
```

安装：`pip install qq-botpy fastapi uvicorn apscheduler`
