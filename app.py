import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd

# Configuración de la API Tradier
API_KEY = "U1iAJk1HhOCfHxULqzo2ywM2jUAX"
BASE_URL = "https://api.tradier.com/v1"

# Configuración de la página
st.set_page_config(page_title="Advanced Options Analytics", layout="wide")
st.title("Advanced Options Analytics - Gamma and Max Pain")

# Función para obtener datos de precio
@st.cache_data
def get_price_data(ticker):
    url = f"{BASE_URL}/markets/quotes"
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    params = {"symbols": ticker}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get("quotes", {}).get("quote", {})
    else:
        st.error("Error fetching data from Tradier API")
        return None

# Función para obtener fechas de expiración
@st.cache_data
def get_expiration_dates(ticker):
    url = f"{BASE_URL}/markets/options/expirations"
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    params = {"symbol": ticker}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get("expirations", {}).get("date", [])
    else:
        st.error("Error fetching expiration dates")
        return []

# Función para obtener datos de opciones, incluyendo Delta y Theta
@st.cache_data
def get_options_data(ticker, expiration_date):
    url = f"{BASE_URL}/markets/options/chains"
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    params = {"symbol": ticker, "expiration": expiration_date, "greeks": "true"}  # Activar greeks
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        options = response.json().get("options", {}).get("option", [])
        strikes_data = {}
        for option in options:
            strike = option["strike"]
            option_type = option["option_type"]
            open_interest = option.get("open_interest", 0)
            volume = option.get("volume", 0)
            delta = option.get("greeks", {}).get("delta", 0)  # Extraer Delta
            theta = option.get("greeks", {}).get("theta", 0)  # Extraer Theta
            if strike not in strikes_data:
                strikes_data[strike] = {"CALL": {"OI": 0, "VOLUME": 0, "DELTA": 0, "THETA": 0},
                                        "PUT": {"OI": 0, "VOLUME": 0, "DELTA": 0, "THETA": 0}}
            if option_type == "call":
                strikes_data[strike]["CALL"]["OI"] += open_interest
                strikes_data[strike]["CALL"]["VOLUME"] += volume
                strikes_data[strike]["CALL"]["DELTA"] = delta
                strikes_data[strike]["CALL"]["THETA"] = theta
            elif option_type == "put":
                strikes_data[strike]["PUT"]["OI"] += open_interest
                strikes_data[strike]["PUT"]["VOLUME"] += volume
                strikes_data[strike]["PUT"]["DELTA"] = delta
                strikes_data[strike]["PUT"]["THETA"] = theta
        return strikes_data
    else:
        st.error("Error fetching options data")
        return {}

# Cálculo de Gamma Max Pain basado en OI combinado
def calculate_gamma_max_pain(strikes_data):
    max_pain_values = {}
    for target_strike in sorted(strikes_data.keys()):
        total_pain = 0
        for strike, data in strikes_data.items():
            if strike < target_strike:
                total_pain += (data["CALL"]["OI"] + data["PUT"]["OI"]) * (target_strike - strike)
            elif strike > target_strike:
                total_pain += (data["CALL"]["OI"] + data["PUT"]["OI"]) * (strike - target_strike)
        max_pain_values[target_strike] = total_pain
    return min(max_pain_values, key=max_pain_values.get)

# Cálculo de Max Pain basado en Volume
def calculate_max_pain_volume(strikes_data):
    max_pain_values = {}
    for target_strike in sorted(strikes_data.keys()):
        total_pain = 0
        for strike, data in strikes_data.items():
            if strike < target_strike:
                total_pain += (data["CALL"]["VOLUME"] + data["PUT"]["VOLUME"]) * (target_strike - strike)
            elif strike > target_strike:
                total_pain += (data["CALL"]["VOLUME"] + data["PUT"]["VOLUME"]) * (strike - target_strike)
        max_pain_values[target_strike] = total_pain
    return min(max_pain_values, key=max_pain_values.get)

# Cálculo de Max Pain basado en Open Interest individual
def calculate_max_pain_oi(strikes_data):
    max_pain_values = {}
    for target_strike in sorted(strikes_data.keys()):
        total_pain = 0
        for strike, data in strikes_data.items():
            if strike < target_strike:
                total_pain += data["CALL"]["OI"] * (target_strike - strike)
            elif strike > target_strike:
                total_pain += data["PUT"]["OI"] * (strike - target_strike)
        max_pain_values[target_strike] = total_pain
    return min(max_pain_values, key=max_pain_values.get)

# Función para obtener los top N strikes por métrica, incluyendo Delta y Theta
def get_top_strikes_with_greeks(strikes_data, metric, option_type, top_n=4):
    strikes = []
    for strike, data in strikes_data.items():
        value = data[option_type][metric]
        delta = data[option_type].get("DELTA", 0)  # Delta por strike
        theta = data[option_type].get("THETA", 0)  # Theta por strike
        strikes.append({"Strike": strike, metric: value, "Delta": delta, "Theta": theta})
    df = pd.DataFrame(strikes).sort_values(by=metric, ascending=False).head(top_n)
    return df

# Función para crear el gráfico de Gamma Exposure
def gamma_exposure_chart(strikes_data, current_price):
    strikes = sorted(strikes_data.keys())
    gamma_calls = [strikes_data[s]["CALL"]["OI"] for s in strikes]
    gamma_puts = [strikes_data[s]["PUT"]["OI"] for s in strikes]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=strikes, y=gamma_calls, name="Gamma CALL", marker_color="blue"))
    fig.add_trace(go.Bar(x=strikes, y=[-g for g in gamma_puts], name="Gamma PUT", marker_color="red"))

    # Línea para el precio actual
    fig.add_shape(
        type="line",
        x0=current_price, x1=current_price,
        y0=min(-max(gamma_puts), -max(gamma_calls)),
        y1=max(gamma_calls),
        line=dict(color="orange", width=1, dash="dot")
    )
    fig.add_annotation(
        x=current_price,
        y=max(gamma_calls) * 0.9,
        text=f"Current Price: ${current_price:.2f}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="orange",
        font=dict(color="orange", size=12)
    )

    fig.update_layout(
        title="Gamma Exposure",
        xaxis_title="Strike Price",
        yaxis_title="Gamma Exposure",
        barmode="relative",
        template="plotly_white"
    )
    return fig

# Sidebar para entradas
st.sidebar.subheader("Inputs")
ticker = st.sidebar.text_input("Enter Ticker", value="AAPL").upper()

# Sección 1: Información del Precio Actual
if ticker:
    expiration_dates = get_expiration_dates(ticker)
    if expiration_dates:
        expiration_date = st.sidebar.selectbox("Select Expiration", expiration_dates)
        price_data = get_price_data(ticker)

        if price_data:
            with st.expander("📈 Current Price"):
                st.write(f"**Last Price:** ${price_data['last']}")
                st.write(f"**High:** ${price_data['high']}")
                st.write(f"**Low:** ${price_data['low']}")
                st.write(f"**Volume:** {price_data['volume']}")

        strikes_data = get_options_data(ticker, expiration_date)

        # Sección 2: Métricas Clave
        if strikes_data:
            gamma_max_pain = calculate_gamma_max_pain(strikes_data)  # Gamma Max Pain basado en OI combinado
            volume_max_pain = calculate_max_pain_volume(strikes_data)  # Max Pain (Volume)
            oi_max_pain = calculate_max_pain_oi(strikes_data)  # Max Pain (OI)

            with st.expander("📊 Key Metrics"):
                st.write(f"**Gamma Max Pain (OI Combined):** ${gamma_max_pain}")
                st.write(f"**Max Pain (Volume):** ${volume_max_pain}")
                st.write(f"**Max Pain (OI):** ${oi_max_pain}")

            # Sección 3: Top Strikes con Delta y Theta
            with st.expander("📊 Top Strikes by Metrics"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Top 4 CALL Strikes by Open Interest")
                    top_call_oi = get_top_strikes_with_greeks(strikes_data, "OI", "CALL")
                    st.dataframe(top_call_oi)

                    st.markdown("#### Top 4 CALL Strikes by Volume")
                    top_call_volume = get_top_strikes_with_greeks(strikes_data, "VOLUME", "CALL")
                    st.dataframe(top_call_volume)

                with col2:
                    st.markdown("#### Top 4 PUT Strikes by Open Interest")
                    top_put_oi = get_top_strikes_with_greeks(strikes_data, "OI", "PUT")
                    st.dataframe(top_put_oi)

                    st.markdown("#### Top 4 PUT Strikes by Volume")
                    top_put_volume = get_top_strikes_with_greeks(strikes_data, "VOLUME", "PUT")
                    st.dataframe(top_put_volume)

            # Sección 4: Gráfico de Gamma Exposure
            current_price = price_data["last"]
            with st.expander("📉 Gamma Exposure Chart"):
                gamma_chart = gamma_exposure_chart(strikes_data, current_price)
                st.plotly_chart(gamma_chart, use_container_width=True)
