import asyncio
import ctypes
import time
import random
import os
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Order, RingBufferHeader

async def simulate_firehose(tagname="ChronosMatchInbound", capacity=65536, duration=10, orders_per_sec=20000):
    print(f"Starting asyncio market simulator. Target: {orders_per_sec} ops/sec")
    
    # Create the mmap ring buffer (create=True creates it)
    mm, header, data_array = get_ring_buffer(tagname, Order, capacity, create=True)
    
    start_time = time.time()
    order_id = 1
    mid_price = 10000 # e.g., $100.00
    
    sleep_time = 1.0 / orders_per_sec
    
    # Pre-generate some randomness to avoid random.randint overhead in the hot loop
    sides = [random.choice([0, 1]) for _ in range(1000)]
    prices = [mid_price + random.randint(-5, 5) for _ in range(1000)]
    sizes = [random.randint(1, 50) for _ in range(1000)]
    
    idx_rnd = 0
    batch_size = 50 # batch inserts to achieve higher throughput

    while time.time() - start_time < duration:
        tail = header.tail
        head = header.head
        
        # Check space
        if tail + batch_size - head >= capacity:
            await asyncio.sleep(0.001)
            continue
            
        for _ in range(batch_size):
            idx = tail % capacity
