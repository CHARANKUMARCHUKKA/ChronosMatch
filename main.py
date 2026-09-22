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
