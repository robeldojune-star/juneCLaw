#!/usr/bin/env python3
import os
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit
import pandas as pd
import sys
from pathlib import Path
import threading
import time
import json

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_ROOT, 'data', 'signals.csv')

# Ensure we can import shared and core modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.kiwoom_client import KiwoomAPIClient
from core.market_data_service import MarketDataService
from dotenv import load_dotenv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

def load_environment(env_name: str):
    base_dir = Path(__file__).resolve().parents[1]
    env_path = base_dir / "envs" / env_name / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
    os.environ["TRADING_ENV"] = env_name

def load_signals():
    if not os.path.isfile(DATA_FILE):
        return pd.DataFrame(columns=['time','stock','type','price','profit'])
    df = pd.read_csv(DATA_FILE)
    # parse time with explicit format
    df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
    return df.sort_values('time', ascending=False)

def get_account_info(env_name: str):
    base_dir = Path(__file__).resolve().parents[1]
    env_path = base_dir / "envs" / env_name / ".env"
    if not env_path.exists():
        return {"error": f"Environment file not found: {env_path}"}
    try:
        client = KiwoomAPIClient.from_env(env_path=env_path)
        mkt = MarketDataService(client)
        # Available cash and holdings from kt00004
        body = {
            "qry_tp": "1",          # 0: 총괄, 1: 상세
            "dmst_stex_tp": "KRX"   # Korean exchange
        }
        acct_info = client.post("kt00004", "/api/dostk/acnt", body)
        # The raw response is a dict; we extract needed fields
        # For simplicity, return the whole dict; frontend can pick fields
        return {
            "cash": acct_info,
            "holdings": acct_info.data.get('stk_acnt_evlt_prst', []) if hasattr(acct_info, 'data') else []
        }
    except Exception as e:
        return {"error": str(e)}

def background_thread():
    """Background thread to send realtime updates via socketio."""
    # Load mock environment for account data (dashboard uses mock for account info)
    load_environment("mock")
    while True:
        try:
            # Fetch data
            signals = load_signals()
            # Only process if not empty
            if not signals.empty:
                # Convert time to ISO string for JSON serialization
                signals['time'] = signals['time'].dt.strftime('%Y%m%d%H%M%S')
            records = signals.head(50).to_dict(orient='records')
            for record in records:
                for k, v in record.items():
                    if isinstance(v, float) and pd.isna(v):
                        record[k] = None
            # Fetch account data (using mock environment)
            accountData = get_account_info("mock")
            # Emit to all clients
            socketio.emit('update', {"signals": records, "accountData": accountData})
        except Exception as e:
            print(f"Error in background thread: {e}")
        socketio.sleep(30)  # send every 30 seconds

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/signals')
def api_signals():
    df = load_signals()
    df = df.head(50)
    # Convert time to ISO string for JSON serialization
    if not df.empty:
        df['time'] = df['time'].dt.strftime('%Y%m%d%H%M%S')
    # Replace NaN with None for valid JSON
    records = df.to_dict(orient='records')
    for record in records:
        for k, v in record.items():
            if isinstance(v, float) and pd.isna(v):
                record[k] = None
    return jsonify(records)

@app.route('/api/account')
def api_account():
    env = request.args.get('env', 'mock')
    data = get_account_info(env)
    return jsonify(data)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Optionally send current data immediately
    pass

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    # Start background thread
    thread = threading.Thread(target=background_thread)
    thread.daemon = True
    thread.start()
    socketio.run(app, host='0.0.0.0', port=3000, debug=False, allow_unsafe_werkzeug=True)