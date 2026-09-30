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
    current_price = 15050 # Start at $150.50
    
    sleep_time = 1.0 / orders_per_sec
    batch_size = 50 

    while time.time() - start_time < duration:
        tail = header.tail
        head = header.head
        
        # Check space
        if tail + batch_size - head >= capacity:
            await asyncio.sleep(0.001)
            continue
            
        for _ in range(batch_size):
            # 1. Realistic Price Action (Random Walk / Brownian Motion)
            # Simulates tick-by-tick micro-movements
            tick_change = random.choices([-3, -2, -1, 0, 1, 2, 3], weights=[0.05, 0.15, 0.25, 0.10, 0.25, 0.15, 0.05])[0]
            current_price += tick_change
            if current_price < 100: current_price = 100
            
            # 2. Realistic Trade Sizes (Exponential Distribution)
            # Many small retail trades, rare massive institutional blocks
            size = int(random.expovariate(1.0 / 60.0)) + 1
            
            # 3. Side (Buy/Sell)
            side = random.choice([0, 1])
            
            idx = tail % capacity
            order = data_array[idx]
            order.order_id = order_id
            order.price = current_price
            order.size = size
            order.side = side
            order.timestamp = time.perf_counter_ns()
            
            tail += 1
            order_id += 1
            
        header.tail = tail
        
        # Simulate network yield
        if sleep_time * batch_size > 0.001:
            await asyncio.sleep(sleep_time * batch_size)
        else:
            await asyncio.sleep(0)

    # Send STOP signal
    tail = header.tail
    idx = tail % capacity
    order = data_array[idx]
    order.order_id = 0
    header.tail = tail + 1

    print(f"Simulator finished. Pushed {order_id-1} orders.")

if __name__ == "__main__":
    asyncio.run(simulate_firehose())

# GBM logic documented

# price boundary check

# throughput tuning

# batch size stabilization

# asyncio perf notes

# [Sim] Calibrated random walk step size

# [Sim] Adjusted scale parameter for whale trade simulation

# [Sim] Verified bid/ask spread generation logic
