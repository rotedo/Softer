# stage2_sweep  (test)
settings changed for this run: {"PUMP": {"pct": 20, "window": 288}, "EVAL": {"horizon": 144}}
data: BLUR=3744, EVAA=5472, MMT=4608, LISTA=3168, ICNT=4608
data notes:
BLURUSDT: no funding file (current month is published only after it ends)
EVAAUSDT: no funding file (current month is published only after it ends)
MMTUSDT: no funding file (current month is published only after it ends)
LISTAUSDT: no funding file (current month is published only after it ends)
ICNTUSDT: no funding file (current month is published only after it ends)

```
TEST on 5 coins; pump = +20.0% in 1440 min; hit = +10.0% in 12h; need 2+ sensors for 'combined'
view            alerts hit% | pumps caught catch% early | lead(min) best% worst% | alerts/coin-day
volume_spike       243  33.7 |    15     13   86.7    12 |    2691.9  10.3   -6.8 | 3.24
price_momentum      91  41.8 |    15     14   93.3    11 |    2221.1  13.7   -9.6 | 1.21
open_interest      155  54.8 |    15     15  100.0    13 |    2220.7  16.5   -8.7 | 2.07
funding_rate         0     - |    15      0    0.0     0 |         -     -      - | 0.0
my_example_big_      0     - |    15      0    0.0     0 |         -     -      - | 0.0
combined            77  49.4 |    15     13   86.7     9 |    2330.4  14.7   -9.9 | 1.03
catch% = real pumps we alerted on in time. hit% = alerts followed by the hit move; the rest are false alerts.

PER COIN (combined view; 'all' = any single sensor):
BLUR     pump 11-22 07:00->11-26 01:05 +65.6%: combined at 11-22 15:30 (already +7.4%, lead 4895 min); earliest single: volume_spike at 11-22 12:25 (already +4.6%)
EVAA     pump 11-08 21:55->11-09 12:35 +22.8%: combined: MISSED; earliest single: volume_spike at 11-08 21:55 (already +3.9%)
EVAA     pump 11-14 10:05->11-17 09:40 +307.1%: combined at 11-14 14:10 (already +20.7%, lead 4050 min); earliest single: volume_spike at 11-14 11:20 (already +4.0%)
EVAA     pump 11-18 01:05->11-21 08:50 +118.2%: combined at 11-18 04:55 (already +13.7%, lead 4555 min); earliest single: price_momentum at 11-18 04:25 (already +8.9%)
EVAA     pump 11-22 09:40->11-22 13:25 +49.1%: combined at 11-22 10:25 (already +27.8%, lead 180 min); earliest single: open_interest at 11-22 10:20 (already +25.5%)
EVAA     pump 11-22 18:10->11-23 12:30 +58.2%: combined at 11-23 03:50 (already +25.5%, lead 520 min); earliest single: open_interest at 11-22 18:45 (already +12.3%)
EVAA     pump 11-24 11:40->11-26 13:50 +77.3%: combined at 11-24 14:25 (already +42.2%, lead 2845 min); earliest single: open_interest at 11-24 13:20 (already +18.8%)
MMT      pump 11-16 13:20->11-19 18:40 +215.7%: combined at 11-16 15:15 (already +10.3%, lead 4525 min); earliest single: volume_spike at 11-16 14:30 (already +2.2%)
MMT      pump 11-22 04:40->11-22 10:25 +24.5%: combined at 11-22 09:45 (already +23.1%, lead 40 min); earliest single: volume_spike at 11-22 06:25 (already +7.4%)
MMT      pump 11-22 11:45->11-22 14:40 +20.6%: combined: MISSED; earliest single: open_interest at 11-22 12:40 (already +12.3%)
MMT      pump 11-23 17:55->11-24 08:00 +48.1%: combined at 11-24 02:30 (already +22.0%, lead 330 min); earliest single: price_momentum at 11-23 21:10 (already +7.6%)
MMT      pump 11-24 14:15->11-25 20:30 +52.9%: combined at 11-25 09:50 (already +12.3%, lead 640 min); earliest single: volume_spike at 11-24 14:05 (already +1.3%)
MMT      pump 11-26 16:40->11-26 18:15 +21.9%: combined at 11-26 18:15 (already +21.2%, lead 0 min); earliest single: volume_spike at 11-26 16:45 (already +7.6%)
LISTA    pump 11-22 03:00->11-25 16:20 +86.7%: combined at 11-22 18:30 (already +12.9%, lead 4190 min); earliest single: volume_spike at 11-22 04:10 (already +0.7%)
ICNT     pump 11-17 00:20->11-20 07:35 +111.1%: combined at 11-17 20:50 (already +11.1%, lead 3525 min); earliest single: volume_spike at 11-17 01:35 (already +2.5%)

SETTINGS SWEEP on 5 coin(s). One setting changed at a time (* = your current number). 'combined' = enough sensors agree.
setting              value | caught early | lead(min) already% | alerts hit% alerts/day

volume_multiplier         2 | 14/15     11 |   2216.4     15.6 |    100  47.0 1.33
volume_multiplier        3* | 13/15      9 |   2330.4     19.2 |     77  49.4 1.03
volume_multiplier         4 | 13/15      8 |   2316.2     20.5 |     69  46.4 0.92
volume_multiplier         5 | 12/15      8 |   2460.4     19.6 |     63  47.6 0.84
volume_multiplier         8 | 12/15      8 |   2457.5     19.8 |     55  47.3 0.73

min_return_pct            1 | 13/15     10 |   2448.1     16.5 |     97  43.3 1.29
min_return_pct           2* | 13/15      9 |   2330.4     19.2 |     77  49.4 1.03
min_return_pct            3 | 13/15      9 |   2330.4     19.2 |     72  48.6 0.96
min_return_pct            5 | 13/15      9 |   2330.4     19.2 |     62  53.2 0.83

bars                      2 | 13/15     10 |   2367.7     17.5 |     94  48.9 1.25
bars                     3* | 13/15      9 |   2330.4     19.2 |     77  49.4 1.03
bars                      4 | 11/15     10 |   2735.9     16.0 |     69  49.3 0.92

breakout_candles         12 | 13/15     10 |   2335.4     17.4 |     83  51.8 1.11
breakout_candles        24* | 13/15      9 |   2330.4     19.2 |     77  49.4 1.03
breakout_candles         48 | 11/15      9 |   2737.7     18.3 |     67  46.3 0.89

oi_change_percent         2 | 14/15     11 |   2352.9     12.7 |    137  44.5 1.83
oi_change_percent         3 | 14/15     11 |   2298.9     16.2 |    109  44.0 1.45
oi_change_percent        5* | 13/15      9 |   2330.4     19.2 |     77  49.4 1.03
oi_change_percent         8 | 10/15      8 |   2867.5     21.1 |     54  53.7 0.72

MIN_STRATEGIES            1 | 15/15     13 |   2410.0      8.0 |    328  39.3 4.37
MIN_STRATEGIES           2* | 13/15      9 |   2330.4     19.2 |     77  49.4 1.03
MIN_STRATEGIES            3 | 9/15      8 |   2765.6     26.5 |     21  61.9 0.28

How to read: lead = minutes between the alert and the top; already% = how much the price had already risen when the alert came (small = early).
Do NOT pick the single best row (that is overfitting). Prefer a RANGE of neighbouring values that all catch the move with few alerts per day, then check the same numbers on Group B.
```
(took 13s; real Binance Vision data; sensors see only the past)