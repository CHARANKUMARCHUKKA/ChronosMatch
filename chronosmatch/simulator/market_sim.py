import asyncio
import ctypes
import time
import random
import os
from collections import deque
from chronosmatch.ipc.ring_buffer import (
    get_ring_buffer,
    Order,
    RingBufferHeader,
    ACTION_NEW,
    ACTION_CANCEL,
    SIDE_BUY,
    SIDE_SELL
)

async def simulate_firehose(tagname="ChronosMatchInbound", capacity=65536, duration=30, orders_per_sec=25000):
    """
    High-throughput asynchronous market simulation generating realistic
    micro-structure price movements via Geometric Brownian Motion and order cancellations.
    Prices are represented in fixed-point cents.
    """
    print(f"[MARKET SIMULATOR] Starting firehose. Target: {orders_per_sec:,} ops/sec, Duration: {duration}s")
    
    mm, header, data_array = get_ring_buffer(tagname, Order, capacity, create=True)
    
    start_time = time.time()
    order_id = 1
    current_price = 15050 # $150.50 in cents
    
    sleep_time = 1.0 / max(1, orders_per_sec)
    batch_size = 50 
    recent_order_ids = deque(maxlen=2000)

    try:
        while time.time() - start_time < duration:
            tail = header.tail
            head = header.head
            
            # Backpressure flow control
            if tail + batch_size - head >= capacity:
                await asyncio.sleep(0.001)
                continue
                
            for _ in range(batch_size):
                # ~10% probability of cancelling a recent resting order
                if recent_order_ids and random.random() < 0.10:
                    cancel_id = recent_order_ids.popleft()
                    idx = tail % capacity
                    order = data_array[idx]
                    order.order_id = cancel_id
                    order.price = 0 # Match by order_id
                    order.size = 0
                    order.side = random.choice([SIDE_BUY, SIDE_SELL])
                    order.action = ACTION_CANCEL
                    order.timestamp = time.perf_counter_ns()
                    tail += 1
                    continue

                # 1. Micro-tick Brownian motion
                tick_change = random.choices([-3, -2, -1, 0, 1, 2, 3], weights=[0.05, 0.15, 0.25, 0.10, 0.25, 0.15, 0.05])[0]
                current_price += tick_change
                if current_price < 100:
                    current_price = 100
                
                # 2. Pareto/Exponential order size distribution
                size = int(random.expovariate(1.0 / 60.0)) + 1
                
                # 3. Buy/Sell side
                side = random.choice([SIDE_BUY, SIDE_SELL])
                
                idx = tail % capacity
                order = data_array[idx]
                order.order_id = order_id
                order.price = current_price
                order.size = size
                order.side = side
                order.action = ACTION_NEW
                order.timestamp = time.perf_counter_ns()
                
                recent_order_ids.append(order_id)
                tail += 1
                order_id += 1
                
            header.tail = tail
            
            if sleep_time * batch_size > 0.001:
                await asyncio.sleep(sleep_time * batch_size)
            else:
                await asyncio.sleep(0)

        # Send STOP signal (order_id == 0)
        tail = header.tail
        idx = tail % capacity
        order = data_array[idx]
        order.order_id = 0
        header.tail = tail + 1

        print(f"[MARKET SIMULATOR] Finished. Generated {order_id - 1:,} total orders.")
    finally:
        order = None
        del header, data_array
        mm.close()

if __name__ == "__main__":
    asyncio.run(simulate_firehose())
