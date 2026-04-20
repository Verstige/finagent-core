"""
RiskCalculator — Portfolio-level risk metrics inspired by Fincept's QuantLib suite
VaR, Sharpe, drawdown, position sizing — the math layer beneath every signal.
"""
from dataclasses import dataclass
from typing import List, Optional
import math


@dataclass
class PositionRisk:
    symbol: str
    size: float  # units
    entry: float
    stop_loss: float
    risk_amount: float  # $ at risk
    risk_pct: float  # % of portfolio


@dataclass
class PortfolioRisk:
    total_equity: float
    available_margin: float
    max_position_size: float
    var_95: float  # 95% VaR (1-day)
    sharpe_ratio: float
    max_drawdown: float
    positions: List[PositionRisk]


class RiskCalculator:
    """
    Risk management engine — calculates position sizes, VaR, Sharpe.
    From Fincept: riskfoliolib + quantstats_analytics modules.
    """

    def __init__(self, account_balance: float = 10000):
        self.account_balance = account_balance
        self.max_risk_pct = 0.02  # 2% max risk per trade

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        risk_amount_dollars: float
    ) -> float:
        """
        Calculate position size in units from stop loss distance.
        risk_amount_dollars = max dollars willing to lose on this trade.
        """
        distance = abs(entry_price - stop_loss)
        if distance == 0:
            return 0.0

        # Pip value for XAUUSD: $0.10 per pip (1 pip = $0.10)
        pip_value = 0.10
        risk_pips = distance / pip_value

        position_size = risk_amount_dollars / distance
        return round(position_size, 2)

    def max_position_from_risk(self, stop_loss: float, entry: float) -> float:
        """
        Standard: risk 2% of account per trade.
        Returns max position size in units.
        """
        risk_dollars = self.account_balance * self.max_risk_pct
        return self.calculate_position_size(entry, stop_loss, risk_dollars)

    def var_1day(self, returns: List[float], confidence: float = 0.95) -> float:
        """
        Historical Value at Risk — 95% confidence.
        Returns the maximum loss expected on any given day.
        """
        if not returns:
            return 0.0

        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        # VaR is expressed as positive number (loss)
        return abs(sorted_returns[max(0, index)])

    def sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        Sharpe Ratio = (Return - RiskFreeRate) / StdDev(Returns)
        Annualized. Assume 252 trading days.
        """
        if not returns or len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        annualized_return = mean_return * 252
        annualized_std = std_dev * math.sqrt(252)

        return (annualized_return - risk_free_rate) / annualized_std

    def max_drawdown(self, equity_curve: List[float]) -> float:
        """
        Maximum drawdown from peak — expressed as percentage.
        """
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd * 100  # as percentage

    def calculate_portfolio_risk(
        self,
        positions: List[dict],
        equity_curve: Optional[List[float]] = None,
        returns: Optional[List[float]] = None
    ) -> PortfolioRisk:
        """
        Full portfolio risk assessment.
        Takes a list of active positions + optional history for VaR/Sharpe.
        """
        total_risk = sum(p.get("risk_amount", 0) for p in positions)
        risk_pct = (total_risk / self.account_balance) * 100

        # Placeholder positions
        pos_risks = [
            PositionRisk(
                symbol=p["symbol"],
                size=p.get("size", 0),
                entry=p.get("entry", 0),
                stop_loss=p.get("stop_loss", 0),
                risk_amount=p.get("risk_amount", 0),
                risk_pct=p.get("risk_amount", 0) / self.account_balance * 100
            )
            for p in positions
        ]

        portfolio = PortfolioRisk(
            total_equity=self.account_balance,
            available_margin=self.account_balance * 0.8,  # simplified
            max_position_size=self.max_position_from_risk(0, 0),  # placeholder
            var_95=self.var_1day(returns or []) if returns else 0.0,
            sharpe_ratio=self.sharpe_ratio(returns or []) if returns else 0.0,
            max_drawdown=self.max_drawdown(equity_curve or []) if equity_curve else 0.0,
            positions=pos_risks
        )

        return portfolio

    def risk_reward_quality(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Kelly-style quality score for a trading strategy.
        Returns: edge quality 0-1 where >0.5 is positive expected value.
        """
        if avg_loss == 0 or win_rate == 0:
            return 0.0

        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        edge = expectancy / avg_loss

        return min(max(edge / 2, 0), 1)  # Normalized to 0-1