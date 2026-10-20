"""
ChronosMatch Analytics Module
Execution statistics, VWAP computation, slippage analysis, and latency metrics.
"""

from .execution_stats import ExecutionMetricsTracker, TradeExecutionStats

__all__ = ["ExecutionMetricsTracker", "TradeExecutionStats"]
