# stage2_B_tight  (test)
settings changed for this run: {"PUMP": {"pct": 20, "window": 288}, "EVAL": {"horizon": 144}, "STRATEGY_CONFIG": {"volume_spike": {"volume_multiplier": 5}, "price_momentum": {"min_return_pct": 3}}}
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
volume_spike       112  33.9 |    15     12   80.0    11 |    2520.8   9.2   -8.0 | 1.49
price_momentum      62  50.0 |    15     13   86.7    10 |    2274.6  14.8  -10.5 | 0.83
open_interest      155  54.8 |    15     15  100.0    13 |    2220.7  16.5   -8.7 | 2.07
funding_rate         0     - |    15      0    0.0     0 |         -     -      - | 0.0
my_example_big_      0     - |    15      0    0.0     0 |         -     -      - | 0.0
combined            57  47.4 |    15     12   80.0     8 |    2460.4  14.7  -10.7 | 0.76
catch% = real pumps we alerted on in time. hit% = alerts followed by the hit move; the rest are false alerts.

PER COIN (combined view; 'all' = any single sensor):
BLUR     pump 11-22 07:00->11-26 01:05 +65.6%: combined at 11-22 15:30 (already +7.4%, lead 4895 min); earliest single: volume_spike at 11-22 15:30 (already +7.4%)
EVAA     pump 11-08 21:55->11-09 12:35 +22.8%: combined: MISSED; earliest single: price_momentum at 11-08 22:40 (already +10.2%)
EVAA     pump 11-14 10:05->11-17 09:40 +307.1%: combined at 11-14 14:10 (already +20.7%, lead 4050 min); earliest single: volume_spike at 11-14 13:40 (already +7.8%)
EVAA     pump 11-18 01:05->11-21 08:50 +118.2%: combined at 11-18 12:15 (already +20.6%, lead 4115 min); earliest single: open_interest at 11-18 04:55 (already +13.7%)
EVAA     pump 11-22 09:40->11-22 13:25 +49.1%: combined at 11-22 10:25 (already +27.8%, lead 180 min); earliest single: open_interest at 11-22 10:20 (already +25.5%)
EVAA     pump 11-22 18:10->11-23 12:30 +58.2%: combined at 11-23 03:50 (already +25.5%, lead 520 min); earliest single: open_interest at 11-22 18:45 (already +12.3%)
EVAA     pump 11-24 11:40->11-26 13:50 +77.3%: combined at 11-24 14:25 (already +42.2%, lead 2845 min); earliest single: open_interest at 11-24 13:20 (already +18.8%)
MMT      pump 11-16 13:20->11-19 18:40 +215.7%: combined at 11-16 15:15 (already +10.3%, lead 4525 min); earliest single: volume_spike at 11-16 14:30 (already +2.2%)
MMT      pump 11-22 04:40->11-22 10:25 +24.5%: combined at 11-22 09:45 (already +23.1%, lead 40 min); earliest single: open_interest at 11-22 06:40 (already +6.7%)
MMT      pump 11-22 11:45->11-22 14:40 +20.6%: combined: MISSED; earliest single: open_interest at 11-22 12:40 (already +12.3%)
MMT      pump 11-23 17:55->11-24 08:00 +48.1%: combined: MISSED; earliest single: open_interest at 11-23 23:35 (already +12.6%)
MMT      pump 11-24 14:15->11-25 20:30 +52.9%: combined at 11-25 09:50 (already +12.3%, lead 640 min); earliest single: open_interest at 11-24 16:05 (already +9.2%)
MMT      pump 11-26 16:40->11-26 18:15 +21.9%: combined at 11-26 18:15 (already +21.2%, lead 0 min); earliest single: volume_spike at 11-26 16:45 (already +7.6%)
LISTA    pump 11-22 03:00->11-25 16:20 +86.7%: combined at 11-22 18:30 (already +12.9%, lead 4190 min); earliest single: volume_spike at 11-22 08:20 (already +2.7%)
ICNT     pump 11-17 00:20->11-20 07:35 +111.1%: combined at 11-17 20:50 (already +11.1%, lead 3525 min); earliest single: volume_spike at 11-17 04:20 (already +4.8%)
```
(took 6s; real Binance Vision data; sensors see only the past)