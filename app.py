import streamlit as st
import requests
import math
import plotly.graph_objects as go
from datetime import datetime
import time

# Configuración de la API de Tradier
API_KEY = "U1iAJk1HhOCfHxULqzo2ywM2jUAX"
BASE_URL = "https://api.tradier.com/v1"

# Configuración de actualización
update_interval_seconds = 10

# Función para obtener el precio actual
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
            return quote[0].get("last")
        return quote.get("last")
    except Exception as e:
        st.error(f"Error al obtener el precio actual: {e}")
        return None

# Función para obtener las fechas de expiración
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
        st.error(f"Error al obtener las fechas de expiración: {e}")
        return None

# Función para obtener datos de opciones
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
        st.error(f"Error al obtener datos de opciones: {e}")
        return None

# Función para calcular el Max Pain
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

# Gráfico de Gamma Exposure
def gamma_exposure_chart(strikes_data, current_price):
    """
    Gráfico de exposición gamma con una línea delgada para el precio actual.
    """
    strikes = sorted(strikes_data.keys())
    gamma_calls = [strikes_data[s]["CALL"] for s in strikes]
    gamma_puts = [strikes_data[s]["PUT"] for s in strikes]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=strikes, y=gamma_calls, name='Gamma CALL', marker_color='blue'))
    fig.add_trace(go.Bar(x=strikes, y=[-g for g in gamma_puts], name='Gamma PUT', marker_color='red'))

    # Línea vertical para el precio actual (extremadamente delgada)
    fig.add_shape(
        type="line",
        x0=current_price,
        x1=current_price,
        y0=min(-max(gamma_puts), -max(gamma_calls)),
        y1=max(gamma_calls),
        line=dict(color="orange", width=0.5, dash="solid"),  # Línea más delgada posible
    )
    fig.add_annotation(
        x=current_price,
        y=max(gamma_calls),
        text=f"Precio Actual: ${current_price}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="orange",
        font=dict(color="orange", size=10),
        ax=30, ay=-40
    )

    fig.update_layout(
        title='Gamma Exposure by Strike',
        xaxis_title='Strike',
        yaxis_title='Gamma Exposure',
        barmode='relative',
        template='plotly_white'
    )
    return fig

# Detectar niveles clave
def detect_key_levels(strikes_data):
    strikes = sorted(strikes_data.keys())
    gamma_net = [strikes_data[s]["CALL"] - strikes_data[s]["PUT"] for s in strikes]
    gamma_flip_index = next((i for i, g in enumerate(gamma_net) if g < 0), None)
    gamma_flip_point = strikes[gamma_flip_index] if gamma_flip_index else None
    high_oi_strikes = sorted(
        strikes,
        key=lambda s: strikes_data[s]["CALL"] + strikes_data[s]["PUT"],
        reverse=True
    )[:5]
    return gamma_flip_point, high_oi_strikes

# Configuración de Streamlit
st.set_page_config(page_title="Max Pain Analysis", layout="wide")
st.title("Max Pain Analysis")

# Entrada del usuario
ticker = st.sidebar.text_input("Ticker", "AAPL").upper()
if ticker:
    expiration_dates = get_expiration_dates(ticker)
    if expiration_dates:
        expiration_date = st.sidebar.selectbox("Fecha de Expiración", expiration_dates)
        strikes_data = get_options_data(ticker, expiration_date)
        
        # Contenedores dinámicos para precio y timestamp
        price_placeholder = st.empty()
        time_placeholder = st.empty()

        # Bloque estático para cálculos y gráficos
        if strikes_data:
            max_pain = calculate_max_pain(strikes_data)
            st.subheader(f"Max Pain Estimado: ${max_pain}")

            gamma_chart = gamma_exposure_chart(strikes_data, get_current_price(ticker))
            st.plotly_chart(gamma_chart, use_container_width=True)

            gamma_flip_point, high_oi_strikes = detect_key_levels(strikes_data)
            st.subheader("Niveles Clave Detectados")
            if gamma_flip_point:
                st.write(f"Gamma Flip Point: ${gamma_flip_point}")
            st.write(f"Strikes con Mayor Open Interest: {', '.join(map(str, high_oi_strikes))}")

        # Actualización dinámica del precio actual
        start_time = datetime.now()
        while True:
            with st.spinner("Actualizando precio en vivo..."):
                current_price = get_current_price(ticker)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if current_price:
                    price_placeholder.subheader(f"Precio Actual: ${current_price:.2f}")
                    time_placeholder.caption(f"Última actualización: {timestamp}")
                time.sleep(update_interval_seconds)
