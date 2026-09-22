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
                
