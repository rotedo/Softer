# HANDOFF v2 — FlowMap/Softer pump system (new chat: read this first, then continue)
(Replaces the older HANDOFF_pump_system.md. Written 2026-11-28 ~17:15 IST.)

## User (Ayush)
Crypto futures trader, ANDROID PHONE ONLY (cannot run terminal commands), free Claude plan, speaks Hinglish by voice. Reply in SHORT HINDI, end with a few lines. Never ask him to paste secrets. Say clearly when something was tested only on fake data. Mention leverage/tiny-capital risk once, kindly (he has ~Rs 400 capital, thinks 5x leverage). Wants everything built in ONE go (complete files), reports problems after. Does NOT want many alerts: 1 alert/day or 1 per 2 days is fine; only RIGHT alerts; none while a trade is running; when linked coins pump together suggest ONE best coin, not all.

## Rules he set (unchanged)
- Chart candles ONLY from CoinDCX (live chart). Other data (open interest, funding, order book, taker ratio, history download) from any exchange (Binance), never for charts. Only coins listed on CoinDCX futures (~505).
- Nothing stored (20 GB limit); raw downloaded data is a temporary box.
- Live scan of all CoinDCX futures coins every 5-min candle, 24/7. Telegram alerts with Hindi "कारण:" reasons; second message with AI explanation; watchlist; Journal follow-up (सही/गलत + वजह).
- Code must NEVER see the future (sensors get candles up to NOW; backtest passes copy ending at candle i). No overfitting (plateaus, validate on separate coins/dates).
- Own setups in pump_custom.py (also alert on Telegram).
- GitHub holds only Python code; thresholds changed in UI /pump Settings tab, never files. AI only edits code, gives no data of its own. Server pulls GitHub main ~every 10 min.
- Process he wants: study pumps in groups (5 coins, next 5, last 4 = 3 checks), find what unusual activity happened BEFORE the pump, why a pump was missed / caught late, fix, re-check. Alerts must state reason. Not finalizing anything: forward-test first 3-4 live alerts WITHOUT real trades.
- Pump label is only an answer key for old data (live never knows pump size). He wants to catch even +20% pumps if the alert is genuine.

## Repo
github.com/rotedo/softer, branch main (use add_repo tool; user linked GitHub). Python stdlib + websockets.
Key files: main.py, web.py, app.html, pump_config.py (defaults + validation: PUMP, FIND, WINDOW, EVAL, STRATEGY_CONFIG, LIVE, FILTER, SELECT, MIN_STRATEGIES), pump_strategies.py (sensors, quality(), decide(), NEW strength()), pump_engine.py (label_pumps, alerts_for, run_coin, sweep), pump_select.py (NEW Selector), pump_validate.py, pump_live.py (CoinDCX scan, Telegram, watch list, JOURNAL), pump_web.py (/pump page: Download/Backtest/Live/Settings), pump_ai.py, pump_vision.py (Binance Vision loader), pump_lab.py (modes profile/test/universe/history/dcxcheck + trade_sim), pump_custom.py, tests test_pump.py/test_lab.py (FAKE data only; all pass).
Live is OFF by default (kv `pump_live`); user turns it ON in the Live tab. Live was NEVER run on real CoinDCX/Telegram.

## Real-data lab (sandbox has no Binance/CoinDCX access)
Write lab/job.json (a dict, or a LIST of jobs) -> push to main -> GitHub Action (.github/workflows/lab.yml) runs pump_lab.py on real Binance Vision data and commits lab_results/<name>.md; poll `git fetch --depth=1 origin main` + `git ls-tree -r origin/main --name-only | grep lab_results/<name>.md`, read with `git show origin/main:lab_results/<name>.md` (1-5 min).
GIT PITFALLS: clone is shallow. The Action commits results to main, so before every push do `git fetch --depth=50 origin main && git rebase origin/main`, then `git push origin HEAD:main`. Stop hook may nag "unpushed commit" — check `git status -sb` after fetch; usually it is already pushed.
Job settings bug (fixed): job-level "settings" are now applied after cfg.reset() for every candidate (earlier results universe1/universe2 used the DEFAULT label +15%/1h, not +20%/24h as believed).
Modes: profile (coins list with from/to: signals before pumps + timeline), universe (days,end,dcx:true, candidates with settings/detail/sim), history (months list, max_days, before; finds days with range >= PUMP.pct, downloads only those days, runs profile), dcxcheck.
Vision limits: newest day missing; current-month funding missing; OI/funding/taker/candles available for any older day (the 30-day limit is only Binance's live API).

## Defaults now in code (NON-FINAL)
MIN_STRATEGIES=3; PUMP label pct 30 / window 288 / merge_candles 288 (one pump per coin-day); EVAL cooldown 288; LIVE cooldown_min 1440; SELECT = enabled, max_per_day 3, pause_min 120, market_wide_n 10, min_score 0. Extra sensors (oi_build, trades_spike, range_expansion) left OFF (enabling them made it far worse: ~200 alerts/day, 5% right).
Selector (pump_select.py, same code in lab and live): per 5-min candle, if >= market_wide_n coins fire -> send nothing (market-wide move); else pick the highest strength() coin, name the others as "linked"; then daily cap, then pause after last alert, then min_score. Live sends text with "जुड़े coins" + "ताकत".

## Results (all real Binance Vision data unless noted; files in lab_results/)
- dcx_history: CoinDCX public candles API DOES give old 5m futures candles (BTC, ACE back ~1 year; a coin only from its listing, BULLA 90d-back empty). CoinDCX has candles only (no OI/funding).
- universe1 (Nov 22-26, label was actually +15%/1h): old defaults 119 alerts/day, ~11% right. 3 sensors 21/day 19.8%.
- universe3/4 (label +30%/24h one per coin-day = 7.2 pumps/day over CoinDCX coins, 36 pumps in 5 days):
  3 sensors no selection: 19.8 alerts/day, 19% right (+10% in 6h), caught 21/36 (only 2 early).
  With selector (3/day, pause 2h, mw10): 2.4/day, 41.7% right, caught 6/36 — but only 12 alerts in 5 days (tiny sample, also tuned on same days).
- grpA/B/C profile (14 coins: ACE BULLA EVAA AIOT MANTRA / BIGTIME SSV PROM ELSA INIT / ARIA CYS MMT AT): before a pump, first thing = volume + trades count spike (2-5x, ~1h before bottom or at bottom, price still 0-2% above bottom); OI often FALLS 5-20% before/at bottom, rises only AFTER the pump starts; taker-buy share useless; first spike is a warning, real run often hours later; spike also happens on normal days 1-3x per coin-day (false/day 1-3).
- history1 (Jan-Oct 2026, 499 CoinDCX coins, +70% in 24h): 835 candidate days -> 102 confirmed coin-days, 119 pumps (~12/month). Early signals (already% 12-18): trades x3, rng x3, oi12 >=2, vol3x3 etc., all fire on ~all pumps but with false/day 3-10 per coin. volx>=10 fired on 99/119, false 0.76/day/coin. Funding-negative fires LATE (already ~75% up) -> not an early signal. One pump shows +11,000% (BABY) = probably bad data; not cleaned.
- history2 (same, +60%): 178 coin-days, 207 pumps. Full signal table in lab_results/history2.md (read it; not yet used to build a rule).
- sim1 (30 days Oct 28-Nov 26, current live defaults+selector, 499 CoinDCX coins): 2.8 alerts/day, only 24.7% right (+10%/6h), 18.8% (+20%/24h), caught 20/240 pumps. TRADE SIM (Rs400, 5x, risk 5% of capital/trade, fee 0.1% + slippage 0.1% each side, no funding, one trade at a time, max hold 6h, stop checked first): ~83 trades; NO setting is profitable. Stop 1% -> ends ~Rs2-8 (lost 98%, 51-53 losing streak); 2% -> Rs112-276; 3% -> Rs93-296; 5% -> Rs293-389 (best: 5% stop, no TP: 59 trades, 34% wins, max win streak 4, lose streak 7, final Rs389 = -3%, max drawdown 55%). 5x with 5% risk forces a 1% stop which noise kills; ~0.4% round-trip costs hurt.
- CONCLUSION (honest): current live defaults are NOT profitable. The 42% right on 5 days was luck/overfit; 30-day is ~25%. Do not trade real money; Live ON only to watch.

## Next steps
1. Read lab_results/history2.md (and history1.md): build a NEW early-signal rule from the shared pre-pump pattern (e.g. volume spike x10 / trades x5 first, then OI fall, then price breakout, in that order) as SETTINGS, not hard-coded numbers.
2. Backtest it on the 30-day universe with the same trade_sim (add a sim candidate: "sim": true) and also on a DIFFERENT date range/coin group for validation. Count false alerts per day, losing streaks. Do not pick the best cell of the grid.
3. Study why pumps were missed/late (lab_results/sim1.md lists MISSED pumps; 220 of 240 missed) and which coins fire together (linked groups) — maybe add real correlation grouping.
4. Clean obvious bad data (e.g. BABY +11,000%) in history mode.
5. User turns Live ON in Live tab; watch first 3-4 alerts in Journal (no real trades); fix from why-wrong notes. Live never tested on real CoinDCX/Telegram: expect first-run bugs.
6. Re-run frozen final test when Vision has newer days (user phrase: "फाइनल दोबारा चलाओ").
7. Commit trailers: Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com> and Claude-Session: https://claude.ai/code/session_01UrZMZCLF6sLjMShdYED5uw
