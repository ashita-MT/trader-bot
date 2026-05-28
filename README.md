# Trader - QQ Bot Virtual Stock Trading Plugin

A QQ bot plugin that simulates stock trading with real-time market data integration and virtual stocks.

## Features

- Real stock prices from Tencent Finance API (HK/A-shares)
- Virtual stocks with configurable volatility
- Buy/sell/holdings management
- Daily work bonus
- Web admin panel
- Button/text interaction modes

## Quick Start

### 1. Clone

`ash
git clone https://github.com/YOUR_USERNAME/trader-bot.git
cd trader-bot
`

### 2. Install Dependencies

`ash
pip install -r requirements.txt
`

### 3. Configure

`ash
cp bot_config.example.json bot_config.json
`

Edit ot_config.json:
- ppid - Your QQ Bot App ID
- secret - Your QQ Bot App Secret

### 4. Run

`ash
python main.py
`

Bot will start with the admin panel at http://localhost:6662.

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

## Admin Panel

Access http://localhost:6662 to:
- View stock/user statistics
- Manage virtual stocks (create/edit/delete)
- Configure interaction modes
- Set refresh intervals
- Enable/disable real/virtual stocks

## Project Structure

`
├── main.py              # Entry point
├── admin.py             # Web admin panel
├── config.py            # Configuration manager
├── core/                # Bot framework
│   ├── bot.py           # Event handlers
│   ├── plugin_loader.py # Plugin system
│   ├── command_parser.py
│   ├── keyboard.py      # QQ button builder
│   ├── adapter.py       # Interaction adapter
│   ├── base.py          # Plugin base class
│   └── utils.py         # Utilities
├── plugins/
│   └── trader/          # Stock trading plugin
│       ├── plugin.py    # Plugin entry
│       ├── db.py        # Database schema
│       ├── seed.py      # Stock seeder
│       ├── engine/      # Core logic
│       │   ├── market.py
│       │   ├── trading.py
│       │   ├── real_market.py
│       │   └── scheduler.py
│       └── handlers/    # Command handlers
│           ├── account.py
│           ├── trade.py
│           ├── market_view.py
│           └── work.py
├── templates/
│   └── index.html       # Admin panel UI
└── data/
    └── local_cache.py   # Price cache
`

## License

MIT
