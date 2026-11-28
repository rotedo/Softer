# HANDOFF — FlowMap/Softer pump system (new chat: read this first, then continue)

## User (Ayush)
Crypto futures trader, ANDROID PHONE ONLY (cannot run terminal commands), free Claude plan, speaks Hinglish by voice. Reply in SHORT HINDI, end with a few lines. Never ask him to paste secrets. Say clearly when something was tested only on fake data. Mention leverage/tiny-capital risk once, kindly. Wants everything built in ONE go (complete files), he reports problems after.

## Rules he set
- Chart candles ONLY from CoinDCX. Other data (open interest, funding, order book, taker ratio) from any exchange, never for charts.
- Nothing stored (20 GB limit); raw downloaded data is a temporary box, deleted after checking.
- Live scan of ALL ~400-500 CoinDCX futures coins every 5-min candle, 24/7. Telegram alerts WITH reasons (Hindi "कारण:" lines). A second message with AI explanation why a coin rises. Watchlist.
- Code must NEVER see the future (sensors get candles up to NOW only; backtest passes a copy ending at candle i). No overfitting (prefer plateaus, validate on a separate coin group).
- Own setups go in separate Python file (pump_custom.py) and also alert on Telegram.
- GitHub holds only Python code; thresholds are changed in the UI /pump Settings tab, never in files. AI only edits code. Server pulls GitHub main ~every 10 min (he may reduce to 2 min).
- LATEST GOAL: ~5-6 of the 400 coins pump daily; catch them AT THE START; ONLY RIGHT alerts, kill garbage/fake signals. Not finalizing anything: add filters as SETTINGS, run on all coins, forward-test on first 3-4 live alerts, if wrong know WHY. Every alert must state the reason it fired.

## Repo
github.com/rotedo/softer, branch main (use add_repo tool; user already linked GitHub). Code is Python stdlib + websockets. Key files:
main.py, web.py, app.html, pump_config.py (defaults + validation; FILTER, STRATEGY_CONFIG, MIN_STRATEGIES, LIVE, EVAL), pump_strategies.py (sensors + quality() + decide() used by BOTH backtest and live), pump_engine.py (label_pumps, alerts_for, run_coin, sweep), pump_validate.py, pump_live.py (CoinDCX scan, Telegram, watch list, JOURNAL follow-up with RIGHT/WRONG + why-wrong), pump_web.py (/pump page: Download/Backtest/Live/Settings), pump_ai.py, pump_vision.py (Binance Vision loader), pump_lab.py (modes profile/test/universe), pump_custom.py, tests test_pump.py/test_lab.py (fake data only; all passed).
Live is OFF by default (kv `pump_live`); he turns it ON in the Live tab.

## Real-data lab (how analysis is done without network in sandbox)
Sandbox cannot reach Binance/CoinDCX. Workaround: write lab/job.json and push -> GitHub Action (.github/workflows/lab.yml) runs pump_lab.py on real Binance Vision data and commits lab_results/<name>.md; pull and read (~1-3 min). Vision lacks the newest day and current-month funding. A helper runjob.sh lived in the old sandbox scratchpad (may be gone; recreate: commit job.json, push, poll git fetch for lab_results/<name>.md).

## Findings so far (real data)
- Earliest signal at a pump bottom: volume/trades/range jump. OI often FALLS before a pump (short squeeze). More sensors agreeing (MIN_STRATEGIES) = biggest precision lever. Settings plateau: volume x3-5, momentum 2-5%, OI 3-5%.
- universe1 (Nov 22-26, 499 coins, pump label = +20% within 24h window, "right" = +10% in 6h):
  C0 no filters 2 sensors: 135 alerts/day, 13.6% right, caught 73/118
  C1 filters on, 2 sensors (current defaults): 119/day, 11.1% right, caught 34/118
  C2 filters, 3 sensors: 21/day, 19.8% right, caught 12/118
  C3 confirm 2: 33/day, 12.3%
  C4 confirm 2 + 3 sensors: 3.8/day, 21.1% right, caught 4/118
  C5 strict numbers: 8.6/day, 18.6%, caught 3/118
  Label found 23.6 pumps/day (not his 5-6; label +20%/24h counts repeats on same coin e.g. BULLA, BLESS, ACE many times; need stricter label like ONE big move per coin-day, +30%).
- CONCLUSION: current defaults are still far too noisy (119 alerts/day, ~89% wrong). Even best case only ~20% right. Honest gap: need new signal types/filters, not just thresholds. Ideas to test next: per-coin-day cap of 1 alert; require coin not already pumped in last 24h; rank alerts and send only top N/day; relative-strength vs BTC; require OI rising AND volume spike AND price breakout together; use order-book bids; time-to-peak stats; separate "early start" (already <=5%) metric. Also re-run Stage 3 final frozen test when Binance Vision publishes Nov 27 files (HAEDAL, PORTAL, FET, INIT, BULLA) — user will say "फाइनल दोबारा चलाओ".
- Live NOT tested on real CoinDCX/Telegram yet. Nothing on server changes until it pulls main.

## Next steps for new chat
1. Pull repo, read this + lab_results/universe1.md.
2. Tell user the honest result in short Hindi (alerts too many; right % low).
3. Run more universe candidates with a stricter pump label and per-coin-day cap/top-N ranking; pick a NON-FINAL default; set in pump_config defaults.
4. Ask him to turn Live ON for forward test of first 3-4 alerts; Journal tab shows reason + सही/गलत + वजह.
5. Commit with trailers: Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com> and Claude-Session line.
