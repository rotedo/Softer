# FlowMap

Multi-exchange futures order flow: footprint + delta, liquidations, order book, funding/OI.

Files: main.py, index.html, requirements.txt, render.yaml, README.md

Render: New > Blueprint (render.yaml) ya Web Service
- Build: pip install -r requirements.txt
- Start: uvicorn main:app --host 0.0.0.0 --port $PORT
- Env: PYTHON_VERSION=3.11.9

Deploy ke baad:
- https://<app>.onrender.com/        (UI)
- https://<app>.onrender.com/api/health   (kaun sa exchange chal raha hai)

Env: COINS=BTC,ETH  EXCHANGES=binance,okx,bybit,bitget,gate,mexc,delta,coindcx
Extra exchanges: kucoin,bingx,htx,hyperliquid,deribit,kraken,bitmex,phemex
