import multiprocessing
import time
import os
import sys
import ctypes
import argparse

from chronosmatch.ipc.ring_buffer import get_ring_buffer, Order, Execution

def run_engine(capacity=65536):
    try:
        from chronosmatch.engine.matcher import Matcher
    except ImportError:
        print("ERROR: Cython engine module not found. Did you run 'python setup.py build_ext --inplace'?")
        sys.exit(1)
        
    print("[ENGINE] Initializing IPC ring buffers...")
    in_mm, in_hdr, in_data = get_ring_buffer("ChronosMatchInbound", Order, capacity, create=True)
    out_mm, out_hdr, out_data = get_ring_buffer("ChronosMatchOutbound", Execution, capacity, create=True)
    
    in_buf_addr = ctypes.addressof(in_data)
    in_hdr_addr = ctypes.addressof(in_hdr)
    out_buf_addr = ctypes.addressof(out_data)
    out_hdr_addr = ctypes.addressof(out_hdr)
    
    matcher = Matcher(max_orders=1000000, max_levels=10000)
    matcher.run(in_buf_addr, in_hdr_addr, out_buf_addr, out_hdr_addr)

def run_sim_feed(duration=3600, capacity=65536):
    import asyncio
    from chronosmatch.simulator.market_sim import simulate_firehose
    asyncio.run(simulate_firehose(tagname="ChronosMatchInbound", capacity=capacity, duration=duration))

def run_binance_stream(capacity=65536):
    import asyncio
    from chronosmatch.simulator.binance_feed import run_binance_feed
    asyncio.run(run_binance_feed(tagname="ChronosMatchInbound", capacity=capacity))

def run_terminal_monitor(duration=3600):
    from chronosmatch.monitor.latency_monitor import run_monitor
    run_monitor(duration=duration)

def parse_args():
    parser = argparse.ArgumentParser(description="ChronosMatch: Zero-Copy High-Frequency Trading Engine")
    parser.add_argument(
        "--feed",
        choices=["sim", "binance"],
        default="sim",
        help="Inbound order telemetry feed: 'sim' (high-throughput synthetic Brownian motion, default) or 'binance' (live BTC/USDT WebSocket)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=3600,
        help="Session runtime in seconds (default: 3600s)"
    )
    parser.add_argument(
        "--capacity",
        type=int,
        default=65536,
        help="Ring buffer slot capacity (default: 65,536)"
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Run in headless mode without curses terminal monitor"
    )
    return parser.parse_args()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    args = parse_args()
    
    print("=" * 65)
    print("  CHRONOSMATCH // ZERO-COPY HIGH-FREQUENCY TRADING ENGINE")
    print(f"  Feed Mode: {args.feed.upper()}  |  Capacity: {args.capacity:,} slots")
    print("=" * 65)
    
    # Start engine process
    engine_process = multiprocessing.Process(target=run_engine, args=(args.capacity,))
    engine_process.start()
    time.sleep(0.5) # Give engine time to allocate memory mapping
    
    # Start feed process
    if args.feed == "binance":
        feed_process = multiprocessing.Process(target=run_binance_stream, args=(args.capacity,))
    else:
        feed_process = multiprocessing.Process(target=run_sim_feed, args=(args.duration, args.capacity))
        
    feed_process.start()
    
    # Start monitor process if enabled
    monitor_process = None
    if not args.no_monitor:
        monitor_process = multiprocessing.Process(target=run_terminal_monitor, args=(args.duration,))
        monitor_process.start()
        
    try:
        if monitor_process:
            monitor_process.join()
        else:
            feed_process.join()
    except KeyboardInterrupt:
        print("\n[MAIN] Interrupted by user. Shutting down gracefully...")
    finally:
        for p in [feed_process, monitor_process, engine_process]:
            if p and p.is_alive():
                p.terminate()
                p.join(timeout=1.0)
                
    print("[MAIN] ChronosMatch shutdown complete.")
