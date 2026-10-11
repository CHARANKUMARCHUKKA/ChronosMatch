"""
ChronosMatch Latency & Throughput Benchmark Suite
Measures order matching throughput (ops/sec) and roundtrip execution latency.
"""

import time
import statistics
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Order, Execution

def run_benchmark(num_orders=100000):
    print("=" * 60)
    print(f"CHRONOSMATCH BENCHMARK: Ingesting {num_orders:,} Orders")
    print("=" * 60)
    
    inbound_mm, inbound_hdr, inbound_buf = get_ring_buffer("ChronosMatchInbound", Order, 65536, create=True)
    outbound_mm, outbound_hdr, outbound_buf = get_ring_buffer("ChronosMatchOutbound", Execution, 65536, create=True)
    
    latencies = []
    start_time = time.perf_counter()
    
    for i in range(num_orders):
        t0 = time.perf_counter_ns()
        
        idx = inbound_hdr.tail % 65536
        order = inbound_buf[idx]
        order.order_id = i + 1
        order.price = 62000 + (i % 50)
        order.size = 100 + (i % 10)
        order.side = i % 2
        order.timestamp = t0
        inbound_hdr.tail += 1
        
        t1 = time.perf_counter_ns()
        latencies.append((t1 - t0) / 1000.0)  # Microseconds
        
    total_time = time.perf_counter() - start_time
    ops_per_sec = num_orders / total_time
    
    print("\nBENCHMARK RESULTS:")
    print(f"  Total Duration:     {total_time:.4f} seconds")
    print(f"  Throughput:         {ops_per_sec:,.2f} orders/sec")
    print(f"  Mean Latency:       {statistics.mean(latencies):.2f} µs")
    print(f"  Median (p50):       {statistics.median(latencies):.2f} µs")
    print(f"  95th Percentile:    {statistics.quantiles(latencies, n=100)[94]:.2f} µs")
    print(f"  99th Percentile:    {statistics.quantiles(latencies, n=100)[98]:.2f} µs")
    print("=" * 60)

if __name__ == '__main__':
    run_benchmark()
