# stage1_profile  (profile)
settings changed for this run: {"PUMP": {"pct": 20, "window": 288}}
data: VELVET=4320, FET=2304, ONE=3168, BIGTIME=2592, CFG=2304
data notes:
VELVETUSDT: no candle file for 1 day(s): 2026-11-27
VELVETUSDT: no funding file (current month is published only after it ends)
FETUSDT: no candle file for 1 day(s): 2026-11-27
FETUSDT: no funding file (current month is published only after it ends)
BIGTIMEUSDT: no candle file for 1 day(s): 2026-11-27
BIGTIMEUSDT: no funding file (current month is published only after it ends)
CFGUSDT: no candle file for 1 day(s): 2026-11-27
CFGUSDT: no funding file (current month is published only after it ends)

```
SIGNALS BEFORE THE MOVE on 10 pump(s). fired = first time the signal reached the level between 1 day before the bottom and the top.
already% = how much price had already risen from the bottom when it fired (small = early); left% = what was still to come to the top; false/day = firings in quiet times (no pump near), per coin-day.
signal   level | fired   already%  left%  lead(min) | false/day  | meaning
oi12         1 |  10/10       2.7   37.2      2455 |     5.72   | % open interest change in 1h
oi12         2 |  10/10       3.3   37.1      2452 |     3.01   | % open interest change in 1h
oi12         3 |  10/10       3.8   34.4      1702 |     1.24   | % open interest change in 1h
oi48         2 |  10/10       3.9   39.8      2445 |     3.68   | % open interest change in 4h
ret3         1 |  10/10       4.0   37.2      2372 |     4.28   | % price change in 15 min
tb        0.55 |  10/10       4.2   39.9      2452 |    10.88   | share of taker BUY volume
tb         0.6 |  10/10       4.2   39.9      2425 |    10.38   | share of taker BUY volume
tls        1.5 |  10/10       4.7   39.3      2420 |    10.41   | taker long/short volume ratio
oi48         5 |  10/10       5.0   42.4      2330 |     1.14   | % open interest change in 4h
tls        1.2 |  10/10       5.0   38.7      2452 |    10.91   | taker long/short volume ratio
volx         2 |  10/10       5.6   32.7      2415 |     6.89   | this candle's volume / average of previous 4h
trx          2 |  10/10       5.6   33.4      2330 |     5.39   | number of trades / average (4h)
ret3         2 |  10/10       5.7   35.9      1990 |     1.00   | % price change in 15 min
volx         3 |  10/10       5.8   36.4      2290 |     4.75   | this candle's volume / average of previous 4h
volx         5 |  10/10       5.8   34.8      2225 |     2.58   | this candle's volume / average of previous 4h
rng          3 |  10/10       5.8   32.5      2192 |     2.01   | candle size / average candle size (4h)
trx          3 |  10/10       5.8   35.8      2290 |     2.81   | number of trades / average (4h)
ret12        3 |  10/10       6.1   34.6      1625 |     1.04   | % price change in 1h
vol3x        2 |  10/10       6.8   32.2      2455 |     4.55   | last 15 min volume / previous ~4h
vol3x        3 |  10/10       7.4   35.8      2455 |     2.78   | last 15 min volume / previous ~4h
rng          5 |  10/10       7.4   25.1      1110 |     0.40   | candle size / average candle size (4h)
oi12         5 |  10/10       7.7   36.0      1590 |     0.40   | % open interest change in 1h
oi48        10 |  10/10       8.1   33.9      1350 |     0.17   | % open interest change in 4h
ret12        5 |  10/10      10.4   31.5      1482 |     0.33   | % price change in 1h
ret3         3 |  10/10      14.9   29.3      1445 |     0.23   | % price change in 15 min
ret3         5 |  10/10      16.5   19.3       728 |     0.03   | % price change in 15 min
tb         0.7 |   9/10       3.2   43.3      2565 |     8.37   | share of taker BUY volume
tls          2 |   9/10       3.2   41.9      2560 |     9.17   | taker long/short volume ratio
vol3x        5 |   9/10       3.9   41.0      1895 |     0.87   | last 15 min volume / previous ~4h
trx          5 |   9/10       7.2   29.1      2435 |     0.97   | number of trades / average (4h)
volx        10 |   8/10       5.6   28.3      1738 |     0.54   | this candle's volume / average of previous 4h
ret12       10 |   8/10      19.4   22.2       778 |     0.00   | % price change in 1h
rng          8 |   6/10      11.4   21.0      1070 |     0.13   | candle size / average candle size (4h)

### VELVET: 4320 candles 11-12 00:00 to 11-26 23:55 UTC; pumps found: 4
pump: bottom 11-12 15:45, top 11-13 15:40 UTC, +20.7% in 23h55m
pump: bottom 11-17 19:40, top 11-19 10:55 UTC, +54.1% in 39h15m
pump: bottom 11-19 11:50, top 11-19 14:50 UTC, +20.9% in 3h00m
pump: bottom 11-21 16:40, top 11-23 16:20 UTC, +45.4% in 47h40m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    -2.7   0.2   0.2   0.2   -0.2    0.5  0.77      -
    -12h    -3.2   0.8   0.9   1.0   -0.5    0.6  0.35      -
     -6h    -2.0   0.6   0.7   0.9   -0.1    1.7  0.19      -
     -3h    -0.9   0.7   0.9   0.8    0.4    0.3  0.57      -
     -1h     0.7   1.5   1.1   0.9    1.9    3.8  0.34      -
    -30m     1.1   1.0   0.8   1.0    1.5    3.8  0.75      -
    -15m     0.4   1.1   0.7   0.7    1.9    4.1  0.23      -
     +0h     0.3   0.3   0.4   0.5   -0.6    2.7  0.47      -
    +15m     1.2   0.6   0.5   0.4    1.1    5.1  0.31      -
    +30m     0.8   0.2   0.4   0.4    0.4    1.7  0.59      -
     +1h     1.5   0.7   2.3   0.9    1.9    4.2  0.31      -
     +3h     2.4   1.0   0.7   1.0    0.7    1.9  0.37      -

### FET: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 0
no pump matching the label (+20.0% within 288 candles) in this window


### ONE: 3168 candles 10-31 00:00 to 11-10 23:55 UTC; pumps found: 3
pump: bottom 11-05 15:50, top 11-07 16:40 UTC, +141.5% in 48h50m
pump: bottom 11-08 04:30, top 11-08 08:50 UTC, +25.1% in 4h20m
pump: bottom 11-10 05:20, top 11-10 10:35 UTC, +53.5% in 5h15m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    12.2   1.4   1.4   1.4    1.9    3.9  0.44  0.005
    -12h     8.8   0.2   0.5   0.5    0.1   -0.7  0.68  0.005
     -6h    11.2   2.7   1.5   2.2    1.6    4.6  0.34  0.005
     -3h     7.8   0.6   1.2   0.8   -1.8   -2.1  0.73  0.005
     -1h     6.9   1.8   3.0   2.3   -1.5   -1.2  0.62  0.005
    -30m     1.8   7.3   5.7   6.3   -7.9   -7.7  0.45  0.005
    -15m     3.2   1.7   2.4   1.8   -5.5   -6.6  0.64  0.005
     +0h     1.0   4.6   2.3   4.2   -6.2   -7.9  0.42  0.005
    +15m     2.1   1.5   1.7   1.5   -2.4   -6.2  0.37  0.005
    +30m     4.6   1.5   1.4   1.6    3.1   -3.0  0.40  0.005
     +1h     3.8   0.5   0.5   0.6    3.1   -3.3  0.46  0.005
     +3h     3.9   0.2   0.2   0.2    0.8   -2.9  0.65  0.005

### BIGTIME: 2592 candles 11-18 00:00 to 11-26 23:55 UTC; pumps found: 2
pump: bottom 11-24 03:05, top 11-25 06:30 UTC, +89.5% in 27h25m
pump: bottom 11-25 06:45, top 11-25 21:25 UTC, +22.5% in 14h40m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h     2.6   0.4   0.9   0.7    1.2    0.2  0.69      -
    -12h     7.9   1.0   1.3   1.8    2.1    7.3  0.25      -
     -6h     3.0   0.7   1.4   1.0   -0.8   -3.8  0.42      -
     -3h     1.3   1.8   1.8   1.5   -0.0   -2.7  0.50      -
     -1h     2.6   1.4   2.7   1.7   -1.1   -2.2  0.71      -
    -30m     2.2   0.4   0.5   0.7   -1.0   -0.5  0.36      -
    -15m     1.5   2.9   1.4   2.2   -1.6   -0.7  0.54      -
     +0h     0.7   5.4   2.3   3.6   -1.5   -2.6  0.48      -
    +15m     1.2   0.9   0.9   1.2   -2.3   -2.9  0.85      -
    +30m     2.0   0.4   0.5   0.9   -1.6   -2.2  0.50      -
     +1h     2.9   0.5   0.8   0.9    1.2   -1.4  0.69      -
     +3h     6.2   0.3   1.0   0.6    2.6    4.3  0.37      -

### CFG: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-25 01:40, top 11-25 20:50 UTC, +31.9% in 19h10m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    10.4   0.4   4.5   0.7    1.9    1.0  0.59      -
    -12h     7.2   0.7   1.4   0.8   -0.1   -2.4  0.20      -
     -6h     2.5   1.9   1.3   0.9   -2.1   -4.4  0.86      -
     -3h     2.4   4.4   1.9   1.6    0.6   -3.9  0.65      -
     -1h     1.4   0.6   2.0   0.9   -3.2   -4.6  0.48      -
    -30m     1.9   0.4   0.6   0.7   -2.3   -3.1  0.58      -
    -15m     1.2   0.4   0.4   0.7   -2.1   -3.3  0.62      -
     +0h     0.4   0.9   0.7   1.1    0.2   -2.5  0.49      -
    +15m     1.4   0.2   0.4   0.5    1.2   -1.1  0.42      -
    +30m     1.3   0.2   0.5   0.4    0.3   -1.4  0.45      -
     +1h     1.6   0.2   0.3   0.3    1.3   -1.7  0.35      -
     +3h     3.6   0.3   0.5   0.4   -1.3    4.7  0.59      -

```
(took 10s; real Binance Vision data; sensors see only the past)