import asyncio
import ctypes
import time
import random
import os
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Order, RingBufferHeader

async def simulate_firehose(tagname="ChronosMatchInbound", capacity=65536, duration=10, orders_per_sec=20000):
    print(f"Starting asyncio market simulator. Target: {orders_per_sec} ops/sec")
    
