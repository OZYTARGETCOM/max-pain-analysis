<<<<<<< HEAD
import streamlit as st
import requests
import math
import plotly.graph_objects as go
from datetime import datetime
import pandas as pd

# Tradier API Configuration
API_KEY = "U1iAJk1HhOCfHxULqzo2ywM2jUAX"
BASE_URL = "https://api.tradier.com/v1"

# App global configuration
st.set_page_config(page_title="Options Scanner", layout="wide")

# Display the logo at the top
st.image("ozy_target_logo.png", width=300)
st.title("OPTIONS SCANNER")

# Rest of your app code continues...


# Function to fetch current price
def get_current_price(ticker):
    try:
        url = f"{BASE_URL}/markets/quotes"
        headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
        params = {"symbols": ticker}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        quote = data.get("quotes", {}).get("quote", {})
        if isinstance(quote, list):
            quote = quote[0]
        return {
            "last": quote.get("last"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "volume": quote.get("volume"),
            "iv": quote.get("greeks", {}).get("iv_mean", "N/A")
        }
    except Exception as e:
        st.error(f"Error fetching current price: {e}")
        return None

# Function to fetch expiration dates
def get_expiration_dates(ticker):
    try:
        url = f"{BASE_URL}/markets/options/expirations"
        headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
        params = {"symbol": ticker}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("expirations", {}).get("date", [])
    except Exception as e:
        st.error(f"Error fetching expiration dates: {e}")
        return []

# Function to fetch options data
def get_options_data(ticker, expiration_date):
    try:
        url = f"{BASE_URL}/markets/options/chains"
        headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
        params = {"symbol": ticker, "expiration": expiration_date}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        options = data.get("options", {}).get("option", [])
        strikes_data = {}
        for option in options:
            strike = option["strike"]
            option_type = option["option_type"]
            open_interest = option.get("open_interest", 0)
            if strike not in strikes_data:
                strikes_data[strike] = {"CALL": 0, "PUT": 0}
            if option_type == "call":
                strikes_data[strike]["CALL"] += open_interest
            elif option_type == "put":
                strikes_data[strike]["PUT"] += open_interest
        return strikes_data
    except Exception as e:
        st.error(f"Error fetching options data: {e}")
        return {}

# Function to calculate Max Pain
def calculate_max_pain(strikes_data):
    max_pain_values = {}
    for target_strike in sorted(strikes_data.keys()):
        total_pain = 0
        for strike, oi_data in strikes_data.items():
            if strike < target_strike:
                total_pain += oi_data["CALL"] * (target_strike - strike)
            elif strike > target_strike:
                total_pain += oi_data["PUT"] * (strike - target_strike)
        max_pain_values[target_strike] = total_pain
    return min(max_pain_values, key=max_pain_values.get)

# Function to create Gamma Exposure chart
def gamma_exposure_chart(strikes_data, current_price):
    strikes = sorted(strikes_data.keys())
    gamma_calls = [strikes_data[s]["CALL"] for s in strikes]
    gamma_puts = [strikes_data[s]["PUT"] for s in strikes]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=strikes, y=gamma_calls, name='Gamma CALL', marker_color='blue'))
    fig.add_trace(go.Bar(x=strikes, y=[-g for g in gamma_puts], name='Gamma PUT', marker_color='red'))

    fig.add_shape(
        type="line",
        x0=current_price, x1=current_price,
        y0=min(-max(gamma_puts), -max(gamma_calls)),
        y1=max(gamma_calls),
        line=dict(color="orange", width=1, dash="solid"),
    )
    fig.add_annotation(
        x=current_price,
        y=max(gamma_calls),
        text=f"Current: ${current_price}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="orange",
        font=dict(color="orange", size=10),
        ax=30, ay=-40
    )

    fig.update_layout(
        title='Gamma Exposure',
        xaxis_title='Strike',
        yaxis_title='Gamma Exposure',
        barmode='relative',
        template='plotly_white'
    )
    return fig

# Function for comparative Call vs. Put Open Interest chart
def comparative_chart(strikes_data):
    df = pd.DataFrame({
        "Strike": list(strikes_data.keys()),
        "CALL OI": [strikes_data[s]["CALL"] for s in strikes_data],
        "PUT OI": [strikes_data[s]["PUT"] for s in strikes_data],
    })
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Strike"], y=df["CALL OI"], name="CALL OI", marker_color="blue"
    ))
    fig.add_trace(go.Bar(
        x=df["Strike"], y=df["PUT OI"], name="PUT OI", marker_color="red"
    ))
    fig.update_layout(
        title="Call vs. Put Open Interest",
        xaxis_title="Strike",
        yaxis_title="Open Interest",
        barmode="group",
        template="plotly_white"
    )
    return fig

# Layout for inputs (Ticker and Expiration)
st.sidebar.subheader("Inputs")
ticker = st.sidebar.text_input(" Ticker", "SPY").upper()
if ticker:
    expiration_dates = get_expiration_dates(ticker)
    if expiration_dates:
        expiration_date = st.sidebar.selectbox(" Expiration", expiration_dates)

        # Update Button
        if st.sidebar.button("Update Data"):
            price_data = get_current_price(ticker)
            if price_data:
                st.sidebar.write(f"Last Price: ${price_data['last']:.2f}")
                st.sidebar.write(f"High: ${price_data['high']:.2f}")
                st.sidebar.write(f"Low: ${price_data['low']:.2f}")
                st.sidebar.write(f"Volume: {price_data['volume']}")
                st.sidebar.write(f"IV: {price_data['iv']}")

        # Charts and Calculations
        strikes_data = get_options_data(ticker, expiration_date)
        if strikes_data:
            st.subheader("Analytics ")

            # Gamma Exposure Chart
            current_price = get_current_price(ticker)["last"]
            max_pain = calculate_max_pain(strikes_data)
            st.write(f"TARGET MP: ${max_pain}")

            st.write("### Gamma Exposure Chart")
            gamma_chart = gamma_exposure_chart(strikes_data, current_price)
            st.plotly_chart(gamma_chart, use_container_width=True)

            # Call vs. Put Open Interest Comparative Chart
            st.write("### Call vs. Put Open Interest Chart")
            comparative_fig = comparative_chart(strikes_data)
            st.plotly_chart(comparative_fig, use_container_width=True)

            # Export Data
            st.subheader("Export Data")
            export_data = pd.DataFrame({
                "Strike": list(strikes_data.keys()),
                "CALL OI": [strikes_data[s]["CALL"] for s in strikes_data],
                "PUT OI": [strikes_data[s]["PUT"] for s in strikes_data],
            })
            csv = export_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Options Data as CSV",
                data=csv,
                file_name=f'{ticker}_options_data.csv',
                mime='text/csv',
            )
=======
import streamlit as st
import requests
import math
import plotly.graph_objects as go
from datetime import datetime
import pandas as pd

# Tradier API Configuration
API_KEY = "U1iAJk1HhOCfHxULqzo2ywM2jUAX"
BASE_URL = "https://api.tradier.com/v1"

# App global configuration
st.set_page_config(page_title="Options Scanner", layout="wide")
st.title("OPTIONS SCANNER")

# Function to fetch current price
def get_current_price(ticker):
    try:
        url = f"{BASE_URL}/markets/quotes"
        headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
        params = {"symbols": ticker}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        quote = data.get("quotes", {}).get("quote", {})
        if isinstance(quote, list):
            quote = quote[0]
        return {
            "last": quote.get("last"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "volume": quote.get("volume"),
            "iv": quote.get("greeks", {}).get("iv_mean", "N/A")
        }
    except Exception as e:
        st.error(f"Error fetching current price: {e}")
        return None

# Function to fetch expiration dates
def get_expiration_dates(ticker):
    try:
        url = f"{BASE_URL}/markets/options/expirations"
        headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
        params = {"symbol": ticker}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("expirations", {}).get("date", [])
    except Exception as e:
        st.error(f"Error fetching expiration dates: {e}")
        return []

# Function to fetch options data
def get_options_data(ticker, expiration_date):
    try:
        url = f"{BASE_URL}/markets/options/chains"
        headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
        params = {"symbol": ticker, "expiration": expiration_date}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        options = data.get("options", {}).get("option", [])
        strikes_data = {}
        for option in options:
            strike = option["strike"]
            option_type = option["option_type"]
            open_interest = option.get("open_interest", 0)
            if strike not in strikes_data:
                strikes_data[strike] = {"CALL": 0, "PUT": 0}
            if option_type == "call":
                strikes_data[strike]["CALL"] += open_interest
            elif option_type == "put":
                strikes_data[strike]["PUT"] += open_interest
        return strikes_data
    except Exception as e:
        st.error(f"Error fetching options data: {e}")
        return {}

# Function to calculate Max Pain
def calculate_max_pain(strikes_data):
    max_pain_values = {}
    for target_strike in sorted(strikes_data.keys()):
        total_pain = 0
        for strike, oi_data in strikes_data.items():
            if strike < target_strike:
                total_pain += oi_data["CALL"] * (target_strike - strike)
            elif strike > target_strike:
                total_pain += oi_data["PUT"] * (strike - target_strike)
        max_pain_values[target_strike] = total_pain
    return min(max_pain_values, key=max_pain_values.get)

# Function to create Gamma Exposure chart
def gamma_exposure_chart(strikes_data, current_price):
    strikes = sorted(strikes_data.keys())
    gamma_calls = [strikes_data[s]["CALL"] for s in strikes]
    gamma_puts = [strikes_data[s]["PUT"] for s in strikes]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=strikes, y=gamma_calls, name='Gamma CALL', marker_color='blue'))
    fig.add_trace(go.Bar(x=strikes, y=[-g for g in gamma_puts], name='Gamma PUT', marker_color='red'))

    fig.add_shape(
        type="line",
        x0=current_price, x1=current_price,
        y0=min(-max(gamma_puts), -max(gamma_calls)),
        y1=max(gamma_calls),
        line=dict(color="orange", width=1, dash="solid"),
    )
    fig.add_annotation(
        x=current_price,
        y=max(gamma_calls),
        text=f"Current: ${current_price}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="orange",
        font=dict(color="orange", size=10),
        ax=30, ay=-40
    )

    fig.update_layout(
        title='Gamma Exposure',
        xaxis_title='Strike',
        yaxis_title='Gamma Exposure',
        barmode='relative',
        template='plotly_white'
    )
    return fig

# Function for comparative Call vs. Put Open Interest chart
def comparative_chart(strikes_data):
    df = pd.DataFrame({
        "Strike": list(strikes_data.keys()),
        "CALL OI": [strikes_data[s]["CALL"] for s in strikes_data],
        "PUT OI": [strikes_data[s]["PUT"] for s in strikes_data],
    })
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Strike"], y=df["CALL OI"], name="CALL OI", marker_color="blue"
    ))
    fig.add_trace(go.Bar(
        x=df["Strike"], y=df["PUT OI"], name="PUT OI", marker_color="red"
    ))
    fig.update_layout(
        title="Call vs. Put Open Interest",
        xaxis_title="Strike",
        yaxis_title="Open Interest",
        barmode="group",
        template="plotly_white"
    )
    return fig

# Layout for inputs (Ticker and Expiration)
st.sidebar.subheader("Inputs")
ticker = st.sidebar.text_input("Enter Ticker", "AAPL").upper()
if ticker:
    expiration_dates = get_expiration_dates(ticker)
    if expiration_dates:
        expiration_date = st.sidebar.selectbox("Select Expiration", expiration_dates)

        # Update Button
        if st.sidebar.button("Refresh Data"):
            price_data = get_current_price(ticker)
            if price_data:
                st.sidebar.write(f"Last Price: ${price_data['last']:.2f}")
                st.sidebar.write(f"High: ${price_data['high']:.2f}")
                st.sidebar.write(f"Low: ${price_data['low']:.2f}")
                st.sidebar.write(f"Volume: {price_data['volume']}")
                st.sidebar.write(f"IV: {price_data['iv']}")

        # Charts and Calculations
        strikes_data = get_options_data(ticker, expiration_date)
        if strikes_data:
            st.subheader("Analytics Results")

            # Gamma Exposure Chart
            current_price = get_current_price(ticker)["last"]
            max_pain = calculate_max_pain(strikes_data)
            st.write(f"Target Max Pain: ${max_pain}")

            st.write("### Gamma Exposure Chart")
            gamma_chart = gamma_exposure_chart(strikes_data, current_price)
            st.plotly_chart(gamma_chart, use_container_width=True)

            # Call vs. Put Open Interest Comparative Chart
            st.write("### Call vs. Put Open Interest Chart")
            comparative_fig = comparative_chart(strikes_data)
            st.plotly_chart(comparative_fig, use_container_width=True)

            # Export Data
            st.subheader("Export Data")
            export_data = pd.DataFrame({
                "Strike": list(strikes_data.keys()),
                "CALL OI": [strikes_data[s]["CALL"] for s in strikes_data],
                "PUT OI": [strikes_data[s]["PUT"] for s in strikes_data],
            })
            csv = export_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Options Data as CSV",
                data=csv,
                file_name=f'{ticker}_options_data.csv',
                mime='text/csv',
            )
>>>>>>> 4c844e497b3eb0165daaf02d8d7763304f51a7e3
