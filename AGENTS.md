# AGENTS.md

## Project Overview

QQ Bot 多插件平台，基于 `botpy` 框架，采用插件化架构。
核心仓库：https://github.com/ashita-MT/trader-bot (test 分支)

包含三个插件：
- **admin** — 后台管理面板（指令统计、群聊信息、插件配置）
- **trader** — 虚拟股市 + 彩票系统
- **arena** — 卡牌银河战力党（12 角色 + 19 曜彩骰 + 22 种效果）

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
│   ├── admin/                  # 后台管理面板
│   │   ├── plugin.py           # 插件入口 + 命令钩子
│   │   ├── plugin.json         # 插件元信息
│   │   ├── db.py               # 指令日志 SQLite
│   │   ├── admin.py            # FastAPI 后台 API
│   │   └── templates/index.html# 管理面板前端
│   ├── trader/                 # 交易员插件
│   │   ├── plugin.py           # 插件入口
│   │   ├── plugin.json         # 插件元信息
│   │   ├── db.py               # SQLite schema + 自动迁移
│   │   ├── seed.py             # 初始化 8 只现实股票
│   │   ├── admin.py            # FastAPI 后台 API
│   │   ├── templates/index.html# 后台前端（单页 SPA）
│   │   ├── data/local_cache.py # 股价本地缓存
│   │   ├── engine/             # 市场引擎
│   │   └── handlers/           # 指令处理
│   └── arena/                  # 银河战力党插件
│       ├── plugin.py           # 插件入口 v4.0.0，12 个指令
│       ├── plugin.json         # 插件元信息
│       ├── game.py             # 游戏状态机（统一效果系统）
│       ├── effects.py          # 22 种效果定义 + 管理
│       ├── data.py             # 数据加载器
│       ├── cards.json          # 12 个角色卡牌
│       └── dice.json           # 19 个曜彩骰
├── data/                       # 根级价格缓存
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
2. 定义 `Plugin` 类继承 `core.base.BasePlugin`
3. 实现 `setup(bot)`、`teardown()`、`get_commands()`
4. `get_commands()` 返回 `{指令名: handler}` 字典
5. handler 签名：`async def handler(message, args)`

### 适配管理后台

所有插件必须在 `setup(bot)` 中调用 `register_plugin()` 向管理后台注册自身：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from plugins.admin.admin import register_plugin

class Plugin(BasePlugin):
    async def setup(self, bot):
        # ... 初始化代码 ...

        # 注册到管理后台（无配置项的插件可省略 config_schema）
        register_plugin("插件名", "插件描述", {
            "config_key": {"type": "boolean", "label": "显示名称", "default": True},
            "config_key2": {"type": "number", "label": "数值配置", "default": 300},
            "config_key3": {"type": "select", "label": "选项配置", "options": ["a", "b"], "default": "a"},
        })
```

**config_schema 规则：**
- `type`：`boolean`（开关）、`number`（数值）、`text`（文本）、`select`（下拉选择）
- `label`：管理面板显示的中文名称
- `default`：默认值（必填）
- `select` 类型额外需要 `options` 列表
- 配置项读写统一使用 `config.get(key)` / `config.set(key, value)`，自动持久化到 `bot_config.json`
- 无配置项的插件调用 `register_plugin("插件名", "描述")` 即可

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

- 频道：`author.id`
- 私聊(C2C)：`author.user_openid`
- 群聊：`author.member_openid`
- 统一使用 `core.utils.get_user_id()` 获取

## Arena 对战插件架构

### 角色卡牌（cards.json）

12 个角色，每个有：HP、攻防等级、骰子配置、技能描述。
- 黄泉保留 `skill` 字段（"洞穿"），其余角色通过卡牌名识别技能
- 技能在 `select_dice()` 和 `_resolve()` 中触发

### 曜彩骰（dice.json）

19 个曜彩骰，支持多种触发机制：
- `use_phase` — 使用阶段限制（"atk" / "def"）
- `condition` — 使用条件（"damage_taken_25" / "hp_le_8" / "round_5_plus" 等）
- `special_values` — 选中特定点数时触发
- 所有效果在选取曜彩骰时才触发，不选则无效果

### 效果系统（effects.py）

22 种效果，统一管理：
- 时机：pre_roll / post_roll / pre_resolve / atk / def / post_combat / instant
- 过期：never / turn / attack / use
- API：`add_effect()` / `remove_effect()` / `has_effect()` / `get_stacks()` / `clear_expired()`

### 如何开一局对战

1. A 发送「对战」创建房间，获取房间码
2. B 发送「接受 房间码」加入指定房间
3. 双方各自「选卡 角色名」和「选骰 曜彩骰名」
4. 全选完后随机一方获得先手，游戏开始

### 回合流程

```
攻击方: 投掷 -> 选取骰子 -> 结算攻击值
防御方: 投掷 -> 选取骰子 -> 结算防御值
                                    |
                            结算前：荆棘 + 中毒
                            伤害计算：攻击 - 防御
                            清除过期效果
                                    |
                            交换攻防，进入下一回合
```

伤害 = 攻击值 - 防御值，生命归零则败北。攻防每回合互换。

### 指令列表

| 指令 | 说明 |
|------|------|
| 对战 | 创建房间，获取房间码 |
| 接受 房间码 | 加入指定房间 |
| 选卡 角色名 | 选择角色卡牌 |
| 选骰 曜彩骰名 | 选择曜彩骰 |
| 投掷 / 重投 | 投掷骰子 / 重新投掷 |
| 选 1 2 3 | 按编号选取骰子 |
| 使用曜彩骰 | 使用曜彩骰（每局2次） |
| 投降 | 认输 |
| 对战卡牌 / 对战曜彩骰 | 查看卡牌 / 曜彩骰 |
| 银河战力党帮助 | 显示帮助 |

## 编码规范

- 所有中文内容直接写在 Python 字符串中（UTF-8）
- 金额计算精确到小数点后两位，50% 计算用 `//` 向下取整
- 不要用 PowerShell 的 `Set-Content` 处理含中文的 Python 文件（会破坏编码）
- 文件编码统一 UTF-8（JSON 读取用 `utf-8-sig` 处理 BOM）
- 角色技能通过卡牌名识别，不自创技能名

## 已知注意事项

- 端口被占用时自动递增寻找可用端口
- `trader-bot/` 是发布到 GitHub 的镜像，修改代码时注意同步
- `handlers/lottery.py` 是旧文件，已被 `number_lottery.py` 和 `pool_lottery.py` 替代
- `_mk_effects.py` 是临时脚本，可删除

## 依赖

```
qq-botpy>=1.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
apscheduler>=3.10.0
```

安装：`pip install qq-botpy fastapi uvicorn apscheduler`
