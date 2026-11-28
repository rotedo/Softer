"""Cross-coin selection: of all coins that fire at the same moment, send ONLY the best one, and keep the number of alerts small.
Used by BOTH the backtest (lab) and live, with the same code. It only looks at the past (what was already sent), never at the future.
Rules (numbers in pump_config.SELECT, changed in the /pump Settings tab):
  market_wide_n: if this many coins fire in the same 5-min candle it is a whole-market move, not one coin's pump -> send nothing
  linked coins:  of the coins firing together (they usually move together) only the one with the highest strength is sent; the rest are named as 'linked'
  pause_min:     after an alert, no new alert for this many minutes (you are in a trade; also stops linked coins that fire a little later)
  max_per_day:   at most this many alerts in any 24 hours
  min_score:     the best coin must have at least this strength (see pump_strategies.strength)"""
import pump_config as cfg


class Selector:
    def __init__(self):
        self.sent = []  # times (ms) of alerts sent

    def step(self, t, cands):
        """t = time (ms) of the candle being judged, cands = [(key, strength)] firing now. -> (best or None, [others], why)"""
        s = cfg.SELECT
        if not s.get("enabled") or not cands:
            return None, [], "off" if not s.get("enabled") else "no candidates"
        if s["market_wide_n"] > 0 and len(cands) >= s["market_wide_n"]:
            return None, [], f"market-wide move ({len(cands)} coins at once)"
        self.sent = [x for x in self.sent if t - x < 86400000]
        if s["max_per_day"] > 0 and len(self.sent) >= s["max_per_day"]:
            return None, [], "daily limit reached"
        if self.sent and t - self.sent[-1] < s["pause_min"] * 60000:
            return None, [], "paused after the last alert"
        best = max(cands, key=lambda x: x[1])
        if best[1] < s["min_score"]:
            return None, [], "strength below minimum"
        self.sent.append(t)
        return best, [x for x in cands if x is not best], ""
