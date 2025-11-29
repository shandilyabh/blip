"""
constantly monitors the market.
supposed to generate position sizing,
stop loss, target

- constantly communicates with the portfolio
to gauge and orchestrate risk diversification
"""

class RiskEngine:
    def __init__(self, 
                 capital: float,
                 risk_per_trade: float = 0.005,  # 0.5%
                 max_leverage: float = 3,
                 max_position_pct: float = 0.2,
                 atr_period: int = 14,
                 volume_period: int = 20):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_leverage = max_leverage
        self.max_position_pct = max_position_pct
        self.atr_period = atr_period
        self.prev_close = None
        self.volume_period = volume_period
        self.volume_values = []

        self.atr_values = []
        self.max_allowed_dd = 0.15   # don't scale the position beyond 15%


    async def update_atr(self, bar):
        """update ATR incrementally"""
        if self.prev_close is None:
            tr = bar["high"] - bar["low"]
        else:
            tr = max(
                bar["high"] - bar["low"],
                abs(bar["high"] - self.prev_close),
                abs(bar["low"] - self.prev_close),
            )

        if len(self.atr_values) < self.atr_period:
            self.atr_values.append(tr)
        else:
            self.atr_values.pop(0)
            self.atr_values.append(tr)


    def _get_atr(self):
        if len(self.atr_values) == 0:
            return None
        return sum(self.atr_values) / len(self.atr_values)


    async def update_volume(self, bar):
        """Keeps a running list of recent volumes."""
        if "volume" in bar and bar["volume"] > 0:
            if len(self.volume_values) < self.volume_period:
                self.volume_values.append(bar["volume"])
            else:
                self.volume_values.pop(0)
                self.volume_values.append(bar["volume"])


    def _get_avg_volume(self):
        """Calculates the average of the stored volumes."""
        if not self.volume_values:
            return 0
        return sum(self.volume_values) / len(self.volume_values)


    async def determine_position(self, signal, bar, instrument_type="index", portfolio_state=None):
        """
        Compute size, stop, target based on:
        - signal direction
        - volatility (ATR)
        - volume confirmation (for equities)
        - capital risk budget
        - portfolio exposure and leverage
        """
        if signal is None or signal == 0:
            return None

        if portfolio_state:
            if portfolio_state.get("portfolio_drawdown_pct", 0) > self.max_allowed_dd:
                print("[RISK-THROTTLE]: Portfolio drawdown exceeds max allowed. No new trades.")
                return None

        await self.update_atr(bar)
        atr = self._get_atr()
        if atr is None or atr == 0:
            return None

        volume_factor = 1.0
        if instrument_type == "equity":
            await self.update_volume(bar)
            current_volume = bar.get("volume", 0)
            avg_volume = self._get_avg_volume()

            if avg_volume > 0 and current_volume > 0:
                if current_volume > avg_volume * 1.5:  # High volume
                    volume_factor = 1.2  # Increase size by 20%
                elif current_volume < avg_volume * 0.8: # Low volume signal
                    volume_factor = 0.8  # Reduce size by 20%
        
        direction = 1 if signal > 0 else -1

        # define stop based on ATR
        stop_distance = atr * 1.5
        entry_price = bar["close"]
        stop_price = entry_price - direction * stop_distance
        target_price = entry_price + direction * (stop_distance * 1.2)

        # risk capital
        capital_at_risk = self.capital * self.risk_per_trade
        size = capital_at_risk / stop_distance

        # Apply volume factor
        size *= volume_factor

        # enforce single position limits
        size = min(size, self.capital * self.max_position_pct / entry_price)

        # --- Leverage Check (Portfolio Level) ---
        if portfolio_state:
            current_positions_value = portfolio_state.get("total_positions_value", 0)
            new_position_value = size * entry_price
            
            projected_total_value = current_positions_value + new_position_value
            max_allowed_value = self.max_leverage * self.capital

            if projected_total_value > max_allowed_value:
                available_value = max_allowed_value - current_positions_value
                if available_value > 0:
                    capped_size = available_value / entry_price
                    size = min(size, capped_size)
                else:
                    size = 0 # No capital available for new positions

        size = int(size)
        if size == 0:
            return None

        return {
            "ts": bar["ts"],
            "side": "BUY" if direction == 1 else "SELL",
            "size": size,
            "entry": entry_price,
            "stop": round(stop_price, 2),
            "target": round(target_price, 2),
            "valid": True,
            "atr" : round(atr, 3)
        }
