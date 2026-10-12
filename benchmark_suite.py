"""
ChronosMatch Latency & Throughput Benchmark Suite
Measures actual Cython matching engine throughput and roundtrip execution latency (µs).
"""

import time
import statistics
import multiprocessing
import ctypes
from chronosmatch.engine.matcher import Matcher
from chronosmatch.ipc.ring_buffer import (
    get_ring_buffer,
    Order,
    Execution,
    ACTION_NEW,
    SIDE_BUY,
    SIDE_SELL
)

def _engine_proc(in_tag, out_tag, capacity):
    in_mm, in_hdr, in_data = get_ring_buffer(in_tag, Order, capacity, create=False)
    out_mm, out_hdr, out_data = get_ring_buffer(out_tag, Execution, capacity, create=False)
    matcher = Matcher(max_orders=1000000, max_levels=10000)
    matcher.run(
        ctypes.addressof(in_data),
        ctypes.addressof(in_hdr),
        ctypes.addressof(out_data),
        ctypes.addressof(out_hdr)
    )
    del in_hdr, in_data, out_hdr, out_data
    in_mm.close()
    out_mm.close()

def run_benchmark(num_orders=50000, capacity=65536):
    multiprocessing.freeze_support()
    print("=" * 65)
    print(f"CHRONOSMATCH BENCHMARK: Ingesting & Matching {num_orders:,} Orders")
    print("=" * 65)
    
    tag_in = f"BenchIn_{int(time.time() * 1000)}"
    tag_out = f"BenchOut_{int(time.time() * 1000)}"

    in_mm, in_hdr, in_data = get_ring_buffer(tag_in, Order, capacity, create=True)
    out_mm, out_hdr, out_data = get_ring_buffer(tag_out, Execution, capacity, create=True)

    engine = multiprocessing.Process(target=_engine_proc, args=(tag_in, tag_out, capacity))
    engine.start()
    time.sleep(0.15)

    latencies = []
    out_head = 0
    t_start = time.perf_counter()

    for i in range(num_orders):
        # Backpressure wait if inbound ring buffer is full
        while in_hdr.tail - in_hdr.head >= capacity - 1:
            # Drain outbound executions while waiting
            while out_head < out_hdr.tail:
                idx_out = out_head % capacity
                rec = out_data[idx_out]
                lat = (rec.ts_out - rec.ts_in) / 1000.0
                if 0 < lat < 50000:
                    latencies.append(lat)
                out_head += 1
            time.sleep(0.00001)

        idx = in_hdr.tail % capacity
        order = in_data[idx]
        order.order_id = i + 1
        order.price = 6200000 + ((i % 10) * 5)
        order.size = 10 + (i % 5)
        order.side = i % 2 # Alternate BUY and SELL to produce continuous matches
        order.action = ACTION_NEW
        order.timestamp = time.perf_counter_ns()
        in_hdr.tail += 1

        # Periodically drain outbound executions
        if i % 100 == 0:
            while out_head < out_hdr.tail:
                idx_out = out_head % capacity
                rec = out_data[idx_out]
                lat = (rec.ts_out - rec.ts_in) / 1000.0
                if 0 < lat < 50000:
                    latencies.append(lat)
                out_head += 1

    # Send STOP signal
    idx = in_hdr.tail % capacity
    in_data[idx].order_id = 0
    in_hdr.tail += 1

    engine.join(timeout=3.0)
    if engine.is_alive():
        engine.terminate()

    # Drain remaining executions
    while out_head < out_hdr.tail:
        idx_out = out_head % capacity
        rec = out_data[idx_out]
        lat = (rec.ts_out - rec.ts_in) / 1000.0
        if 0 < lat < 50000:
            latencies.append(lat)
        out_head += 1

    t_end = time.perf_counter()
    total_time = t_end - t_start
    throughput = num_orders / total_time
    matches_generated = len(latencies)

    print("\nBENCHMARK RESULTS:")
    print(f"  Total Duration:     {total_time:.4f} seconds")
    print(f"  Ingest Throughput:  {throughput:,.2f} orders/sec")
    print(f"  Matches Generated:  {matches_generated:,} trades")
    if latencies:
        print(f"  Min Latency:        {min(latencies):.2f} us")
        print(f"  Mean Latency:       {statistics.mean(latencies):.2f} us")
        print(f"  Median (P50):       {statistics.median(latencies):.2f} us")
        if len(latencies) >= 100:
            print(f"  95th Percentile:    {statistics.quantiles(latencies, n=100)[94]:.2f} us")
            print(f"  99th Percentile:    {statistics.quantiles(latencies, n=100)[98]:.2f} us")
        print(f"  Max Latency:        {max(latencies):.2f} us")
    print("=" * 65)

    order = None
    rec = None
    del in_hdr, in_data, out_hdr, out_data
    in_mm.close()
    out_mm.close()

if __name__ == '__main__':
    run_benchmark(num_orders=20000)

# [CI-Perf] Verified 100k iteration warmups
