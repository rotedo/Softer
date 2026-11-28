# stage2_C_six_sensors_min3  (test)
settings changed for this run: {"PUMP": {"pct": 20, "window": 288}, "EVAL": {"horizon": 144}, "STRATEGY_CONFIG": {"volume_spike": {"volume_multiplier": 4}, "price_momentum": {"min_return_pct": 3}, "range_expansion": {"enabled": true, "multiplier": 5}, "trades_spike": {"enabled": true, "multiplier": 4}}, "MIN_STRATEGIES": 3}
data: BLUR=3744, EVAA=5472, MMT=4608, LISTA=3168, ICNT=4608
data notes:
BLURUSDT: no funding file (current month is published only after it ends)
EVAAUSDT: no funding file (current month is published only after it ends)
MMTUSDT: no funding file (current month is published only after it ends)
LISTAUSDT: no funding file (current month is published only after it ends)
ICNTUSDT: no funding file (current month is published only after it ends)

```
TEST on 5 coins; pump = +20.0% in 1440 min; hit = +10.0% in 12h; need 3+ sensors for 'combined'
view            alerts hit% | pumps caught catch% early | lead(min) best% worst% | alerts/coin-day
volume_spike       162  34.0 |    15     13   86.7    12 |    2468.5   9.6   -7.5 | 2.16
price_momentum      62  50.0 |    15     13   86.7    10 |    2274.6  14.8  -10.5 | 0.83
open_interest      155  54.8 |    15     15  100.0    13 |    2220.7  16.5   -8.7 | 2.07
funding_rate         0     - |    15      0    0.0     0 |         -     -      - | 0.0
trades_spike        85  42.4 |    15     12   80.0    11 |    2618.3  11.0   -8.8 | 1.13
range_expansion     38  36.8 |    15      8   53.3     8 |    2768.1  11.8   -9.3 | 0.51
my_example_big_      0     - |    15      0    0.0     0 |         -     -      - | 0.0
combined            52  38.5 |    15     11   73.3     9 |    2469.1  12.5  -10.2 | 0.69
catch% = real pumps we alerted on in time. hit% = alerts followed by the hit move; the rest are false alerts.

PER COIN (combined view; 'all' = any single sensor):
BLUR     pump 11-22 07:00->11-26 01:05 +65.6%: combined at 11-22 16:05 (already +9.9%, lead 4860 min); earliest single: volume_spike at 11-22 15:30 (already +7.4%)
EVAA     pump 11-08 21:55->11-09 12:35 +22.8%: combined: MISSED; earliest single: price_momentum at 11-08 22:40 (already +10.2%)
EVAA     pump 11-14 10:05->11-17 09:40 +307.1%: combined at 11-14 13:40 (already +7.8%, lead 4080 min); earliest single: volume_spike at 11-14 13:40 (already +7.8%)
EVAA     pump 11-18 01:05->11-21 08:50 +118.2%: combined at 11-19 06:40 (already +40.7%, lead 3010 min); earliest single: trades_spike at 11-18 01:05 (already +2.6%)
EVAA     pump 11-22 09:40->11-22 13:25 +49.1%: combined: MISSED; earliest single: open_interest at 11-22 10:20 (already +25.5%)
EVAA     pump 11-22 18:10->11-23 12:30 +58.2%: combined at 11-23 02:05 (already +19.8%, lead 625 min); earliest single: open_interest at 11-22 18:45 (already +12.3%)
EVAA     pump 11-24 11:40->11-26 13:50 +77.3%: combined at 11-25 03:00 (already +14.2%, lead 2090 min); earliest single: open_interest at 11-24 13:20 (already +18.8%)
MMT      pump 11-16 13:20->11-19 18:40 +215.7%: combined at 11-16 15:10 (already +5.5%, lead 4530 min); earliest single: volume_spike at 11-16 14:30 (already +2.2%)
MMT      pump 11-22 04:40->11-22 10:25 +24.5%: combined: MISSED; earliest single: volume_spike at 11-22 06:35 (already +8.5%)
MMT      pump 11-22 11:45->11-22 14:40 +20.6%: combined: MISSED; earliest single: open_interest at 11-22 12:40 (already +12.3%)
MMT      pump 11-23 17:55->11-24 08:00 +48.1%: combined at 11-24 05:35 (already +38.6%, lead 145 min); earliest single: open_interest at 11-23 23:35 (already +12.6%)
MMT      pump 11-24 14:15->11-25 20:30 +52.9%: combined at 11-25 20:20 (already +50.8%, lead 10 min); earliest single: open_interest at 11-24 16:05 (already +9.2%)
MMT      pump 11-26 16:40->11-26 18:15 +21.9%: combined at 11-26 16:45 (already +7.6%, lead 90 min); earliest single: volume_spike at 11-26 16:45 (already +7.6%)
LISTA    pump 11-22 03:00->11-25 16:20 +86.7%: combined at 11-22 18:30 (already +12.9%, lead 4190 min); earliest single: volume_spike at 11-22 04:10 (already +0.7%)
ICNT     pump 11-17 00:20->11-20 07:35 +111.1%: combined at 11-17 20:45 (already +9.8%, lead 3530 min); earliest single: volume_spike at 11-17 01:35 (already +2.5%)
```
(took 9s; real Binance Vision data; sensors see only the past)