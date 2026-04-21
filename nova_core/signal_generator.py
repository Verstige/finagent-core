"""
SignalGenerator — Generates trade signals from Fincept Terminal's investor agent frameworks
Supports: Buffett (value), Graham (quant), Lynch (growth), Dalio (macro), Marks (risk), Soros (reflexivity)

Each investor archetype brings a different analytical lens to signal validation.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from .confluence_engine import ConfluenceEngine, ConfluenceResult


class InvestorStyle(Enum):
    BUFFETT = "buffett"       # Value — fair value vs current price
    GRAHAM = "graham"         # Quant — intrinsic value via fundamentals
    LYNCH = "lynch"           # Growth — earnings momentum + sector
    DALIO = "dalio"           # Macro — risk parity,宏观周期
    MARKS = "marks"           # Risk — credit cycles,Bear market stages
    SOROS = "soros"           # Reflexivity — self-reinforcing feedback loops
    MUNGER = "munger"         # Mental models — multi-factor heuristics
    KLARMAN = "klarman"       # Distressed — bottom-up,极度悲观
    BERKSHIRE = "berkshire"   # Moat + capital allocation lens


@dataclass
class InvestorView:
    style: InvestorStyle
    signal: str  # "bullish" | "bearish" | "neutral"
    conviction: float  # 0.0 - 1.0
    thesis: str  # 1-2 sentence explanation
    key_factor: str  # the single most important factor in this view


@dataclass
class TradeSignal:
    # Identity
    id: str
    generated_at: str
    symbol: str  # XAUUSD, US30, NAS100

    # Direction
    direction: str  # "long" | "short"

    # Entry
    entry_price: float
    stop_loss: float
    take_profit: float

    # Risk/Reward
    risk_reward_ratio: float
    risk_amount_pips: float

    # Confidence (from confluence engine)
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    confluence_count: int

    # Investor archetype views
    investor_views: List[InvestorView] = field(default_factory=list)

    # Execution
    recommendation: str = "ALERT_ONLY"  # "EXECUTE" | "ALERT_ONLY" | "NO_TRADE"

    def to_telegram_format(self) -> str:
        """Format signal for Telegram output — HTML parse_mode.
        Matches the original Verstige signal card format."""
        direction_label = "BUY ✅" if self.direction == "long" else "SELL ❌"
        emoji = "🟢" if self.direction == "long" else "🔴"
        conf_emoji = "🔥" if self.confidence == "HIGH" else "⚠️" if self.confidence == "MEDIUM" else "⏳"

        entry = self.entry_price
        direction_mult = 1 if self.direction == "long" else -1

        # Pip calculation for XAUUSD: 1 pip = $0.10, so divide by 0.10
        pip_value = 0.10
        sl_pips = round(abs(entry - self.stop_loss) / pip_value, 1)
        tp1_price = self.take_profit
        tp2_price = round(entry + direction_mult * abs(entry - self.stop_loss) * 1.5, 2)
        tp3_price = round(entry + direction_mult * abs(entry - self.stop_loss) * 3.0, 2)
        tp1_pips = round(abs(tp1_price - entry) / pip_value, 1)
        tp2_pips = round(abs(tp2_price - entry) / pip_value, 1)
        tp3_pips = round(abs(tp3_price - entry) / pip_value, 1)

        # Dominant investor archetype for strategy label
        strategy_label = "Verstige Strategy™ + Investor Confluence"
        if self.investor_views:
            top = max(self.investor_views, key=lambda v: v.conviction)
            strategy_label = f"{top.style.value.upper()} Framework"

        from datetime import datetime

        lines = [
            f"{emoji} <b>{direction_label}</b> — <b>XAUUSD</b> ✨",
            f"",
            f"<b>Entry:</b> <code>{entry:.2f}</code>",
            f"<b>Stop Loss:</b> <code>{self.stop_loss:.2f}</code> <i>({sl_pips:.0f} pips)</i>",
            f"",
            f"📍 <b>Take Profit Levels</b>",
            f"├ 🥇 TP1: <code>{tp1_price:.2f}</code> <i>(+{tp1_pips:.0f} pips)</i>",
            f"├ 🥈 TP2: <code>{tp2_price:.2f}</code> <i>(+{tp2_pips:.0f} pips)</i>",
            f"└ 🥉 TP3: <code>{tp3_price:.2f}</code> <i>(+{tp3_pips:.0f} pips)</i>",
            f"",
            f"📊 <b>Risk : Reward</b>",
            f"├ 1:1 → +{tp1_pips:.0f}p | 1:2 → +{tp2_pips:.0f}p | 1:6 → +{tp3_pips:.0f}p",
            f"",
            f"{conf_emoji} <b>{self.confidence}</b> confidence — {self.confluence_count}/6 confluences",
            f"🧠 <b>Strategy:</b> {strategy_label}",
            f"⏰ {datetime.utcnow().strftime('%I:%M %p EDT')}",
            f"",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"<i>Verstige OS Automated Signal</i>",
        ]

        return "\n".join(lines)

    def to_full_report(self) -> str:
        """Full analysis report — NOVA full report mode."""
        lines = [
            f"# Trading Signal — {self.symbol}",
            f"## {self.direction.upper()} @ {self.entry_price:.2f}",
            f"**Generated:** {self.generated_at}",
            f"",
            f"### Risk Parameters",
            f"| Parameter | Value |",
            f"|---|---|",
            f"| Entry | {self.entry_price:.2f} |",
            f"| Stop Loss | {self.stop_loss:.2f} |",
            f"| Take Profit | {self.take_profit:.2f} |",
            f"| Risk/Reward | {self.risk_reward_ratio:.1f}:1 |",
            f"| Risk (pips) | {self.risk_amount_pips:.1f} |",
            f"",
            f"### Confluence Analysis ({self.confluence_count}/6)",
            f"**Confidence:** {self.confidence}",
            f"",
            f"### Investor Archetype Views",
        ]

        for view in sorted(self.investor_views, key=lambda v: v.conviction, reverse=True):
            conf_bar = "█" * int(view.conviction * 5) + "░" * (5 - int(view.conviction * 5))
            lines.append(
                f"- **{view.style.value.upper()}** [{conf_bar}] — {view.thesis}"
            )

        lines.append(f"\n**Recommendation:** {self.recommendation}")

        return "\n".join(lines)


class SignalGenerator:
    """
    Generates trade signals by combining confluence analysis with investor archetype lenses.
    From Fincept: 37 agents, each with different analytical strength.
    We use 9 core archetypes relevant to our markets (XAUUSD, US30, NAS100).
    """

    def __init__(self):
        self.confluence = ConfluenceEngine()
        self.investor_weights = {
            InvestorStyle.BUFFETT: 0.15,
            InvestorStyle.GRAHAM: 0.10,
            InvestorStyle.LYNCH: 0.08,
            InvestorStyle.DALIO: 0.20,  # Macro focus suits XAUUSD
            InvestorStyle.MARKS: 0.15,   # Risk sentiment key for gold
            InvestorStyle.SOROS: 0.10,
            InvestorStyle.MUNGER: 0.08,
            InvestorStyle.KLARMAN: 0.07,
            InvestorStyle.BERKSHIRE: 0.07,
        }

    def generate(
        self,
        market_data: dict,
        direction: str,
        entry_price: float
    ) -> TradeSignal:
        """
        Main entry point — takes market data + direction + entry, outputs full signal.
        """
        from uuid import uuid4

        # Step 1: Confluence analysis
        confluence_count, results = self.confluence.analyze(market_data)
        confidence_data = self.confluence.assess_confidence(confluence_count, results)

        # Step 2: Run investor archetype views
        investor_views = self._run_investor_views(market_data, direction, entry_price, confluence_count)

        # Step 3: Calculate risk parameters
        sl, tp, rr, risk_pips = self._calculate_risk(
            entry_price, direction, market_data.get("atr", 10)
        )

        # Step 4: Build signal
        signal = TradeSignal(
            id=str(uuid4())[:8],
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            symbol=market_data.get("symbol", "XAUUSD"),
            direction=direction,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit=tp,
            risk_reward_ratio=rr,
            risk_amount_pips=risk_pips,
            confidence=confidence_data["level"],
            confluence_count=confluence_count,
            investor_views=investor_views,
            recommendation=confidence_data["recommendation"],
        )

        return signal

    def _run_investor_views(
        self, data: dict, direction: str, entry: float, confluence: int
    ) -> List[InvestorView]:
        views = []

        # Buffett — fair value vs current price
        fair_value = data.get("fair_value", entry)
        gap = (entry - fair_value) / fair_value * 100
        signal = "neutral"
        if gap < -10:
            signal = "bullish"
        elif gap > 10:
            signal = "bearish"

        views.append(InvestorView(
            style=InvestorStyle.BUFFETT,
            signal=signal,
            conviction=min(abs(gap) / 20, 1.0) if gap != 0 else 0.3,
            thesis=f"Entry at {gap:.1f}% {'below' if gap < 0 else 'above'} fair value — {'margin of safety' if gap < 0 else 'overvalued'}",
            key_factor="Fair value gap" if abs(gap) > 10 else "No clear value edge"
        ))

        # Dalio — macro cycle positioning (gold = risk-off / inflation hedge)
        macro_cycle = data.get("macro_cycle", "neutral")  # "expansion" | "peak" | "contraction" | "recovery"
        if direction == "long":
            if macro_cycle in ("contraction", "recovery"):
                conviction = 0.85
                thesis = f"Macro {macro_cycle} phase — risk-off flows favor long gold"
            else:
                conviction = 0.5
                thesis = f"Macro {macro_cycle} phase — mixed signals for gold"
        else:
            if macro_cycle == "expansion":
                conviction = 0.8
                thesis = "Macro expansion — risk-on reduces gold demand"
            else:
                conviction = 0.4
                thesis = f"Macro {macro_cycle} — short bias moderate"

        views.append(InvestorView(
            style=InvestorStyle.DALIO,
            signal="bullish" if conviction > 0.6 else "neutral" if conviction > 0.4 else "bearish",
            conviction=conviction,
            thesis=thesis,
            key_factor=f"Macro cycle: {macro_cycle}"
        ))

        # Marks — credit cycle / risk sentiment
        risk_sentiment = data.get("risk_sentiment", "neutral")  # "fear" | "complacency" | "euphoria"
        if risk_sentiment == "fear" and direction == "long":
            conviction, thesis = 0.9, "Risk sentiment in FEAR — safe haven bid supports gold"
        elif risk_sentiment == "euphoria" and direction == "short":
            conviction, thesis = 0.85, "Risk euphoria — gold overvalued in risk-on environment"
        elif risk_sentiment == "complacency":
            conviction, thesis = 0.4, "Market complacency — no strong directional view"
        else:
            conviction, thesis = 0.5, f"Risk sentiment: {risk_sentiment}"

        views.append(InvestorView(
            style=InvestorStyle.MARKS,
            signal="bullish" if conviction > 0.6 else "neutral",
            conviction=conviction,
            thesis=thesis,
            key_factor=f"Risk sentiment: {risk_sentiment}"
        ))

        # Graham — quantitative edge (RSI, moving averages)
        rsi = data.get("rsi", 50)
        if rsi < 35:
            conviction, thesis = 0.75, f"RSI {rsi:.0f} — oversold, mean reversion bias"
            signal = "bullish"
        elif rsi > 65:
            conviction, thesis = 0.75, f"RSI {rsi:.0f} — overbought, mean reversion bias"
            signal = "bearish"
        else:
            conviction, thesis = 0.4, f"RSI {rsi:.0f} — neutral zone"
            signal = "neutral"

        views.append(InvestorView(
            style=InvestorStyle.GRAHAM,
            signal=signal,
            conviction=conviction,
            thesis=thesis,
            key_factor=f"RSI: {rsi:.0f}"
        ))

        # Add remaining archetypes with lighter analysis
        views.extend([
            InvestorView(
                style=InvestorStyle.LYNCH,
                signal=direction,
                conviction=0.5,
                thesis="Growth metrics mixed — no clear sector momentum signal",
                key_factor="Earnings momentum: neutral"
            ),
            InvestorView(
                style=InvestorStyle.SOROS,
                signal="neutral" if confluence < 5 else direction,
                conviction=0.6 if confluence >= 5 else 0.3,
                thesis=f"Reflexivity: market positioning self-reinforcing at {confluence}/6 confluences",
                key_factor="Self-reinforcing feedback loop"
            ),
            InvestorView(
                style=InvestorStyle.MUNGER,
                signal="neutral",
                conviction=0.45,
                thesis="Multi-factor check: no single dominant signal",
                key_factor="Mental model: inconclusive"
            ),
            InvestorView(
                style=InvestorStyle.KLARMAN,
                signal=direction if confluence >= 4 else "neutral",
                conviction=min(confluence / 6, 0.7),
                thesis="Distressed lens: setup requires patience, no forced entry",
                key_factor="Value trap risk: moderate"
            ),
            InvestorView(
                style=InvestorStyle.BERKSHIRE,
                signal="neutral",
                conviction=0.5,
                thesis="Moat analysis — gold has no competitive moat, stores value in crisis only",
                key_factor="Moat: none (commodity)"
            ),
        ])

        return views

    def _calculate_risk(self, entry: float, direction: str, atr: float) -> tuple:
        """
        Calculate stop loss, take profit, R:R from entry using ATR.
        Rule: Stop at 1.5x ATR, TP at 2x ATR (giving 1.33:1) or better if RR > 2.0
        """
        # ATR in price units for XAUUSD (1 pip = $0.01 for most pairs, $0.10 for gold)
        pip_value = 0.10  # XAUUSD: $0.10 per pip
        atr_pips = atr / pip_value

        sl_distance = atr * 1.5
        tp_distance = atr * 2.0

        # Alternative: if we can get 2:1, use that
        if tp_distance >= sl_distance * 2:
            tp_distance = sl_distance * 2
        else:
            # Adjust to hit 2:1 — scale tp up
            tp_distance = sl_distance * 2

        if direction == "long":
            sl = entry - sl_distance
            tp = entry + tp_distance
        else:
            sl = entry + sl_distance
            tp = entry - tp_distance

        rr = tp_distance / sl_distance
        risk_pips = sl_distance / pip_value

        return round(sl, 2), round(tp, 2), round(rr, 2), round(risk_pips, 1)