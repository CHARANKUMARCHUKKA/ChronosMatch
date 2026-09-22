import curses
import time
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Execution

def monitor_app(stdscr, duration=15):
    curses.curs_set(0)
    stdscr.nodelay(1)
    
    # Wait for the engine to create the outbound buffer
    time.sleep(1)
    
    try:
