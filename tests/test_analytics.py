"""
Unit tests for ChronosMatch Execution Analytics Module.
"""

import unittest
from chronosmatch.analytics.execution_stats import ExecutionMetricsTracker, TradeExecutionStats

class TestExecutionAnalytics(unittest.TestCase):

    def setUp(self):
        self.tracker = ExecutionMetricsTracker(max_history=1000)

    def test_initial_state(self):
        stats = self.tracker.get_summary()
        self.assertEqual(stats.total_trades, 0)
        self.assertEqual(stats.total_volume, 0)
        self.assertEqual(stats.vwap, 0.0)

    def test_vwap_calculation(self):
        # 100 units @ 10.0 = 1000 notional
        # 200 units @ 20.0 = 4000 notional
        # Total volume = 300, Total notional = 5000 -> VWAP = 5000 / 300 = 16.666...
        self.tracker.record_execution(price=10.0, size=100, side=0, latency_us=2.5)
        self.tracker.record_execution(price=20.0, size=200, side=1, latency_us=3.5)

        self.assertAlmostEqual(self.tracker.compute_vwap(), 5000.0 / 300.0, places=4)

    def test_latency_percentiles(self):
        for i in range(1, 101):
            self.tracker.record_execution(price=100.0, size=1, side=0, latency_us=float(i))

        stats = self.tracker.get_summary()
        self.assertEqual(stats.total_trades, 100)
        self.assertEqual(stats.min_latency_us, 1.0)
        self.assertEqual(stats.max_latency_us, 100.0)
        self.assertEqual(stats.p50_latency_us, 51.0)
        self.assertEqual(stats.p95_latency_us, 96.0)
        self.assertEqual(stats.p99_latency_us, 100.0)

    def test_slippage_calculation(self):
        self.tracker.record_execution(price=101.0, size=100, side=0, latency_us=1.0)
        # Benchmark = 100.0, Execution = 101.0 -> slippage = (1/100) * 10000 = 100 bps
        slippage_bps = self.tracker.compute_slippage(benchmark_price=100.0)
        self.assertAlmostEqual(slippage_bps, 100.0, places=2)

if __name__ == '__main__':
    unittest.main()
