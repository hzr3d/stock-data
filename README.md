✦ This Python script, app.py, is a command-line tool for fetching and displaying near real-time
  intraday stock data from the Alpha Vantage financial data API.

  Here is a detailed breakdown of what the code does:

  Overall Purpose

  The script's main goal is to retrieve historical intraday stock data for a given ticker
  symbol over a specified recent time period (e.g., the last 90 minutes, 6 hours, or 5 days).
  It then displays a summary of this data and can optionally plot the closing price over time.

  How It Works

   1. Argument Parsing: The script takes command-line arguments: a stock symbol, a period to
      look back, and optional flags like --plot to show a chart. It also requires an Alpha
      Vantage API key, which can be passed via the --api-key argument or set as an environment
      variable (ALPHAVANTAGE_API_KEY).

   2. Input Processing:
       * The human-readable period string (e.g., "90m", "1d") is parsed into a timedelta
         object, which represents a specific duration of time.
       * Based on the length of this duration, the script intelligently chooses an appropriate
         interval for the API call (e.g., "1min", "5min", "15min"). For shorter periods, it
         requests higher-resolution data (like 1-minute intervals), and for longer periods, it
         uses lower-resolution data (like 60-minute intervals).

   3. Data Fetching:
       * It makes an HTTP request to the Alpha Vantage TIME_SERIES_INTRADAY API endpoint.
       * It sends the stock symbol, the chosen interval, and the API key as parameters.
       * It handles potential errors from the API, such as rate-limiting notes or error
         messages, and will exit gracefully if an error occurs.

   4. Data Processing:
       * The JSON response from the API, which contains the time series data, is parsed.
       * The data is loaded into a pandas DataFrame, a powerful table-like data structure ideal
         for time-series analysis.
       * Each row in the DataFrame represents a single time interval and includes the
         timestamp, open, high, low, close prices, and volume.
       * Timestamps are converted to a consistent format.

   5. Filtering and Display:
       * The script filters the DataFrame to only include data within the user's requested
         lookback window.
       * It then prints a summary of the data (number of rows, start and end times) and the
         last 10 data points to the console.
       * If the --plot flag was used, it uses the matplotlib library to generate and display a
         simple line chart of the stock's closing price over the requested period.

  Key Functions


   * parse_period(s): Converts a string like "30m" or "2d" into a timedelta object that
     Python can understand.
   * choose_interval(period): Selects the optimal API interval ("1min", "5min", etc.) based on
      the total length of the period. This helps in fetching the most relevant data without
     requesting unnecessary detail.
   * fetch_intraday(...): This is the core function that communicates with the Alpha Vantage
     API, fetches the raw data, and transforms it into a clean pandas DataFrame.
   * main(): The main function that orchestrates the entire process, from parsing arguments
     to fetching data and displaying the results.

  Dependencies

  To run, the script requires the following Python libraries, which are listed in
  requirements.txt:
   * requests: For making HTTP API calls.
   * pandas: For data manipulation and analysis.
   * python-dateutil: For flexible date and time parsing.
   * matplotlib: For plotting the data (used only if you --plot).

How ro run:

1. Get an API key (free): https://www.alphavantage.co/support/#api-key

2. Install deps

python -m venv .venv && source .venv/bin/activate  
pip install -r requirements.txt
export ALPHAVANTAGE_API_KEY=YOUR_KEY  

3. Fetch data:

python app.py AAPL 90m --plot
python app.py MSFT 1d
python app.py TSLA 5d --full
python app.py TSLA 26w --plot
python app.py TSLA 5y --plot

