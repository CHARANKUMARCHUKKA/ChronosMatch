import unittest
import multiprocessing
import ctypes
import time
from chronosmatch.engine.matcher import Matcher
from chronosmatch.ipc.ring_buffer import (
    get_ring_buffer,
    Order,
    Execution,
    SIDE_BUY,
    SIDE_SELL,
    ACTION_NEW,
    EXEC_FILL
)

def _engine_worker(in_tag, out_tag, capacity):
    in_mm, in_hdr, in_data = get_ring_buffer(in_tag, Order, capacity, create=False)
    out_mm, out_hdr, out_data = get_ring_buffer(out_tag, Execution, capacity, create=False)
    matcher = Matcher(max_orders=1000, max_levels=100)
    matcher.run(
        ctypes.addressof(in_data),
        ctypes.addressof(in_hdr),
        ctypes.addressof(out_data),
        ctypes.addressof(out_hdr)
    )
    del in_hdr, in_data, out_hdr, out_data
    in_mm.close()
    out_mm.close()

class TestIntegration(unittest.TestCase):
    def test_pipeline_e2e(self):
        """Verify multi-process pipeline: Producer -> Inbound RingBuffer -> Cython Matcher -> Outbound RingBuffer."""
        capacity = 256
        tag_in = f"TestPipeIn_{int(time.time() * 1000)}"
        tag_out = f"TestPipeOut_{int(time.time() * 1000)}"

        # 1. Setup shared memory buffers
        in_mm, in_hdr, in_data = get_ring_buffer(tag_in, Order, capacity, create=True)
        out_mm, out_hdr, out_data = get_ring_buffer(tag_out, Execution, capacity, create=True)

        try:
            # 2. Start engine process
            engine_proc = multiprocessing.Process(target=_engine_worker, args=(tag_in, tag_out, capacity))
            engine_proc.start()
            time.sleep(0.1)

            # 3. Producer: Push 2 crossing orders + STOP signal
            # Order 1: SELL 10 units at 60000
            idx1 = in_hdr.tail % capacity
            in_data[idx1].order_id = 1
            in_data[idx1].price = 60000
            in_data[idx1].size = 10
            in_data[idx1].side = SIDE_SELL
            in_data[idx1].action = ACTION_NEW
            in_data[idx1].timestamp = time.perf_counter_ns()
            in_hdr.tail += 1

            # Order 2: BUY 10 units at 60000
            idx2 = in_hdr.tail % capacity
            in_data[idx2].order_id = 2
            in_data[idx2].price = 60000
            in_data[idx2].size = 10
            in_data[idx2].side = SIDE_BUY
            in_data[idx2].action = ACTION_NEW
            in_data[idx2].timestamp = time.perf_counter_ns()
            in_hdr.tail += 1

            # Order 3: STOP signal (order_id = 0)
            idx3 = in_hdr.tail % capacity
            in_data[idx3].order_id = 0
            in_hdr.tail += 1

            # 4. Wait for engine process to process and terminate cleanly
            engine_proc.join(timeout=3.0)
            self.assertFalse(engine_proc.is_alive(), "Engine process did not terminate on STOP signal")

            # 5. Verify outbound executions
            self.assertEqual(out_hdr.tail, 2)
            self.assertEqual(out_data[0].order_id, 1)
            self.assertEqual(out_data[0].price, 60000)
            self.assertEqual(out_data[0].size, 10)
            self.assertEqual(out_data[0].exec_type, EXEC_FILL)

            self.assertEqual(out_data[1].order_id, 2)
            self.assertEqual(out_data[1].price, 60000)
            self.assertEqual(out_data[1].size, 10)
            self.assertEqual(out_data[1].exec_type, EXEC_FILL)

        finally:
            if engine_proc.is_alive():
                engine_proc.terminate()
            del in_hdr, in_data, out_hdr, out_data
            in_mm.close()
            out_mm.close()

if __name__ == '__main__':
    unittest.main()
