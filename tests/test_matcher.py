import unittest
import ctypes
import time
from chronosmatch.engine.matcher import Matcher
from chronosmatch.ipc.ring_buffer import (
    get_ring_buffer,
    Order,
    Execution,
    ACTION_NEW,
    ACTION_CANCEL,
    SIDE_BUY,
    SIDE_SELL,
    EXEC_FILL,
    EXEC_CANCELED
)

class TestMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = Matcher(max_orders=10000, max_levels=100)
        self.tag_out = f"TestMatcherOut_{int(time.time() * 1000)}"
        self.mm_out, self.hdr_out, self.data_out = get_ring_buffer(self.tag_out, Execution, 1024, create=True)

    def tearDown(self):
        del self.hdr_out, self.data_out
        self.mm_out.close()

    def _send_order(self, order_id, price, size, side, action=ACTION_NEW):
        o = Order()
        o.order_id = order_id
        o.price = price
        o.size = size
        o.side = side
        o.action = action
        o.timestamp = time.perf_counter_ns()
        self.matcher.process_order_single(
            ctypes.addressof(o),
            ctypes.addressof(self.data_out),
            ctypes.addressof(self.hdr_out)
        )

    def test_resting_orders_bids_and_asks(self):
        """Verify non-crossing orders rest on bids and asks sides correctly."""
        self._send_order(order_id=1, price=9900, size=10, side=SIDE_BUY)
        self._send_order(order_id=2, price=10100, size=20, side=SIDE_SELL)

        self.assertEqual(self.matcher.get_num_bids(), 1)
        self.assertEqual(self.matcher.get_num_asks(), 1)
        self.assertEqual(self.matcher.get_best_bid(), 9900)
        self.assertEqual(self.matcher.get_best_ask(), 10100)
        self.assertEqual(self.hdr_out.tail, 0) # No executions generated

    def test_exact_crossing_match(self):
        """Verify crossing orders execute at the resting maker price."""
        # 1. Maker resting SELL at 10000 for size 50
        self._send_order(order_id=10, price=10000, size=50, side=SIDE_SELL)
        self.assertEqual(self.matcher.get_num_asks(), 1)

        # 2. Taker incoming BUY at 10000 for size 50
        self._send_order(order_id=20, price=10000, size=50, side=SIDE_BUY)

        # Both sides matched and emptied
        self.assertEqual(self.matcher.get_num_asks(), 0)
        self.assertEqual(self.matcher.get_num_bids(), 0)
        self.assertEqual(self.hdr_out.tail, 2) # Maker and taker executions

        exec_maker = self.data_out[0]
        exec_taker = self.data_out[1]
        self.assertEqual(exec_maker.order_id, 10)
        self.assertEqual(exec_maker.price, 10000)
        self.assertEqual(exec_maker.size, 50)
        self.assertEqual(exec_maker.exec_type, EXEC_FILL)

        self.assertEqual(exec_taker.order_id, 20)
        self.assertEqual(exec_taker.price, 10000)
        self.assertEqual(exec_taker.size, 50)
        self.assertEqual(exec_taker.exec_type, EXEC_FILL)

    def test_price_time_priority(self):
        """Verify earlier orders at the same price are matched first (FIFO priority)."""
        # Two resting SELL orders at the same price 10000
        self._send_order(order_id=101, price=10000, size=25, side=SIDE_SELL)
        self._send_order(order_id=102, price=10000, size=40, side=SIDE_SELL)

        # Incoming BUY order for 25 should match order 101 first
        self._send_order(order_id=201, price=10000, size=25, side=SIDE_BUY)

        self.assertEqual(self.hdr_out.tail, 2)
        exec_maker = self.data_out[0]
        self.assertEqual(exec_maker.order_id, 101) # Earliest order filled
        self.assertEqual(exec_maker.size, 25)

        # Order 102 should still be resting with size 40
        self.assertEqual(self.matcher.get_num_asks(), 1)
        self.assertEqual(self.matcher.get_best_ask(), 10000)

    def test_partial_fill_leaves_remaining_quantity(self):
        """Verify partial fill decrements resting order size and retains it in book."""
        # 1. Maker BUY 100 units at 5000
        self._send_order(order_id=301, price=5000, size=100, side=SIDE_BUY)

        # 2. Taker SELL 35 units at 5000
        self._send_order(order_id=302, price=5000, size=35, side=SIDE_SELL)

        self.assertEqual(self.hdr_out.tail, 2)
        exec_maker = self.data_out[0]
        exec_taker = self.data_out[1]
        self.assertEqual(exec_maker.size, 35)
        self.assertEqual(exec_taker.size, 35)

        # 3. Remaining 65 units can be matched by another order
        self._send_order(order_id=303, price=5000, size=65, side=SIDE_SELL)
        self.assertEqual(self.hdr_out.tail, 4)
        self.assertEqual(self.matcher.get_num_bids(), 0)

    def test_order_cancellation(self):
        """Verify cancelling resting order removes it from book and emits EXEC_CANCELED."""
        # Insert resting order
        self._send_order(order_id=401, price=7500, size=50, side=SIDE_BUY)
        self.assertEqual(self.matcher.get_num_bids(), 1)

        # Send cancellation
        self._send_order(order_id=401, price=7500, size=50, side=SIDE_BUY, action=ACTION_CANCEL)

        # Book is now empty
        self.assertEqual(self.matcher.get_num_bids(), 0)
        self.assertEqual(self.hdr_out.tail, 1)

        cancel_exec = self.data_out[0]
        self.assertEqual(cancel_exec.order_id, 401)
        self.assertEqual(cancel_exec.price, 7500)
        self.assertEqual(cancel_exec.size, 50)
        self.assertEqual(cancel_exec.exec_type, EXEC_CANCELED)

    def test_cancel_nonexistent_order_no_op(self):
        """Verify cancelling a non-existent order gracefully does nothing."""
        self._send_order(order_id=999999, price=7500, size=10, side=SIDE_BUY, action=ACTION_CANCEL)
        self.assertEqual(self.hdr_out.tail, 0)
        self.assertEqual(self.matcher.get_num_bids(), 0)

if __name__ == '__main__':
    unittest.main()
