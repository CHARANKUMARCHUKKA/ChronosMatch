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
    
