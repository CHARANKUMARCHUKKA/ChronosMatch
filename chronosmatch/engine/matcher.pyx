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
    
    # Simple arrays for price levels
    cdef PriceLevel* bids
    cdef uint32_t num_bids
    
    cdef PriceLevel* asks
    cdef uint32_t num_asks
    
    cdef uint64_t execution_counter

    def __cinit__(self, uint32_t max_orders=1000000, uint32_t max_levels=10000):
        self.pool_capacity = max_orders
        self.order_pool = <OrderNode*>malloc(sizeof(OrderNode) * max_orders)
        self.pool_index = 0
        
        self.bids = <PriceLevel*>malloc(sizeof(PriceLevel) * max_levels)
        self.asks = <PriceLevel*>malloc(sizeof(PriceLevel) * max_levels)
        self.num_bids = 0
        self.num_asks = 0
        self.execution_counter = 0

    def __dealloc__(self):
        if self.order_pool != NULL:
            free(self.order_pool)
        if self.bids != NULL:
            free(self.bids)
        if self.asks != NULL:
            free(self.asks)

