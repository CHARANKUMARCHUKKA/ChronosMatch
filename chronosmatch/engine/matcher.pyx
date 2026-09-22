# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: initializedcheck=False

from libc.stdlib cimport malloc, free
from libc.string cimport memset
from libc.stdint cimport uint8_t, uint32_t, uint64_t
import time

from .lob cimport Order, Execution, RingBufferHeader, OrderNode, PriceLevel

cdef uint64_t get_time_ns():
    return <uint64_t>time.perf_counter_ns()

cdef class Matcher:
    cdef OrderNode* order_pool
    cdef uint32_t pool_capacity
    cdef uint32_t pool_index
    
