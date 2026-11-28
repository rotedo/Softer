# grpA  (profile)
settings changed for this run: {"PUMP": {"pct": 30, "window": 288, "merge_candles": 288}}
data: ACE=2304, BULLA=2304, EVAA=2304, AIOT=2304, MANTRA=2304
data notes:
ACEUSDT: no funding file (current month is published only after it ends)
BULLAUSDT: no funding file (current month is published only after it ends)
EVAAUSDT: no funding file (current month is published only after it ends)
AIOTUSDT: no funding file (current month is published only after it ends)
MANTRAUSDT: no funding file (current month is published only after it ends)

```
SIGNALS BEFORE THE MOVE on 8 pump(s). fired = first time the signal reached the level between 1 day before the bottom and the top.
already% = how much price had already risen from the bottom when it fired (small = early); left% = what was still to come to the top; false/day = firings in quiet times (no pump near), per coin-day.
signal   level | fired   already%  left%  lead(min) | false/day  | meaning
rng          3 |   8/8       10.3   46.3      3012 |     2.41   | candle size / average candle size (4h)
volx         5 |   8/8       11.0   44.2      2882 |     2.52   | this candle's volume / average of previous 4h
tls          2 |   8/8       11.3   46.1      3068 |     6.73   | taker long/short volume ratio
vol3x        3 |   8/8       11.4   43.4      3008 |     2.63   | last 15 min volume / previous ~4h
tb         0.7 |   8/8       11.4   46.0      3072 |     5.53   | share of taker BUY volume
trx          3 |   8/8       12.0   43.9      3018 |     3.06   | number of trades / average (4h)
trx          5 |   8/8       12.9   50.7      2520 |     1.26   | number of trades / average (4h)
oi12         5 |   8/8       13.0   42.4      2588 |     1.20   | % open interest change in 1h
volx         2 |   8/8       13.1   43.7      3045 |     6.40   | this candle's volume / average of previous 4h
volx         3 |   8/8       13.1   42.3      3018 |     4.38   | this candle's volume / average of previous 4h
vol3x        2 |   8/8       13.5   41.8      3012 |     4.49   | last 15 min volume / previous ~4h
tls        1.5 |   8/8       14.1   43.9      3080 |     9.25   | taker long/short volume ratio
tb         0.6 |   8/8       14.2   43.7      3085 |     9.25   | share of taker BUY volume
oi48        10 |   8/8       15.3   39.8      2025 |     0.82   | % open interest change in 4h
trx          2 |   8/8       16.7   42.3      3045 |     5.47   | number of trades / average (4h)
vol3x        5 |   8/8       17.5   41.8      2482 |     1.09   | last 15 min volume / previous ~4h
ret3         3 |   8/8       17.5   75.5      2280 |     1.31   | % price change in 15 min
oi12         3 |   8/8       19.4   45.4      2840 |     2.74   | % open interest change in 1h
ret12        3 |   8/8       19.5   51.7      2580 |     2.41   | % price change in 1h
ret12        5 |   8/8       19.7   49.2      2042 |     1.04   | % price change in 1h
oi48         5 |   8/8       20.9   42.4      2822 |     2.02   | % open interest change in 4h
ret3         1 |   8/8       21.2   40.0      3198 |     5.75   | % price change in 15 min
oi12         1 |   8/8       21.3   41.8      3190 |     6.84   | % open interest change in 1h
ret3         2 |   8/8       21.4   68.0      2878 |     2.46   | % price change in 15 min
oi48         2 |   8/8       22.0   40.9      3078 |     4.27   | % open interest change in 4h
oi12         2 |   8/8       22.6   40.1      3102 |     3.89   | % open interest change in 1h
tls        1.2 |   8/8       23.5   36.5      3225 |    10.62   | taker long/short volume ratio
ret12       10 |   8/8       23.6   47.3      1415 |     0.22   | % price change in 1h
tb        0.55 |   8/8       23.9   37.1      3230 |    10.40   | share of taker BUY volume
ret3         5 |   8/8       28.4   60.8      1512 |     0.49   | % price change in 15 min
rng          5 |   6/8       46.0   23.7      1542 |     0.93   | candle size / average candle size (4h)
volx        10 |   3/8       11.4   32.0      1455 |     0.93   | this candle's volume / average of previous 4h
rng          8 |   3/8       22.5   32.0      1455 |     0.38   | candle size / average candle size (4h)

### ACE: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-22 18:30, top 11-23 18:10 UTC, +175.3% in 23h40m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h   167.5   0.8   1.0   0.7    1.1    2.0  0.82      -
    -12h   163.7   0.6   0.6   0.8    0.9   -1.6  0.15      -
     -6h   170.6   0.7   1.2   0.9    0.6    4.4  0.45      -
     -3h   170.8   0.4   0.6   0.9    0.7    2.3  0.37      -
     -1h   170.4   0.5   0.6   0.7   -0.1    1.0  0.45      -
    -30m   127.2  60.5 416.8  67.8   13.5   14.0  0.49      -
    -15m    76.6  16.1  37.1  18.9   22.9   23.0  0.48      -
     +0h    18.6   6.7  14.5   7.2   84.3   85.4  0.47      -
    +15m    81.9   3.0   7.2   3.0  154.4  155.0  0.52      -
    +30m    96.0   2.4   2.4   2.3  134.8  168.2  0.54      -
     +1h    72.6   0.9   1.0   1.2   38.4  154.8  0.48      -
     +3h   101.2   0.2   0.2   0.3   -0.5  190.0  0.51      -

### BULLA: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 2
pump: bottom 11-22 03:30, top 11-23 10:55 UTC, +101.5% in 31h25m
pump: bottom 11-24 11:00, top 11-26 16:45 UTC, +211.8% in 53h45m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    28.1   0.8   1.1   0.8    7.7   39.4  0.51      -
    -12h     8.6   0.7   0.4   0.8    0.1    0.0  0.67      -
     -6h     6.8   0.3   0.3   0.4    0.9   -0.1  0.48      -
     -3h    15.3   1.1   1.0   1.2   -0.9   10.6  0.47      -
     -1h    14.4   2.8   1.3   2.3   -4.1   -0.3  0.47      -
    -30m    10.6   0.8   0.7   0.8   -7.3   -6.9  0.36      -
    -15m     9.9   0.8   0.9   0.9   -5.2   -7.0  0.43      -
     +0h     6.3   5.0   3.5   4.6  -10.5  -14.3  0.47      -
    +15m     5.9   0.7   1.0   0.8  -11.1  -15.0  0.55      -
    +30m     8.2   0.6   1.0   0.6   -6.3  -12.6  0.56      -
     +1h     8.2   0.5   0.4   0.7    3.4  -10.5  0.46      -
     +3h    13.4   1.5   0.8   1.6    0.7   -5.8  0.58      -

### EVAA: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 2
pump: bottom 11-22 09:40, top 11-22 13:25 UTC, +49.1% in 3h45m
pump: bottom 11-24 11:40, top 11-26 13:50 UTC, +77.3% in 50h10m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    81.1   0.5   0.4   0.5    2.6    8.7  0.46      -
    -12h    60.9   1.3   1.1   1.2    1.3   -0.3  0.59      -
     -6h    33.8   0.8   1.4   1.0    0.8   -9.8  0.52      -
     -3h    36.0   0.6   0.5   0.6   -0.2    2.4  0.48      -
     -1h    31.1   2.2   2.1   2.5   -3.0   -2.3  0.49      -
    -30m    19.2   3.8   2.0   3.1    0.8   -1.1  0.44      -
    -15m    14.4   4.1   4.8   4.1   -7.1   -9.3  0.46      -
     +0h     2.2   3.5   3.8   3.2  -18.9  -21.6  0.50      -
    +15m     6.3   1.2   2.8   1.7  -18.1  -18.3  0.53      -
    +30m     8.9   0.8   1.3   1.0  -12.8  -14.9  0.53      -
     +1h     4.5   0.4   0.6   0.6    3.0  -19.1  0.55      -
     +3h    34.2   1.6   2.2   1.4   13.9    7.8  0.50      -

### AIOT: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 2
pump: bottom 11-23 01:45, top 11-24 10:40 UTC, +72.9% in 32h55m
pump: bottom 11-25 13:30, top 11-26 18:05 UTC, +47.0% in 28h35m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    20.0   0.6   0.5   0.7   -0.6   -1.1  0.62      -
    -12h    11.7   0.9   0.8   0.9    0.0   -1.4  0.31      -
     -6h     3.9   0.8   1.2   0.8   -1.2   -0.5  0.55      -
     -3h     3.8   0.4   0.8   0.7   -0.9   -0.9  0.34      -
     -1h     3.2   1.1   0.9   0.8   -2.0   -1.0  0.25      -
    -30m     1.4   1.0   1.9   1.1   -1.0   -1.5  0.46      -
    -15m     1.1   1.8   1.4   1.9   -1.3   -2.0  0.30      -
     +0h     0.3   1.6   1.2   1.5   -1.7   -2.9  0.32      -
    +15m     1.1   2.2   3.2   2.4    1.1    0.0  0.44      -
    +30m     4.3   3.5   2.2   2.8    2.3    1.9  0.59      -
     +1h     4.6   0.7   0.7   1.0    4.0    1.9  0.52      -
     +3h     3.0   0.5   0.6   0.4   -2.8    0.3  0.66      -

### MANTRA: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-25 00:10, top 11-25 22:15 UTC, +127.1% in 22h05m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h     8.4   0.4   1.7   0.8    0.5   -0.1  0.52      -
    -12h     3.5   0.4   1.5   0.5    0.4    3.1  0.72      -
     -6h     2.6   0.8   0.5   0.6    0.1   -0.2  0.14      -
     -3h     1.4   0.3   0.7   0.7    1.0    2.8  0.54      -
     -1h     1.2   5.0   2.2   2.9   -0.5    1.9  0.28      -
    -30m     0.9   0.7   0.7   1.0   -1.0    0.5  0.53      -
    -15m     1.1   0.2   0.3   0.5   -0.7    0.7  0.81      -
     +0h     0.5   2.4   1.8   3.4   -1.0    0.1  0.27      -
    +15m     0.5   1.2   1.3   1.3   -0.4    0.8  0.61      -
    +30m     0.9   1.2   2.3   1.1    0.7    0.3  0.29      -
     +1h     1.2   1.0   1.3   1.4    0.6   -0.4  0.62      -
     +3h     6.4   4.4   5.5   3.1    7.1   10.3  0.50      -

```
(took 4s; real Binance Vision data; sensors see only the past)