# Trader - QQ Bot Virtual Stock Trading Plugin

A plugin for QQ bot framework (botpy) that simulates stock trading with real-time market data.

## Installation

### 1. Clone into your bot plugins directory

`
cd your-bot-project/plugins
git clone https://github.com/YOUR_USERNAME/trader.git
`

### 2. Install dependencies

`
pip install -r plugins/trader/requirements.txt
`

### 3. Configure

Add settings to your bot_config.json (see bot_config.example.json)

### 4. Run

Start your bot. The plugin loads automatically.
Admin panel: http://localhost:6662

## Commands

- 开户 - Create account
- 查余额 - Check balance
- 买入 X N - Buy N shares of X
- 卖出 X N - Sell N shares of X
- 持仓 - View holdings
- 行情 - View all stocks
- 打工 - Work once per day (1000-10000)
- 帮助 - Show help

## Features

- 8 real stocks (HK/A-shares) with Tencent Finance API
- Virtual stocks with configurable volatility
- Hash-based independent price simulation
- Per-stock volatility control
- Daily work bonus
- Web admin panel
- Button/text interaction modes
