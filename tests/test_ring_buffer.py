import unittest
import ctypes
import time
from chronosmatch.ipc.ring_buffer import (
    get_ring_buffer,
    Order,
    Execution,
    RingBufferHeader,
    ACTION_NEW,
    ACTION_CANCEL,
    SIDE_BUY,
    SIDE_SELL,
    EXEC_FILL,
    EXEC_CANCELED
)

class TestRingBuffer(unittest.TestCase):
    def test_struct_sizes_and_alignment(self):
        """Verify struct memory packing and alignment match C layout exactly."""
        self.assertEqual(ctypes.sizeof(Order), 32)
        self.assertEqual(ctypes.sizeof(Execution), 48)
        self.assertEqual(ctypes.sizeof(RingBufferHeader), 24)

    def test_buffer_allocation_and_header(self):
        """Verify shared memory allocation initializes header correctly."""
        tag = f"TestRingBufAlloc_{int(time.time() * 1000)}"
        mm, hdr, data = get_ring_buffer(tag, Order, 128, create=True)
        try:
            self.assertEqual(hdr.head, 0)
            self.assertEqual(hdr.tail, 0)
            self.assertEqual(hdr.capacity, 128)
            self.assertEqual(len(data), 128)
        finally:
            del hdr, data
            mm.close()

    def test_order_read_write(self):
        """Verify writing an Order struct and reading back fields."""
        tag = f"TestOrderRW_{int(time.time() * 1000)}"
        mm, hdr, data = get_ring_buffer(tag, Order, 64, create=True)
        try:
            order = data[0]
            order.order_id = 999
            order.price = 6500050
            order.size = 150
            order.side = SIDE_BUY
            order.action = ACTION_NEW
            order.timestamp = 123456789

            hdr.tail = 1

            read_order = data[0]
            self.assertEqual(read_order.order_id, 999)
            self.assertEqual(read_order.price, 6500050)
            self.assertEqual(read_order.size, 150)
            self.assertEqual(read_order.side, SIDE_BUY)
            self.assertEqual(read_order.action, ACTION_NEW)
            self.assertEqual(read_order.timestamp, 123456789)
        finally:
            del order, read_order, hdr, data
            mm.close()

    def test_ring_buffer_circular_wrap(self):
        """Verify modulo arithmetic wrap-around behavior."""
        cap = 16
        tag = f"TestRingWrap_{int(time.time() * 1000)}"
        mm, hdr, data = get_ring_buffer(tag, Order, cap, create=True)
        try:
            for i in range(50):
                idx = hdr.tail % cap
                data[idx].order_id = i + 1
                data[idx].price = 1000 + i
                hdr.tail += 1

            self.assertEqual(hdr.tail, 50)
            last_idx = (hdr.tail - 1) % cap
            self.assertEqual(data[last_idx].order_id, 50)
            self.assertEqual(data[last_idx].price, 1049)
        finally:
            del hdr, data
            mm.close()

    def test_shared_memory_attachment(self):
        """Verify attaching to an existing ring buffer shares memory across handles."""
        tag = f"TestRingAttach_{int(time.time() * 1000)}"
        mm1, hdr1, data1 = get_ring_buffer(tag, Execution, 32, create=True)
        mm2, hdr2, data2 = get_ring_buffer(tag, Execution, 32, create=False)
        try:
            hdr1.tail = 5
            self.assertEqual(hdr2.tail, 5)

            data1[0].exec_id = 42
            data1[0].price = 7000000
            data1[0].exec_type = EXEC_FILL

            self.assertEqual(data2[0].exec_id, 42)
            self.assertEqual(data2[0].price, 7000000)
            self.assertEqual(data2[0].exec_type, EXEC_FILL)
        finally:
            del hdr1, data1, hdr2, data2
            mm1.close()
            mm2.close()

if __name__ == '__main__':
    unittest.main()
