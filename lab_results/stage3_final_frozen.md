# stage3_final_frozen  (test)
settings changed for this run: {"PUMP": {"pct": 20, "window": 288}, "EVAL": {"horizon": 144}, "STRATEGY_CONFIG": {"volume_spike": {"volume_multiplier": 4}, "price_momentum": {"min_return_pct": 3}, "open_interest": {"oi_change_percent": 4}}}
data: HAEDAL=1728, INIT=2016, PORTAL=1728, FET=2304, BULLA=3168
data notes:
HAEDALUSDT: no candle file for 1 day(s): 2026-11-27
HAEDALUSDT: no funding file (current month is published only after it ends)
INITUSDT: no candle file for 1 day(s): 2026-11-27
INITUSDT: no funding file (current month is published only after it ends)
PORTALUSDT: no candle file for 1 day(s): 2026-11-27
PORTALUSDT: no funding file (current month is published only after it ends)
FETUSDT: no candle file for 1 day(s): 2026-11-27
FETUSDT: no funding file (current month is published only after it ends)
BULLAUSDT: no candle file for 1 day(s): 2026-11-27
BULLAUSDT: no funding file (current month is published only after it ends)

```
TEST on 5 coins; pump = +20.0% in 1440 min; hit = +10.0% in 12h; need 2+ sensors for 'combined'
view            alerts hit% | pumps caught catch% early | lead(min) best% worst% | alerts/coin-day
volume_spike        70  34.3 |     6      5   83.3     4 |    2070.0  13.3   -6.0 | 1.84
price_momentum      26  53.8 |     6      6  100.0     3 |    1013.3  18.1  -12.2 | 0.68
open_interest       85  60.0 |     6      6  100.0     6 |    1530.0  18.9   -9.9 | 2.24
funding_rate         0     - |     6      0    0.0     0 |         -     -      - | 0.0
my_example_big_      0     - |     6      0    0.0     0 |         -     -      - | 0.0
combined            30  53.3 |     6      6  100.0     3 |    1335.8  19.4  -12.5 | 0.79
catch% = real pumps we alerted on in time. hit% = alerts followed by the hit move; the rest are false alerts.

PER COIN (combined view; 'all' = any single sensor):
HAEDAL   no pump found by the label in this window
INIT     pump 11-26 03:00->11-26 21:05 +81.8%: combined at 11-26 06:30 (already +7.6%, lead 875 min); earliest single: volume_spike at 11-26 06:15 (already +4.9%)
PORTAL   no pump found by the label in this window
FET      no pump found by the label in this window
BULLA    pump 11-18 01:30->11-18 16:50 +53.2%: combined at 11-18 04:20 (already +28.7%, lead 750 min); earliest single: volume_spike at 11-18 01:30 (already +3.6%)
BULLA    pump 11-18 17:15->11-19 05:45 +32.9%: combined at 11-19 03:05 (already +29.0%, lead 160 min); earliest single: volume_spike at 11-18 16:45 (already +36.7%)
BULLA    pump 11-20 15:45->11-23 10:55 +118.8%: combined at 11-21 15:35 (already +19.2%, lead 2600 min); earliest single: volume_spike at 11-20 17:45 (already +7.5%)
BULLA    pump 11-23 20:50->11-26 16:45 +215.5%: combined at 11-24 05:15 (already +14.2%, lead 3570 min); earliest single: open_interest at 11-23 21:50 (already +9.0%)
BULLA    pump 11-26 20:10->11-26 22:45 +107.8%: combined at 11-26 21:45 (already +82.0%, lead 60 min); earliest single: open_interest at 11-26 21:10 (already +53.0%)
```
(took 7s; real Binance Vision data; sensors see only the past)