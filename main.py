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
    
