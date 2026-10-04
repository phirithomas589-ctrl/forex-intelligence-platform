import streamlit as st
from dotenv import load_dotenv
from mt5_adapter import MT5Adapter, MT5Config, MT5Unavailable
from risk import build_protected_market_request, validate_trade_inputs

load_dotenv()
st.set_page_config(page_title="XAU/USD MT5 Integration", page_icon="🛡️", layout="wide")
st.title("XAU/USD Forex Trading Intelligence Platform")
st.caption("MT5 integration scaffold · DEMO ONLY · no account is connected by this package until configured")

def get_config():
    return MT5Config.from_env()

try:
    cfg = get_config()
except MT5Unavailable as exc:
    st.error(str(exc))
    st.info("Copy .env.example to .env, fill in your demo-account settings, and restart Streamlit.")
    st.stop()

st.warning("Demo-only execution guard is enabled. Verify the account shown below before submitting any order.")

with st.sidebar:
    st.subheader("Connection")
    st.write("Broker route: MetaTrader 5")
    st.write(f"Configured symbol: `{cfg.symbol}`")
    st.write(f"Execution enabled: `{cfg.execution_enabled}`")
    st.caption("Credentials are read from environment variables / .env, never entered into this page.")

adapter = MT5Adapter(cfg)
col1, col2, col3 = st.columns(3)
try:
    with adapter.session():
        account = adapter.account_info()
        terminal = adapter.terminal_info()
        tick = adapter.tick()
        col1.metric("Connection", "Connected")
        col2.metric("Account mode", "DEMO" if adapter.is_demo_account(account) else "NOT DEMO")
        col3.metric("XAU/USD bid / ask", f"{tick.bid:.2f} / {tick.ask:.2f}")
        st.write("**Account summary**")
        st.json({
            "login": getattr(account, "login", None),
            "server": getattr(account, "server", None),
            "currency": getattr(account, "currency", None),
            "balance": getattr(account, "balance", None),
            "equity": getattr(account, "equity", None),
            "terminal_connected": getattr(terminal, "connected", None),
        })
        st.subheader("Demo order ticket")
        side = st.radio("Direction", ["BUY", "SELL"], horizontal=True)
        volume = st.number_input("Volume (lots)", min_value=0.01, max_value=0.10, value=0.01, step=0.01)
        sl_distance = st.number_input("Stop-loss distance (price units)", min_value=1.0, value=5.0, step=0.5)
        rr = st.number_input("Reward:risk multiple", min_value=1.0, max_value=3.0, value=2.0, step=0.25)
        st.caption("This uses the current quote to calculate SL/TP. Actual fills may differ. Check your broker's gold contract and stop-distance rules.")
        confirm = st.checkbox("I confirm this is a DEMO account and want to submit this test order.")
        if st.button("Submit DEMO order with broker-side SL/TP", type="primary", disabled=not (confirm and cfg.execution_enabled)):
            try:
                request = build_protected_market_request(
                    adapter=adapter, side=side, volume=float(volume),
                    sl_distance=float(sl_distance), reward_risk=float(rr)
                )
                validate_trade_inputs(cfg, side, float(volume), float(sl_distance), float(rr))
                result = adapter.submit_demo_order(request)
                st.success("Broker returned an order result. Verify the position and SL/TP below.")
                st.json(result)
            except Exception as exc:
                st.error(f"Order not submitted / not confirmed: {exc}")

        st.subheader("Open XAU/USD positions")
        positions = adapter.positions()
        if not positions:
            st.info("No open positions returned for this symbol.")
        else:
            st.dataframe([{
                "ticket": p.ticket, "symbol": p.symbol, "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume, "price_open": p.price_open, "sl": p.sl, "tp": p.tp,
                "profit": p.profit
            } for p in positions], use_container_width=True)
except MT5Unavailable as exc:
    col1.metric("Connection", "Not connected")
    st.error(str(exc))
    st.markdown("""
    **Setup checklist**
    1. Install the desktop MetaTrader 5 terminal on the same Windows machine.
    2. Log into your broker's demo account in MT5.
    3. Copy `.env.example` to `.env` and fill in the demo login, password, server, terminal path and exact gold symbol.
    4. Install requirements and run `streamlit run app.py`.
    """)
