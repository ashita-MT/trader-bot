# Trader Bot

QQ bot with virtual stock trading plugin built on botpy framework.

## Installation

### Method 1: Full Bot (Recommended)

Clone the entire project and run directly.

`
git clone https://github.com/ashita-MT/trader-bot.git
cd trader-bot
pip install -r requirements.txt
cp bot_config.example.json bot_config.json
`

Edit bot_config.json:
- appid: Your QQ Bot App ID
- secret: Your QQ Bot App Secret

`
python main.py
`

### Method 2: Plugin Only

If you already have a botpy-based bot, clone just the plugin:

`
cd your-bot/plugins
git clone https://github.com/ashita-MT/trader-bot.git trader
pip install -r trader/requirements.txt
`

Add settings to your bot_config.json

## Commands

| Command | Description |
|---------|-------------|
| 开户 | Create account |
| 查余额 | Check balance |
| 买入 X N | Buy N shares of X |
| 卖出 X N | Sell N shares of X |
| 持仓 | View holdings |
| 行情 | View all stocks |
| 打工 | Work once per day (1000-10000) |
| 帮助 | Show help |

## Features

- 8 real stocks (HK/A-shares) with Tencent Finance API
- Virtual stocks with configurable volatility
- Hash-based independent price simulation
- Per-stock volatility control
- Daily work bonus
- Web admin panel (default: http://localhost:6662)
- Button/text interaction modes

## Admin Panel

Access http://localhost:6662 to:
- View stock/user statistics
- Manage virtual stocks (create/edit/delete)
- Configure interaction modes
- Set refresh intervals
- Enable/disable real/virtual stocks

## License

MIT