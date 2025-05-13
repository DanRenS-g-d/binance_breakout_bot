# Binance Breakout Trading Bot

A web application for algorithmic trading and backtesting on Binance Testnet, designed for users like Aymen. It detects breakout patterns in BTC/USDT and provides a responsive UI to monitor trades and analyze historical performance.

## Features

- **Real-time Trading**: Detects breakout patterns in BTC/USDT with configurable Take Profit (TP) and Stop Loss (SL).
- **Backtesting**: Analyzes trading strategy performance on historical data, generating metrics (win rate, profit, drawdown) and an equity curve.
- **Responsive UI**: Displays live price charts, trade details, and backtest results using Tailwind CSS and Chart.js.
- **WebSocket Updates**: Real-time market data and bot status via Flask-SocketIO.
- **Safe Testing**: Uses Binance Testnet to simulate trading without financial risk.

## Technologies

- **Backend**: Python, Flask, Flask-SocketIO, python-binance, matplotlib, python-dotenv
- **Frontend**: HTML, Tailwind CSS, JavaScript, Chart.js, SocketIO
- **Environment**: Binance Testnet API, dotenv for secure API key management

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/DanRenS-g-d/binance_breakout_bot
   cd binance_breakout_bot
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:

   - Copy `.env.example` to `.env`:

     ```bash
     cp .env.example .env
     ```
   - Edit `.env` with Binance Testnet API keys from Binance Testnet:

     ```
     API_KEY=your_testnet_api_key
     API_SECRET=your_testnet_api_secret
     ```

4. **Run the application**:

   ```bash
   python trading_app.py
   ```

   Open `http://127.0.0.1:5000` in your browser.

## Usage

- **Start/Stop Bot**: Click "Iniciar Bot" to begin trading or "Detener Bot" to pause.
- **Backtesting**: Enter dates (YYYY-MM-DD, e.g., `2025-04-12` to `2025-05-12`), lookback, TP%, and SL% in the backtest form, then click "Ejecutar Backtest" to view results.
- **Monitor**: View real-time prices, trade details, and bot status in the dashboard.

## Screenshots

## Project Structure

```
binance_breakout_bot/
├── trading_app.py          # Flask application and trading logic
├── templates/
│   └── index.html          # Frontend UI
├── screenshots/            # UI screenshots
├── .env.example            # Template for API keys
├── requirements.txt        # Python dependencies
├── .gitignore              # Files to exclude from Git
├── README.md               # Project documentation
```

## License

MIT License

## Contact

For issues or inquiries, contact drengifosulbaran@gmail.com or open an issue on GitHub.
