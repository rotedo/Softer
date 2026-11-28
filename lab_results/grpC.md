# grpC  (profile)
settings changed for this run: {"PUMP": {"pct": 30, "window": 288, "merge_candles": 288}}
data: ARIA=2304, CYS=2304, MMT=2304, AT=2304
data notes:
ARIAUSDT: no funding file (current month is published only after it ends)
CYSUSDT: no funding file (current month is published only after it ends)
MMTUSDT: no funding file (current month is published only after it ends)
ATUSDT: no funding file (current month is published only after it ends)

```
SIGNALS BEFORE THE MOVE on 6 pump(s). fired = first time the signal reached the level between 1 day before the bottom and the top.
already% = how much price had already risen from the bottom when it fired (small = early); left% = what was still to come to the top; false/day = firings in quiet times (no pump near), per coin-day.
signal   level | fired   already%  left%  lead(min) | false/day  | meaning
oi12         3 |   6/6        7.2   46.8      1628 |     2.52   | % open interest change in 1h
tls        1.5 |   6/6        7.3   45.0      2150 |     9.74   | taker long/short volume ratio
volx         5 |   6/6        7.5   44.6      1668 |     2.22   | this candle's volume / average of previous 4h
tb         0.6 |   6/6        7.5   44.8      2155 |     9.64   | share of taker BUY volume
volx         2 |   6/6        7.6   44.7      2032 |     6.91   | this candle's volume / average of previous 4h
trx          2 |   6/6        7.6   44.7      2008 |     5.60   | number of trades / average (4h)
oi48         2 |   6/6        8.4   44.5      2082 |     4.24   | % open interest change in 4h
vol3x        3 |   6/6        8.9   45.9      1858 |     2.72   | last 15 min volume / previous ~4h
rng          3 |   6/6        9.1   43.8      1790 |     2.62   | candle size / average candle size (4h)
ret12        3 |   6/6        9.8   45.1      1308 |     2.72   | % price change in 1h
ret3         2 |   6/6        9.9   42.3      1570 |     2.57   | % price change in 15 min
volx         3 |   6/6       10.5   43.8      1895 |     4.39   | this candle's volume / average of previous 4h
vol3x        2 |   6/6       10.5   43.8      1898 |     5.10   | last 15 min volume / previous ~4h
trx          3 |   6/6       10.5   43.8      1855 |     3.13   | number of trades / average (4h)
oi12         1 |   6/6       10.9   42.7      2095 |     7.32   | % open interest change in 1h
oi12         2 |   6/6       11.0   42.2      2070 |     4.59   | % open interest change in 1h
trx          5 |   6/6       11.1   39.8       982 |     1.21   | number of trades / average (4h)
oi48         5 |   6/6       11.5   42.4      1735 |     1.56   | % open interest change in 4h
tb        0.55 |   6/6       11.7   42.2      2182 |    10.65   | share of taker BUY volume
ret12        5 |   6/6       12.4   38.4      1235 |     0.76   | % price change in 1h
tls        1.2 |   6/6       12.5   39.3      2215 |    10.80   | taker long/short volume ratio
oi48        10 |   6/6       12.8   39.8      1222 |     0.50   | % open interest change in 4h
ret3         1 |   6/6       12.8   40.1      2168 |     6.56   | % price change in 15 min
oi12         5 |   6/6       13.4   40.0      1230 |     0.96   | % open interest change in 1h
ret3         3 |   6/6       15.0   37.7      1242 |     1.41   | % price change in 15 min
ret3         5 |   6/6       17.5   31.3       992 |     0.50   | % price change in 15 min
tls          2 |   5/6        4.8   46.6      2225 |     7.57   | taker long/short volume ratio
rng          5 |   5/6        6.7   30.4      1285 |     0.61   | candle size / average candle size (4h)
ret12       10 |   5/6       17.9   34.4       345 |     0.25   | % price change in 1h
vol3x        5 |   5/6       18.6   24.9      1325 |     1.01   | last 15 min volume / previous ~4h
tb         0.7 |   4/6        2.9   51.1      2178 |     6.31   | share of taker BUY volume
volx        10 |   3/6       17.9   34.4      1330 |     0.76   | this candle's volume / average of previous 4h
rng          8 |   1/6       17.9   34.4      1115 |     0.05   | candle size / average candle size (4h)

### ARIA: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-22 13:50, top 11-23 13:20 UTC, +58.7% in 23h30m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h   -10.7   2.2   1.9   1.5   -2.7   -7.9  0.52      -
    -12h     3.3   0.6   0.6   0.6    1.0    3.0  0.29      -
     -6h     5.4   0.6   0.7   0.8    0.5    1.7  0.74      -
     -3h     1.6   0.6   0.8   0.8   -1.4   -2.8  0.42      -
     -1h     6.7   1.6   5.2   1.4   -0.7   -0.2  0.48      -
    -30m     8.4   1.8   1.7   1.5    2.7    6.1  0.46      -
    -15m     9.8   1.3   1.5   1.1    2.4    7.1  0.53      -
     +0h     6.8  16.2  14.2  12.3    0.3    3.7  0.49      -
    +15m     5.9   1.8   2.3   2.3   -2.1    2.1  0.52      -
    +30m     6.8   0.7   1.0   0.9   -1.3    3.4  0.45      -
     +1h     9.3   0.6   0.8   0.7    2.8    8.1  0.49      -
     +3h     7.6   0.3   0.4   0.4   -4.1    1.4  0.54      -

### CYS: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-23 02:50, top 11-24 02:35 UTC, +58.5% in 23h45m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h     5.7   1.2   1.2   1.2   -0.5    1.8  0.50      -
    -12h     3.7   1.4   1.8   1.3    0.6   -0.1  0.50      -
     -6h     4.1   0.4   0.2   0.5    0.1    0.7  0.54      -
     -3h     4.0   0.6   0.7   0.9   -0.3   -0.5  0.70      -
     -1h     1.7   2.7   2.1   1.6   -1.1   -2.2  0.31      -
    -30m     1.9   0.9   0.9   0.7   -0.8   -1.8  0.15      -
    -15m     1.6   0.5   0.5   0.4   -1.0   -2.5  0.31      -
     +0h     0.8   2.0   4.0   1.6   -1.4   -3.9  0.67      -
    +15m     1.2   0.4   0.6   0.7    0.0   -2.6  0.46      -
    +30m     2.8   1.7   1.3   1.7    0.3   -2.4  0.55      -
     +1h     2.2   0.5   0.6   0.7    1.5   -2.2  0.45      -
     +3h     6.1   1.3   1.0   1.3    1.5    4.0  0.41      -

### MMT: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 3
pump: bottom 11-19 08:00, top 11-19 18:40 UTC, +65.1% in 10h40m
pump: bottom 11-23 17:55, top 11-24 08:00 UTC, +48.1% in 14h05m
pump: bottom 11-25 08:45, top 11-25 20:30 UTC, +52.7% in 11h45m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
     -3h    14.3   0.8   0.6   0.8    2.5   -3.6  0.52      -
     -1h     2.9   0.9   0.9   0.9   -7.1  -18.0  0.53      -
    -30m     1.2   0.4   0.7   0.4   -4.7  -15.8  0.53      -
    -15m     0.6   0.5   0.4   0.6    0.7   -9.6  0.56      -
     +0h     1.0   0.8   0.7   0.8    0.0   -7.7  0.45      -
    +15m     0.6   0.4   0.5   0.5   -0.5  -12.8  0.56      -
    +30m     1.1   0.4   0.4   0.4   -1.7  -14.7  0.51      -
     +1h     4.5   1.1   1.2   1.1   -1.4  -11.3  0.58      -
     +3h     2.1   0.6   0.7   0.8    1.3   -2.0  0.47      -

### AT: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-25 15:05, top 11-25 22:25 UTC, +39.1% in 7h20m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    19.0   1.6   5.2   1.6   -0.8   -3.3  0.65      -
    -12h    11.3   2.1   1.1   1.3    0.8   -0.2  0.72      -
     -6h     7.5   1.6   1.3   1.5   -0.5    0.8  0.33      -
     -3h     5.2   2.7   1.3   1.9    0.4   -1.5  0.30      -
     -1h     2.5   0.9   2.1   1.2   -3.2   -2.3  0.52      -
    -30m     2.1   0.7   1.3   1.2   -2.4   -4.8  0.57      -
    -15m     1.3   1.1   1.3   1.3   -3.2   -4.3  0.59      -
     +0h     0.6   2.9   1.8   2.6   -0.8   -3.7  0.43      -
    +15m     0.4   0.7   0.8   0.8   -1.6   -3.4  0.61      -
    +30m     1.9   1.2   0.8   1.1    0.1   -3.1  0.74      -
     +1h     1.5   1.3   0.9   1.3    1.0   -3.2  0.70      -
     +3h    24.7   1.4   3.4   1.6   10.2   25.8  0.50      -

```
(took 3s; real Binance Vision data; sensors see only the past)