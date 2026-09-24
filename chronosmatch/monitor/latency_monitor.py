import curses
import time
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Execution

def monitor_app(stdscr, duration=15):
    curses.curs_set(0)
    stdscr.nodelay(1)
    
    # Wait for the engine to create the outbound buffer
    time.sleep(1)
    
    try:
        mm, header, data_array = get_ring_buffer("ChronosMatchOutbound", Execution, capacity=65536, create=False)
    except FileNotFoundError:
        stdscr.addstr(0, 0, "Outbound ring buffer not found! Is the engine running?")
        stdscr.refresh()
        time.sleep(3)
        return

    head = header.head
    cap = header.capacity
    
    latencies = []
    total_executions = 0
    start_time = time.time()
    
    last_ui_update = 0
    
    while time.time() - start_time < duration:
        tail = header.tail
        
        while head < tail:
            idx = head % cap
            exec_record = data_array[idx]
            
            # calculate latency in microseconds
            latency_ns = exec_record.ts_out - exec_record.ts_in
            latency_us = latency_ns / 1000.0
            
            if latency_us > 0: # filter anomalies
                latencies.append(latency_us)
            total_executions += 1
            
            head += 1
            
        header.head = head
        
        # UI Update every 100ms
        now = time.time()
        if now - last_ui_update > 0.1:
            last_ui_update = now
            if len(latencies) > 10000:
                latencies = latencies[-10000:]
                
            if len(latencies) > 0:
                avg_lat = sum(latencies) / len(latencies)
                max_lat = max(latencies)
                min_lat = min(latencies)
                
                latencies_sorted = sorted(latencies)
                p99 = latencies_sorted[int(len(latencies) * 0.99)] if len(latencies) > 100 else 0
                
                stdscr.clear()
                stdscr.addstr(0, 0, "=== ChronosMatch Zero-Copy HFT Dashboard ===", curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(2, 0, f"Total Executions: {total_executions:,}")
                stdscr.addstr(4, 0, f"Latency Metrics (last {len(latencies)} execs):")
                stdscr.addstr(5, 2, f"Min Latency : {min_lat:8.2f} µs")
                stdscr.addstr(6, 2, f"Avg Latency : {avg_lat:8.2f} µs")
                stdscr.addstr(7, 2, f"P99 Latency : {p99:8.2f} µs")
                stdscr.addstr(8, 2, f"Max Latency : {max_lat:8.2f} µs")
                
                # Draw a simple bar chart
                bar_len = min(50, int(avg_lat / 2))
                stdscr.addstr(10, 0, "Avg Latency |" + "#" * bar_len)
                
                stdscr.refresh()
            
        time.sleep(0.001)

def run_monitor():
    try:
        curses.wrapper(monitor_app)
    except Exception as e:
        print(f"Monitor exited: {e}")

if __name__ == "__main__":
    run_monitor()

# div-by-zero mitigation

# [Monitor] Microsecond timestamp differential recording module
