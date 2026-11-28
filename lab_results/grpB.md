# grpB  (profile)
settings changed for this run: {"PUMP": {"pct": 30, "window": 288, "merge_candles": 288}}
data: BIGTIME=2304, SSV=2304, PROM=2304, ELSA=2304, INIT=2304
data notes:
BIGTIMEUSDT: no funding file (current month is published only after it ends)
SSVUSDT: no funding file (current month is published only after it ends)
PROMUSDT: no funding file (current month is published only after it ends)
ELSAUSDT: no funding file (current month is published only after it ends)
INITUSDT: no funding file (current month is published only after it ends)

```
SIGNALS BEFORE THE MOVE on 7 pump(s). fired = first time the signal reached the level between 1 day before the bottom and the top.
already% = how much price had already risen from the bottom when it fired (small = early); left% = what was still to come to the top; false/day = firings in quiet times (no pump near), per coin-day.
signal   level | fired   already%  left%  lead(min) | false/day  | meaning
trx          5 |   7/7        4.3   65.8      2220 |     1.17   | number of trades / average (4h)
tls          2 |   7/7        4.3   74.5      2795 |     7.49   | taker long/short volume ratio
tb         0.7 |   7/7        4.7   70.4      2665 |     6.32   | share of taker BUY volume
vol3x        5 |   7/7        4.7   54.6      2210 |     1.17   | last 15 min volume / previous ~4h
rng          3 |   7/7        4.7   64.2      2205 |     2.66   | candle size / average candle size (4h)
trx          3 |   7/7        4.7   68.9      2435 |     3.16   | number of trades / average (4h)
volx         5 |   7/7        5.6   63.7      2435 |     2.80   | this candle's volume / average of previous 4h
vol3x        3 |   7/7        5.6   63.7      2435 |     2.98   | last 15 min volume / previous ~4h
ret12        3 |   7/7        5.7   64.3      2260 |     1.62   | % price change in 1h
volx         2 |   7/7        6.7   67.1      2700 |     6.63   | this candle's volume / average of previous 4h
volx         3 |   7/7        6.7   68.9      2700 |     4.87   | this candle's volume / average of previous 4h
vol3x        2 |   7/7        6.7   68.9      2700 |     4.38   | last 15 min volume / previous ~4h
trx          2 |   7/7        6.7   67.8      2550 |     5.64   | number of trades / average (4h)
ret3         2 |   7/7        6.7   70.4      2340 |     1.53   | % price change in 15 min
ret12        5 |   7/7        7.6   65.6      1545 |     0.36   | % price change in 1h
oi12         2 |   7/7        8.0   58.9      2430 |     3.34   | % open interest change in 1h
tb        0.55 |   7/7        8.2   64.7      2800 |    10.70   | share of taker BUY volume
tb         0.6 |   7/7        8.2   64.9      2800 |     9.97   | share of taker BUY volume
oi12         1 |   7/7        8.3   58.9      2795 |     5.60   | % open interest change in 1h
oi48         2 |   7/7        8.3   58.9      2525 |     3.39   | % open interest change in 4h
tls        1.2 |   7/7        8.3   64.2      2795 |    10.74   | taker long/short volume ratio
tls        1.5 |   7/7        8.3   63.9      2795 |     9.97   | taker long/short volume ratio
oi12         3 |   7/7        8.5   63.1      2005 |     1.72   | % open interest change in 1h
ret3         1 |   7/7        8.8   58.9      2520 |     4.87   | % price change in 15 min
oi48         5 |   7/7        8.9   58.9      2255 |     1.49   | % open interest change in 4h
volx        10 |   7/7        9.8   52.9      1425 |     0.81   | this candle's volume / average of previous 4h
ret3         3 |   7/7        9.8   62.9      1555 |     0.50   | % price change in 15 min
oi12         5 |   7/7        9.8   58.9      1540 |     0.41   | % open interest change in 1h
oi48        10 |   7/7       12.5   58.9      1410 |     0.45   | % open interest change in 4h
ret3         5 |   7/7       17.6   46.8       935 |     0.23   | % price change in 15 min
ret12       10 |   6/7       22.5   44.0       840 |     0.09   | % price change in 1h
rng          5 |   4/7        9.4   64.8      1978 |     0.95   | candle size / average candle size (4h)
rng          8 |   3/7       24.0   43.7      1695 |     0.32   | candle size / average candle size (4h)

### BIGTIME: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-24 04:05, top 11-25 06:30 UTC, +85.0% in 26h25m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h     1.7   0.3   0.6   0.4    0.7    1.0  0.45      -
    -12h     4.9   0.8   0.6   1.2   -0.8    6.8  0.71      -
     -6h    -0.8   1.5   1.5   1.7   -0.9   -3.3  0.52      -
     -3h    -0.7   0.4   0.4   0.7   -0.1   -2.0  0.75      -
     -1h    -1.7   5.4   2.3   3.6   -1.5   -2.6  0.48      -
    -30m    -0.5   0.4   0.5   0.9   -1.6   -2.2  0.50      -
    -15m    -0.5   0.4   0.7   0.7   -0.6   -1.4  0.48      -
     +0h     0.4   0.5   0.8   0.9    1.2   -1.4  0.69      -
    +15m     0.9   0.3   0.4   0.6    2.1   -1.2  0.25      -
    +30m     1.5   1.0   0.6   1.5    1.5   -0.6  0.76      -
     +1h     2.3   0.9   1.5   1.4    1.9    0.5  0.57      -
     +3h     3.3   0.6   0.7   0.8   10.3   16.7  0.57      -

### SSV: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-25 01:30, top 11-26 22:05 UTC, +95.2% in 44h35m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h     4.7   0.7   0.7   1.0    0.6    0.5  0.43      -
    -12h     2.0   0.7   0.6   1.1   -0.7   -2.2  0.75      -
     -6h     1.7   0.5   0.3   0.9   -0.0    0.6  0.29      -
     -3h     1.4   0.2   0.7   0.6    0.5   -0.5  0.91      -
     -1h     0.4   2.1   1.6   1.5   -0.4   -0.4  0.54      -
    -30m     0.1   1.4   0.7   1.3   -0.5   -0.5  0.41      -
    -15m     0.5   0.6   1.6   0.8   -0.1   -0.1  0.49      -
     +0h     0.1   2.3   1.2   2.0   -0.0   -0.8  0.51      -
    +15m     0.9  10.1   4.5   7.8   -0.5   -0.4  0.80      -
    +30m     1.2   5.6   6.0   5.2   -0.5   -0.6  0.76      -
     +1h     1.6   1.7   1.3   0.9   -1.9   -3.2  0.56      -
     +3h     2.6   0.5   0.5   0.5   -1.6   -1.5  0.52      -

### PROM: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-22 16:35, top 11-23 15:15 UTC, +84.7% in 22h40m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h    32.1   0.4   0.7   0.6    0.7    1.8  0.67      -
    -12h    30.8   0.5   0.7   0.6    1.4    0.5  0.35      -
     -6h    34.4   0.4   0.5   0.7    0.4    3.2  0.54      -
     -3h    25.8   1.3   2.3   1.7    5.2   -9.1  0.45      -
     -1h    35.6   1.0   1.3   1.4    1.4    3.6  0.60      -
    -30m    23.0   2.1   3.8   2.0  -10.5    6.1  0.50      -
    -15m    16.3   2.7   3.9   2.5  -10.8    2.4  0.50      -
     +0h     5.9   6.2   4.2   5.2  -15.5   -3.7  0.44      -
    +15m    22.6   2.0   3.4   2.3  -15.2    0.5  0.48      -
    +30m    24.7   1.3   2.8   1.4    1.2    7.3  0.55      -
     +1h    21.4   0.4   0.5   0.4    9.5    0.3  0.40      -
     +3h    14.4   0.2   0.8   0.4   -1.3  -13.1  0.47      -

### ELSA: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 3
pump: bottom 11-19 20:05, top 11-20 19:50 UTC, +32.0% in 23h45m
pump: bottom 11-21 19:55, top 11-23 14:05 UTC, +72.9% in 42h10m
pump: bottom 11-25 11:30, top 11-26 04:25 UTC, +67.9% in 16h55m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h     8.9   0.9   1.2   0.9    6.1   28.3  0.50      -
    -12h    -1.8   0.3   0.3   0.4   -0.3    1.7  0.47      -
     -6h     0.2   0.4   0.4   0.4   -0.9   -2.6  0.34      -
     -3h     1.1   0.3   0.7   0.4    0.2   -1.5  0.59      -
     -1h     0.1   0.7   0.6   0.6   -0.5    0.5  0.25      -
    -30m     0.3   0.3   0.4   0.4   -0.9    1.8  0.37      -
    -15m     0.1   0.5   0.5   0.5    0.2    1.1  0.55      -
     +0h     0.1   0.4   0.4   0.7   -0.1    0.4  0.53      -
    +15m     0.9   0.2   0.5   0.4    0.7    2.8  0.47      -
    +30m     0.9   0.3   0.3   0.4    0.3    1.0  0.38      -
     +1h     1.4   0.5   0.4   0.6    1.0    1.1  0.63      -
     +3h     2.5   0.5   1.0   0.5    1.2    3.1  0.32      -

### INIT: 2304 candles 11-19 00:00 to 11-26 23:55 UTC; pumps found: 1
pump: bottom 11-26 03:00, top 11-26 21:05 UTC, +81.8% in 18h05m
timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):
  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%
    -24h     7.1   1.0   1.0   1.3   -1.2    3.2  0.49      -
    -12h     5.1   1.5   1.0   2.0    0.8    3.4  0.52      -
     -6h     3.6   1.3   1.1   2.0   -1.7   -2.8  0.56      -
     -3h     2.5   2.1   1.3   1.6   -0.1   -3.3  0.44      -
     -1h     2.1   2.7   2.8   5.1   -1.9   -2.7  0.61      -
    -30m     1.9   1.5   1.2   1.3   -2.3   -3.4  0.62      -
    -15m     1.8   0.6   0.7   0.8   -1.6   -3.0  0.47      -
     +0h     0.3   5.9   2.7   3.8   -1.2   -3.5  0.45      -
    +15m     0.7   1.0   2.1   0.9   -0.5   -3.2  0.46      -
    +30m     1.0   0.8   1.1   0.9    0.0   -2.8  0.51      -
     +1h     2.0   1.2   1.5   1.1    1.1   -2.3  0.55      -
     +3h     1.8   1.2   0.8   1.8   -1.5   -2.1  0.50      -

```
(took 4s; real Binance Vision data; sensors see only the past)