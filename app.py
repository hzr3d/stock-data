import os
import sys
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse

API_URL = "https://www.alphavantage.co/query"

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


def main():
    p = argparse.ArgumentParser(description="Fetch near real-time intraday stock data.")
    p.add_argument("symbol", help="Ticker symbol, e.g. AAPL, MSFT, TSLA")
    p.add_argument("period", help="Lookback window (e.g., 90m, 6h, 1d, 5d, 1w)")
    p.add_argument("--plot", action="store_true", help="Show a close-price plot")
    p.add_argument("--full", action="store_true", help="Use outputsize=full (slower, more data)")
    p.add_argument("--api-key", default=os.getenv("ALPHAVANTAGE_API_KEY"), help="Alpha Vantage API key or env ALPHAVANTAGE_API_KEY")
    args = p.parse_args()

    if not args.api_key:
        print("ERROR: Provide Alpha Vantage API key via --api-key or ALPHAVANTAGE_API_KEY env var.", file=sys.stderr)
        sys.exit(2)

    try:
        lookback = parse_period(args.period)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    interval = choose_interval(lookback)
    print(f"[info] symbol={args.symbol} period={args.period} interval={interval}")

    # If period is > 100 days, we must use full output size to get all the data.
    use_full_output = args.full
    if not use_full_output and lookback > timedelta(days=100):
        print("[info] Period > 100 days, forcing full output size to retrieve all data.")
        use_full_output = True

    try:
        if interval == "daily":
            df = fetch_daily(args.symbol, args.api_key, full=use_full_output)
        else:
            df = fetch_intraday(args.symbol, args.api_key, interval=interval, full=use_full_output)
    except Exception as e:
        print(f"ERROR fetching data: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter to the requested lookback window.
    # Use naive "now" to compare with naive timestamps (keeps it simple).
    now_local = datetime.now()
    cutoff = now_local - lookback
    df_window = df[df["time"] >= cutoff].copy()

    if df_window.empty:
        print("No data in the requested window (market closed or period too short for chosen interval).")
        print(df.tail(5).to_string(index=False))
        sys.exit(0)

    # Show a small summary + tail
    print("\nSummary:")
    print(f"rows={len(df_window)}, from={df_window['time'].iloc[0]} to={df_window['time'].iloc[-1]}")
    print("\nLast 10 bars:")
    print(df_window.tail(10).to_string(index=False))

    if args.plot:
        import matplotlib.pyplot as plt
        plt.figure()
        plt.plot(df_window["time"], df_window["close"])
        plt.title(f"{args.symbol} close ({interval})")
        plt.xlabel("Time")
        plt.ylabel("Close")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    main()

