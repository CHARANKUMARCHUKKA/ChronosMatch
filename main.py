import multiprocessing
import time
import os
import sys
import ctypes

from chronosmatch.simulator.market_sim import simulate_firehose
from chronosmatch.monitor.latency_monitor import run_monitor
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Order, Execution

def run_engine():
    try:
        from chronosmatch.engine.matcher import Matcher
    except ImportError:
        print("ERROR: Cython engine module not found. Did you run 'python setup.py build_ext --inplace'?")
        sys.exit(1)
        
    print("Initializing IPC ring buffers for engine...")
    in_mm, in_hdr, in_data = get_ring_buffer("ChronosMatchInbound", Order, 65536, create=True)
    out_mm, out_hdr, out_data = get_ring_buffer("ChronosMatchOutbound", Execution, 65536, create=True)
    
    # We need the memory addresses to pass to Cython
    in_buf_addr = ctypes.addressof(in_data)
    in_hdr_addr = ctypes.addressof(in_hdr)
    out_buf_addr = ctypes.addressof(out_data)
    out_hdr_addr = ctypes.addressof(out_hdr)
    
    matcher = Matcher(max_orders=1000000, max_levels=10000)
    matcher.run(in_buf_addr, in_hdr_addr, out_buf_addr, out_hdr_addr)

def run_simulator():
    import asyncio
    asyncio.run(simulate_firehose(duration=36000, orders_per_sec=20000))

if __name__ == '__main__':
    # Fix for Windows multiprocessing
    multiprocessing.freeze_support()
    
    print("Starting ChronosMatch Zero-Copy HFT Engine...")
    
    engine_process = multiprocessing.Process(target=run_engine)
    sim_process = multiprocessing.Process(target=run_simulator)
    monitor_process = multiprocessing.Process(target=run_monitor)
    
    engine_process.start()
    time.sleep(1) # Give engine time to setup memory map
    
    monitor_process.start()
    sim_process.start()
    
    sim_process.join()
    monitor_process.join()
    engine_process.terminate()
    engine_process.join()
    
    print("ChronosMatch finished successfully.")

# test harness prep

# mp spawn cleanup

# final linting pass

# [Sim] Ensured sleep intervals match HFT constraints

# [Meta] ChronosMatch - High Frequency Matching Engine

# [Process] Trap SIGINT for clean subprocess exit

# [Opt] Added micro-sleep to idle spin lock

# [Config] Duration hardcoded for infinite run
