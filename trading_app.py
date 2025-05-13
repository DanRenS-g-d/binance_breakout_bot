from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from binance.client import Client
import os
import time
from dotenv import load_dotenv
import logging
import threading
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
client = Client(API_KEY, API_SECRET, testnet=True)  # Usar Testnet para pruebas seguras

# CONFIGURACIÓN
SYMBOL = 'BTCUSDT'
INTERVAL = Client.KLINE_INTERVAL_15MINUTE
LOOKBACK = 20
QUANTITY = 0.001
TP_PERCENT = 0.03
SL_PERCENT = 0.02
COMMISSION = 0.001
RANGE_THRESHOLD = 1.5
INITIAL_BALANCE = 1000

logging.basicConfig(filename='trading_bot.log', level=logging.INFO)

def wait_for_next_candle(interval_seconds=900):
    current_time = time.time()
    sleep_time = interval_seconds - (current_time % interval_seconds)
    time.sleep(sleep_time)

def get_klines(symbol, interval, lookback):
    return client.get_klines(symbol=symbol, interval=interval, limit=lookback)

def get_historical_klines(symbol, interval, start_ts, end_ts=None):
    """Obtener datos históricos usando timestamps en milisegundos."""
    try:
        start_ts_ms = int(start_ts.timestamp() * 1000)
        end_ts_ms = int(end_ts.timestamp() * 1000) if end_ts else None
        return client.get_historical_klines(symbol, interval, start_ts_ms, end_ts_ms)
    except Exception as e:
        logging.error(f"Error al obtener datos históricos: {e}")
        return []

def calculate_atr(klines, period=14):
    trs = [max(float(k[2]) - float(k[3]), abs(float(k[2]) - float(k[4])), abs(float(k[3]) - float(k[4]))) for k in klines[-period:]]
    return sum(trs) / period

def check_balance(symbol, quantity):
    asset = symbol.replace('USDT', '')
    info = client.get_asset_balance(asset=asset)
    balance = float(info['free'])
    if balance < quantity:
        logging.warning(f"Saldo insuficiente: {balance} < {quantity}")
        return False
    return True

def place_market_buy(symbol, quantity):
    try:
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
        logging.info(f"Compra ejecutada: {order}")
        return order
    except Exception as e:
        logging.error(f"Error en compra: {e}")
        return None

def breakout_bot():
    klines = get_klines(SYMBOL, INTERVAL, LOOKBACK)
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    volumes = [float(k[5]) for k in klines]

    highest_high = max(highs)
    lowest_low = min(lows)
    avg_volume = sum(volumes) / len(volumes)
    latest_volume = volumes[-1]
    current_price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])

    log_msg = f"Precio: {current_price}, Rango: {lowest_low}-{highest_high}, Volumen: {latest_volume}/{avg_volume}"
    socketio.emit('update', {'price': current_price, 'high': highest_high, 'low': lowest_low, 'volume': latest_volume, 'avg_volume': avg_volume})

    atr = calculate_atr(klines, period=14)
    range_percent = ((highest_high - lowest_low) / lowest_low) * 100
    atr_percent = (atr / lowest_low) * 100
    dynamic_threshold = max(RANGE_THRESHOLD, atr_percent * 1.5)

    if range_percent < dynamic_threshold:
        socketio.emit('status', {'message': f"Rango estrecho ({range_percent:.2f}% < {dynamic_threshold:.2f}%)"})
        return

    if current_price > highest_high and latest_volume > avg_volume:
        if check_balance(SYMBOL, QUANTITY):
            socketio.emit('status', {'message': "🚀 Breakout al alza detectado"})
            # place_market_buy(symbol=SYMBOL, quantity=QUANTITY)
            entry_price = current_price
            take_profit = entry_price * (1 + TP_PERCENT + COMMISSION)
            stop_loss = entry_price * (1 - SL_PERCENT - COMMISSION)
            socketio.emit('trade', {'type': 'long', 'entry': entry_price, 'tp': take_profit, 'sl': stop_loss})
            monitor_trade(entry_price, take_profit, stop_loss, trade_type='long')

    elif current_price < lowest_low and latest_volume > avg_volume:
        socketio.emit('status', {'message': "📉 Breakout a la baja detectado"})
        # client.order_market_sell(symbol=SYMBOL, quantity=QUANTITY)
        entry_price = current_price
        take_profit = entry_price * (1 - TP_PERCENT - COMMISSION)
        stop_loss = entry_price * (1 + SL_PERCENT + COMMISSION)
        socketio.emit('trade', {'type': 'short', 'entry': entry_price, 'tp': take_profit, 'sl': stop_loss})
        monitor_trade(entry_price, take_profit, stop_loss, trade_type='short')

    else:
        socketio.emit('status', {'message': "⏸️ No hay breakout claro"})

def monitor_trade(entry_price, tp, sl, trade_type='long'):
    while True:
        price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
        socketio.emit('monitor', {'price': price})

        if trade_type == 'long':
            if price >= tp:
                socketio.emit('status', {'message': "✅ TP alcanzado (long)"})
                break
            elif price <= sl:
                socketio.emit('status', {'message': "❌ SL alcanzado (long)"})
                break
        else:
            if price <= tp:
                socketio.emit('status', {'message': "✅ TP alcanzado (short)"})
                break
            elif price >= sl:
                socketio.emit('status', {'message': "❌ SL alcanzado (short)"})
                break
        time.sleep(30)

def backtest_breakout_bot(start_date, end_date, lookback=LOOKBACK, tp_percent=TP_PERCENT, sl_percent=SL_PERCENT):
    # Convertir fechas a objetos datetime
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.now()
    except ValueError as e:
        logging.error(f"Formato de fecha inválido: {e}")
        return {'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}

    # Obtener datos históricos usando timestamps
    klines = get_historical_klines(SYMBOL, INTERVAL, start_dt, end_dt)
    if not klines:
        return {'error': 'No se pudieron obtener datos históricos'}

    trades = []
    balance = INITIAL_BALANCE
    equity_curve = [balance]
    position = None

    for i in range(lookback, len(klines) - 1):
        current_klines = klines[i - lookback:i]
        highs = [float(k[2]) for k in current_klines]
        lows = [float(k[3]) for k in current_klines]
        volumes = [float(k[5]) for k in current_klines]

        highest_high = max(highs)
        lowest_low = min(lows)
        avg_volume = sum(volumes) / len(volumes)
        latest_volume = volumes[-1]
        current_price = float(klines[i][4])

        atr = calculate_atr(current_klines, period=14)
        range_percent = ((highest_high - lowest_low) / lowest_low) * 100
        atr_percent = (atr / lowest_low) * 100
        dynamic_threshold = max(RANGE_THRESHOLD, atr_percent * 1.5)

        if range_percent < dynamic_threshold:
            continue

        if current_price > highest_high and latest_volume > avg_volume and not position:
            entry_price = current_price
            take_profit = entry_price * (1 + tp_percent + COMMISSION)
            stop_loss = entry_price * (1 - sl_percent - COMMISSION)
            position = {'type': 'long', 'entry': entry_price, 'tp': take_profit, 'sl': stop_loss, 'time': klines[i][0]}

        elif current_price < lowest_low and latest_volume > avg_volume and not position:
            entry_price = current_price
            take_profit = entry_price * (1 - tp_percent - COMMISSION)
            stop_loss = entry_price * (1 + sl_percent + COMMISSION)
            position = {'type': 'short', 'entry': entry_price, 'tp': take_profit, 'sl': stop_loss, 'time': klines[i][0]}

        if position:
            next_high = float(klines[i + 1][2])
            next_low = float(klines[i + 1][3])

            if position['type'] == 'long':
                if next_high >= position['tp']:
                    exit_price = position['tp']
                    profit = (exit_price - position['entry']) * QUANTITY - (position['entry'] + exit_price) * QUANTITY * COMMISSION
                    balance += profit
                    trades.append({'type': 'long', 'entry': position['entry'], 'exit': exit_price, 'profit': profit, 'result': 'TP'})
                    position = None
                elif next_low <= position['sl']:
                    exit_price = position['sl']
                    profit = (exit_price - position['entry']) * QUANTITY - (position['entry'] + exit_price) * QUANTITY * COMMISSION
                    balance += profit
                    trades.append({'type': 'long', 'entry': position['entry'], 'exit': exit_price, 'profit': profit, 'result': 'SL'})
                    position = None
            else:
                if next_low <= position['tp']:
                    exit_price = position['tp']
                    profit = (position['entry'] - exit_price) * QUANTITY - (position['entry'] + exit_price) * QUANTITY * COMMISSION
                    balance += profit
                    trades.append({'type': 'short', 'entry': position['entry'], 'exit': exit_price, 'profit': profit, 'result': 'TP'})
                    position = None
                elif next_high >= position['sl']:
                    exit_price = position['sl']
                    profit = (position['entry'] - exit_price) * QUANTITY - (position['entry'] + exit_price) * QUANTITY * COMMISSION
                    balance += profit
                    trades.append({'type': 'short', 'entry': position['entry'], 'exit': exit_price, 'profit': profit, 'result': 'SL'})
                    position = None

            equity_curve.append(balance)

    total_trades = len(trades)
    winning_trades = len([t for t in trades if t['profit'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    total_profit = sum(t['profit'] for t in trades)
    max_drawdown = min(0, min(equity_curve) - INITIAL_BALANCE)

    plt.figure(figsize=(10, 6))
    plt.plot(equity_curve, label='Capital')
    plt.title('Curva de Capital - Backtesting')
    plt.xlabel('Operaciones')
    plt.ylabel('Saldo (USDT)')
    plt.legend()
    plt.grid(True)
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return {
        'trades': trades,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'balance': balance,
        'max_drawdown': max_drawdown,
        'equity_curve': plot_url
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_bot', methods=['POST'])
def start_bot():
    threading.Thread(target=run_bot).start()
    return jsonify({'status': 'Bot iniciado'})

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global running
    running = False
    return jsonify({'status': 'Bot detenido'})

@app.route('/backtest', methods=['POST'])
def run_backtest():
    data = request.json
    start_date = data['start_date']
    end_date = data['end_date']
    lookback = int(data.get('lookback', LOOKBACK))
    tp_percent = float(data.get('tp_percent', TP_PERCENT))
    sl_percent = float(data.get('sl_percent', SL_PERCENT))
    result = backtest_breakout_bot(start_date, end_date, lookback, tp_percent, sl_percent)
    return jsonify(result)

def run_bot():
    global running
    running = True
    while running:
        try:
            wait_for_next_candle()
            breakout_bot()
        except Exception as e:
            socketio.emit('status', {'message': f"⚠️ Error: {e}"})
            time.sleep(60)

if __name__ == '__main__':
    # Calcular fechas explícitas para el backtesting por defecto
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Ejecutar un backtest inicial
    print(f"Ejecutando backtest inicial desde {start_date.strftime('%Y-%m-%d')} hasta {end_date.strftime('%Y-%m-%d')}")
    backtest_result = backtest_breakout_bot(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    if 'error' not in backtest_result:
        print(f"Backtest completado: {backtest_result['total_trades']} operaciones, {backtest_result['win_rate']:.2f}% tasa de aciertos")
    else:
        print(f"Error en backtest inicial: {backtest_result['error']}")

    # Iniciar el servidor Flask
    socketio.run(app, debug=True)