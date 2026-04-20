"""
ConfluenceEngine — Multi-timeframe confluence checker for XAUUSD
Built from Fincept Terminal's multi-indicator framework + Verstige Strategy™
"""
from dataclasses import dataclass
from typing import List, Optional
import math


@dataclass
class ConfluenceResult:
    indicator: str
    signal: str  # "bullish" | "bearish" | "neutral"
    strength: float  # 0.0 - 1.0
    details: str


class ConfluenceEngine:
    """
    Checks 6 confluence layers for every signal:
    1. Session ATR blocks (London/NY overlap preferred)
    2. Psychological level (whole number proximity)
    3. Price action (pin bar, engulf, rejection candle)
    4. Volume confirmation
    5. Higher timeframe trend alignment
    6. Session timing (London/NY open window)
    """

    def __init__(self):
        self.layers = [
            self.check_atr_session,
            self.check_psychological_level,
            self.check_price_action,
            self.check_volume,
            self.check_htf_alignment,
            self.check_session_timing,
        ]

    def analyze(self, market_data: dict) -> tuple[int, List[ConfluenceResult]]:
        """
        Returns: (confluence_count, list of results)
        Each layer adds 1 confluence if passed, 0 if failed.
        Target: 5+ confluences for HIGH confidence signal.
        """
        results = []
        total = 0

        for layer_check in self.layers:
            result = layer_check(market_data)
            results.append(result)
            if result.signal in ("bullish", "bearish") and result.strength >= 0.6:
                total += 1

        return total, results

    def check_atr_session(self, data: dict) -> ConfluenceResult:
        """Layer 1: ATR session blocks aligned — ATR within 50% of session range."""
        atr = data.get("atr", 0)
        session_high = data.get("session_high", 0)
        session_low = data.get("session_low", 0)
        session_range = session_high - session_low

        if session_range == 0:
            return ConfluenceResult("ATR Session", "neutral", 0.0, "No session range data")

        ratio = atr / session_range

        if ratio <= 0.5:
            return ConfluenceResult(
                "ATR Session",
                "bullish" if data.get("bias") == "long" else "bearish",
                1.0,
                f"ATR {ratio:.1%} of session range — tight compression, explosive move likely"
            )
        elif ratio <= 0.75:
            return ConfluenceResult(
                "ATR Session", "neutral", 0.5,
                f"ATR {ratio:.1%} of session range — normal"
            )
        else:
            return ConfluenceResult(
                "ATR Session", "neutral", 0.3,
                f"ATR {ratio:.1%} of session range — high volatility, low confidence"
            )

    def check_psychological_level(self, data: dict) -> ConfluenceResult:
        """Layer 2: Price within 20 pips of a whole-number psychological level."""
        price = data.get("price", 0)
        level = data.get("nearest_psych_level", 0)
        distance = abs(price - level)

        # Whole number for XAUUSD = every $50 for spot, $100 for US30
        pip_value = 1.0  # for XAUUSD pips
        threshold = 20 * pip_value

        if distance <= threshold:
            proximity = 1.0 - (distance / threshold)
            return ConfluenceResult(
                "Psych Level",
                "bullish" if data.get("bias") == "long" else "bearish",
                0.7 + (proximity * 0.3),
                f"Price within {distance:.1f} pips of psychological level ${level:.0f}"
            )

        return ConfluenceResult(
            "Psych Level", "neutral", 0.2,
            f"No psychological level nearby (nearest: ${level:.0f}, {distance:.1f} pips away)"
        )

    def check_price_action(self, data: dict) -> ConfluenceResult:
        """Layer 3: Price action confirmation — pin bar, engulf, or rejection."""
        pattern = data.get("price_action_pattern", "none")

        bullish_patterns = ["pin_bar_bull", "engulf_bull", "hammer", "doji_bull"]
        bearish_patterns = ["pin_bar_bear", "engulf_bear", "shooting_star", "doji_bear"]

        if pattern in bullish_patterns:
            return ConfluenceResult(
                "Price Action", "bullish", 0.85,
                f"Bullish pattern detected: {pattern}"
            )
        elif pattern in bearish_patterns:
            return ConfluenceResult(
                "Price Action", "bearish", 0.85,
                f"Bearish pattern detected: {pattern}"
            )
        elif pattern != "none":
            return ConfluenceResult(
                "Price Action", "neutral", 0.4,
                f"Weak pattern: {pattern}"
            )
        else:
            return ConfluenceResult(
                "Price Action", "neutral", 0.0,
                "No price action pattern detected"
            )

    def check_volume(self, data: dict) -> ConfluenceResult:
        """Layer 4: Volume confirmation — above-average volume on signal candle."""
        volume = data.get("volume", 0)
        avg_volume = data.get("avg_volume", 1)

        if avg_volume == 0:
            return ConfluenceResult("Volume", "neutral", 0.0, "No volume data")

        ratio = volume / avg_volume

        if ratio >= 1.5:
            return ConfluenceResult(
                "Volume",
                "bullish" if data.get("bias") == "long" else "bearish",
                0.9,
                f"Volume {ratio:.1f}x average — strong conviction"
            )
        elif ratio >= 1.0:
            return ConfluenceResult(
                "Volume", "neutral", 0.5,
                f"Volume {ratio:.1f}x average — normal"
            )
        else:
            return ConfluenceResult(
                "Volume", "neutral", 0.2,
                f"Volume {ratio:.1f}x average — weak, low confidence"
            )

    def check_htf_alignment(self, data: dict) -> ConfluenceResult:
        """Layer 5: Higher timeframe trend aligned with signal direction."""
        htf_trend = data.get("htf_trend", "neutral")  # "up" | "down" | "neutral"
        bias = data.get("bias", "neutral")

        if htf_trend == bias or htf_trend == "neutral":
            if htf_trend == bias:
                return ConfluenceResult(
                    "HTF Alignment", bias, 0.8,
                    f"Higher timeframe {htf_trend.upper()} aligns with signal"
                )
            else:
                return ConfluenceResult(
                    "HTF Alignment", "neutral", 0.4,
                    "HTF neutral — no alignment or conflict"
                )
        else:
            return ConfluenceResult(
                "HTF Alignment", "neutral", 0.3,
                f"HTF {htf_trend.upper()} conflicts with {bias} signal"
            )

    def check_session_timing(self, data: dict) -> ConfluenceResult:
        """Layer 6: London (02:00-05:00 EST) or NY open (08:30-10:00 EST) window."""
        session = data.get("active_session", "none")  # "london" | "ny" | "asia" | "none"

        if session in ("london", "ny"):
            return ConfluenceResult(
                "Session Timing", "bullish" if data.get("bias") == "long" else "bearish",
                0.75,
                f"Active {session.upper()} session — high liquidity window"
            )
        elif session == "overlap":
            return ConfluenceResult(
                "Session Timing",
                "bullish" if data.get("bias") == "long" else "bearish",
                0.95,
                "London/NY overlap — peak liquidity, highest probability window"
            )
        else:
            return ConfluenceResult(
                "Session Timing", "neutral", 0.3,
                f"Outside preferred sessions (London/NY) — {session} session"
            )

    def assess_confidence(self, total: int, results: List[ConfluenceResult]) -> dict:
        """
        Translate confluence count to confidence level + recommendation.
        From NOVA.md: HIGH = 5+ confluences, MEDIUM = 3-4, LOW = 0-2
        """
        if total >= 5:
            return {
                "level": "HIGH",
                "confluence_count": total,
                "recommendation": "EXECUTE",
                "rationale": f"{total}/6 confluences confirmed. High-probability setup."
            }
        elif total >= 3:
            return {
                "level": "MEDIUM",
                "confluence_count": total,
                "recommendation": "ALERT_ONLY",
                "rationale": f"{total}/6 confluences. Confirm with additional analysis."
            }
        else:
            return {
                "level": "LOW",
                "confluence_count": total,
                "recommendation": "NO_TRADE",
                "rationale": f"Only {total}/6 confluences. Insufficient probability edge."
            }