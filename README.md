# XAU/USD MT5 Broker Integration Scaffold

This is a **demo-first integration scaffold**, not a connected account or a claim that any order has been placed.

## Important platform constraint
The official MetaTrader5 Python package communicates with a running desktop MT5 terminal. It is generally a Windows-oriented setup. Run Streamlit and the MT5 terminal on the same Windows machine or use a carefully secured Windows execution host. A typical Linux-only Streamlit cloud host cannot directly use a local desktop terminal.

## Setup
1. Install MetaTrader 5 desktop terminal from your broker.
2. Log in manually to a broker **demo** account.
3. Confirm the broker's exact gold symbol in Market Watch (e.g. `XAUUSD`, `GOLD`, or a suffixed symbol).
4. Use Python 3.10/3.11 on Windows and create a virtual environment.
5. `pip install -r requirements.txt`
6. Copy `.env.example` to `.env`; set demo credentials and terminal path.
7. Keep `MT5_DEMO_EXECUTION_ENABLED=false` while testing read-only connection.
8. Run `streamlit run app.py`.
9. Only after checking the displayed account is demo, set `MT5_DEMO_EXECUTION_ENABLED=true` to permit the small demo test ticket.

## Safety
- Never commit `.env` or put secrets in Streamlit widgets, source code, screenshots, logs or GitHub.
- The adapter refuses order submission unless execution is explicitly enabled and the account reports DEMO mode.
- Volume and position-count caps are enforced.
- The request includes `sl` and `tp` at entry; after the response, the adapter checks that an open position reports both levels.
- This is not a guarantee that a broker will accept or preserve the levels. Inspect the position in MT5.
- If protection verification fails, stop trading and investigate immediately.
- Do not enable live trading by changing a single flag. Build a separate reviewed live-mode path with independent credentials, stronger controls, monitoring and explicit approvals.
- Stops can slip during gaps/fast markets; losses can exceed the intended amount depending on product and broker terms.

## Test
`pytest -q`

The tests validate input guards only; they do not connect to MT5 or place orders.

## Official references
- Python integration: https://www.mql5.com/en/docs/python_metatrader5
- initialize/login: https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py
- order_send: https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py
