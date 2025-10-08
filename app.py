import os
import sys
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse
from flask import Flask, render_template, request, url_for

API_URL = "https://www.alphavantage.co/query"

app = Flask(__name__)

def parse_period(s: str) -> timedelta:
    """
    Accepts period strings like: 30m, 90m, 2h, 6h, 1d, 5d, 1w, 2w
    """
    s = s.strip().lower()
    if s.endswith("m"):
        return timedelta(minutes=int(s[:-1]))
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    if s.endswith("w"):
        return timedelta(weeks=int(s[:-1]))
    if s.endswith("y"):
        return timedelta(days=int(s[:-1]) * 365) # Approximation
    raise ValueError(f"Unsupported period: {s}")

def choose_interval(period: timedelta) -> str:
    """
    Pick Alpha Vantage intraday interval based on lookback.
    """
    total_mins = period.total_seconds() / 60.0
    if total_mins <= 120:    # <= 2h
        return "1min"
    if total_mins <= 2 * 24 * 60:  # <= 2d
        return "5min"
    if total_mins <= 7 * 24 * 60:  # <= 1w
        return "15min"
    if total_mins <= 14 * 24 * 60: # <= 2w
        return "30min"
    if total_mins <= 30 * 24 * 60: # <= 30d
        return "60min"
    return "daily"

def fetch_intraday(symbol: str, api_key: str, interval: str, full: bool) -> pd.DataFrame:
    """
    Calls Alpha Vantage TIME_SERIES_INTRADAY and returns a DataFrame with UTC timestamps.
    """
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": interval,
        "apikey": api_key,
        "datatype": "json",
        "outputsize": "full" if full else "compact",
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Handle API throttle / error messages
    if "Note" in data:
        raise RuntimeError(f"Alpha Vantage rate limit: {data['Note']}")
    if "Information" in data:
        raise RuntimeError(f"Alpha Vantage info: {data['Information']}")
    if "Error Message" in data:
        raise RuntimeError(f"Alpha Vantage error: {data['Error Message']}")
    key = next((k for k in data.keys() if k.startswith("Time Series")), None)
    if not key:
        raise RuntimeError(f"Unexpected response: {list(data.keys())}")

    ts = data[key]
    # ts is dict: { "2025-10-07 15:59:00": { "1. open": "...", ... } }
    records = []
    for ts_str, ohlc in ts.items():
        # Alpha Vantage timestamps are in the market time zone (usually US/Eastern)
        # Parse naïvely and treat as local timestamp; convert to UTC for consistency
        dt_local = isoparse(ts_str)  # naive or offset-aware
        if dt_local.tzinfo is None:
            # Assume timestamps are US/Eastern if naive; convert to UTC by attaching ET and converting.
            # To avoid tz database dependency, treat as naive and keep as naive; users can interpret.
            # Simpler: keep as naive and document. We'll store as naive; filtering will be by naive now().
            dt = dt_local
        else:
            dt = dt_local.astimezone(timezone.utc).replace(tzinfo=None)
        records.append({
            "time": dt,
            "open": float(ohlc["1. open"]),
            "high": float(ohlc["2. high"]),
            "low":  float(ohlc["3. low"]),
            "close":float(ohlc["4. close"]),
            "volume": int(float(ohlc["5. volume"])),
        })
    df = pd.DataFrame.from_records(records).sort_values("time")
    return df

def fetch_daily(symbol: str, api_key: str, full: bool) -> pd.DataFrame:
    """
    Calls Alpha Vantage TIME_SERIES_DAILY and returns a DataFrame.
    """
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "apikey": api_key,
        "datatype": "json",
        "outputsize": "full" if full else "compact",
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Handle API throttle / error messages
    if "Note" in data:
        raise RuntimeError(f"Alpha Vantage rate limit: {data['Note']}")
    if "Information" in data:
        raise RuntimeError(f"Alpha Vantage info: {data['Information']}")
    if "Error Message" in data:
        raise RuntimeError(f"Alpha Vantage error: {data['Error Message']}")
    key = next((k for k in data.keys() if k.startswith("Time Series")), None)
    if not key:
        raise RuntimeError(f"Unexpected response: {list(data.keys())}")

    ts = data[key]
    # ts is dict: { "2025-10-07": { "1. open": "...", ... } }
    records = []
    for ts_str, ohlc in ts.items():
        dt = isoparse(ts_str)
        records.append({
            "time": dt,
            "open": float(ohlc["1. open"]),
            "high": float(ohlc["2. high"]),
            "low":  float(ohlc["3. low"]),
            "close":float(ohlc["4. close"]),
            "volume": int(float(ohlc["5. volume"])),
        })
    df = pd.DataFrame.from_records(records).sort_values("time")
    return df

def get_stock_data(symbol, period_str):

    api_key = os.getenv("ALPHAVANTAGE_API_KEY")

    if not api_key:

        raise ValueError("API key not configured. Set ALPHAVANTAGE_API_KEY environment variable.")



    lookback = parse_period(period_str)

    interval = choose_interval(lookback)

    

    use_full_output = lookback > timedelta(days=100)



    if interval == "daily":

        df = fetch_daily(symbol, api_key, full=use_full_output)

    else:

        df = fetch_intraday(symbol, api_key, interval=interval, full=use_full_output)



    now_local = datetime.now()

    cutoff = now_local - lookback

    df_window = df[df["time"] >= cutoff].copy()



    return df_window, interval



@app.route('/')

def index():

    return render_template('index.html')



@app.route('/stockdata', methods=['POST'])

def stockdata():

    symbol = request.form['symbol']

    period_str = request.form['period']



    try:

        df_window, interval = get_stock_data(symbol, period_str)

    except (ValueError, RuntimeError) as e:

        return render_template('index.html', error=str(e))



    if df_window.empty:

        return render_template('index.html', error="No data in the requested window.")



    # Generate plot

    import matplotlib.pyplot as plt

    plt.figure()

    plt.plot(df_window["time"], df_window["close"])

    plt.title(f"{symbol} close ({interval})")

    plt.xlabel("Time")

    plt.ylabel("Close")

    plt.xticks(rotation=30, ha="right")

    plt.tight_layout()

    

    plot_path = os.path.join('static', 'stock_plot.png')

    plt.savefig(plot_path)

    plot_url = url_for('static', filename='stock_plot.png')



    return render_template('index.html', 

                           plot_url=plot_url, 

                           data=df_window.to_html(index=False))



def main_cli():

    if len(sys.argv) != 3:

        print("Usage: python app.py <symbol> <period>")

        sys.exit(1)



    symbol = sys.argv[1]

    period_str = sys.argv[2]



    try:

        df_window, interval = get_stock_data(symbol, period_str)

    except (ValueError, RuntimeError) as e:

        print(f"Error: {e}", file=sys.stderr)

        sys.exit(1)



    if df_window.empty:

        print("No data in the requested window.")

        sys.exit(0)



    print(df_window.to_string())



    # Generate plot

    import matplotlib.pyplot as plt

    plt.figure()

    plt.plot(df_window["time"], df_window["close"])

    plt.title(f"{symbol} close ({interval})")

    plt.xlabel("Time")

    plt.ylabel("Close")

    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.show()



if __name__ == "__main__":

    if len(sys.argv) > 1:

        main_cli()

    else:

        app.run(debug=True)
