"""
ChronosMatch Real-Time Execution Statistics & Microstructure Analytics
Calculates Volume-Weighted Average Price (VWAP), slippage, fill ratios, and latency distributions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math
import statistics

@dataclass
class TradeExecutionStats:
    total_volume: int = 0
    total_notional: float = 0.0
    vwap: float = 0.0
    total_trades: int = 0
    buy_trades: int = 0
    sell_trades: int = 0
    total_latency_us: float = 0.0
    avg_latency_us: float = 0.0
    min_latency_us: float = float("inf")
    max_latency_us: float = 0.0
    p50_latency_us: float = 0.0
    p95_latency_us: float = 0.0
    p99_latency_us: float = 0.0

class ExecutionMetricsTracker:
    """
    High-performance in-memory execution metrics aggregator.
    Maintains a rolling window of executions for sub-millisecond quant telemetry.
    """

    def __init__(self, max_history: int = 50000):
        self.max_history = max_history
        self.latencies: List[float] = []
        self.prices: List[float] = []
        self.volumes: List[int] = []
        self.sides: List[int] = []  # 0 = Buy, 1 = Sell
        self.timestamps: List[int] = []

        self.cum_volume: int = 0
        self.cum_notional: float = 0.0
        self.trade_count: int = 0
        self.buy_count: int = 0
        self.sell_count: int = 0

    def record_execution(self, price: float, size: int, side: int, latency_us: float, timestamp_ns: int = 0):
        """Record an execution event from the matching engine."""
        self.trade_count += 1
        self.cum_volume += size
        self.cum_notional += price * size

        if side == 0:
            self.buy_count += 1
        else:
            self.sell_count += 1

        self.latencies.append(latency_us)
        self.prices.append(price)
        self.volumes.append(size)
        self.sides.append(side)
        self.timestamps.append(timestamp_ns)

        if len(self.latencies) > self.max_history:
            self.latencies.pop(0)
            self.prices.pop(0)
            self.volumes.pop(0)
            self.sides.pop(0)
            self.timestamps.pop(0)

    def compute_vwap(self) -> float:
        """Calculate Volume Weighted Average Price."""
        if self.cum_volume == 0:
            return 0.0
        return self.cum_notional / self.cum_volume

    def compute_slippage(self, benchmark_price: float) -> float:
        """Compute execution slippage relative to a reference benchmark price."""
        if benchmark_price <= 0 or self.cum_volume == 0:
            return 0.0
        vwap = self.compute_vwap()
        return ((vwap - benchmark_price) / benchmark_price) * 10000.0  # Basis points (bps)

    def get_summary(self) -> TradeExecutionStats:
        """Generate comprehensive execution statistics summary."""
        stats = TradeExecutionStats()
        stats.total_trades = self.trade_count
        stats.total_volume = self.cum_volume
        stats.total_notional = self.cum_notional
        stats.vwap = self.compute_vwap()
        stats.buy_trades = self.buy_count
        stats.sell_trades = self.sell_count

        if self.latencies:
            valid_latencies = [l for l in self.latencies if l > 0]
            if valid_latencies:
                stats.total_latency_us = sum(valid_latencies)
                stats.avg_latency_us = stats.total_latency_us / len(valid_latencies)
                stats.min_latency_us = min(valid_latencies)
                stats.max_latency_us = max(valid_latencies)

                sorted_lats = sorted(valid_latencies)
                n = len(sorted_lats)
                stats.p50_latency_us = sorted_lats[int(n * 0.50)]
                stats.p95_latency_us = sorted_lats[int(n * 0.95)]
                stats.p99_latency_us = sorted_lats[int(n * 0.99)]

        return stats
