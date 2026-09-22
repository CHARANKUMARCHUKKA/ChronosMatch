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

    cdef OrderNode* alloc_node(self, Order* order):
        if self.pool_index >= self.pool_capacity:
            return NULL # Out of memory in pool
        cdef OrderNode* node = &self.order_pool[self.pool_index]
        self.pool_index += 1
        node.order = order[0]
        node.next = NULL
        return node

    cdef void add_execution(self, Execution* out_buf, RingBufferHeader* out_hdr, uint64_t order_id, uint64_t price, uint32_t size, uint64_t ts_in, uint64_t ts_out):
        cdef uint64_t tail = out_hdr.tail
        cdef uint64_t cap = out_hdr.capacity
        cdef uint64_t idx = tail % cap
        
        self.execution_counter += 1
        out_buf[idx].exec_id = self.execution_counter
        out_buf[idx].order_id = order_id
        out_buf[idx].price = price
        out_buf[idx].size = size
        out_buf[idx].ts_in = ts_in
        out_buf[idx].ts_out = ts_out
        
        out_hdr.tail = tail + 1

    cdef void process_order(self, Order* order, Execution* out_buf, RingBufferHeader* out_hdr):
        cdef uint32_t match_size = 0
        cdef uint64_t match_price = 0
        cdef OrderNode* curr
        cdef OrderNode* prev
        cdef int level_idx
        cdef int i, j
        
        if order.side == 0: # BUY
            # Match against Asks (lowest to highest)
            while order.size > 0 and self.num_asks > 0:
                # Find min ask
                level_idx = 0
                for i in range(1, self.num_asks):
                    if self.asks[i].price < self.asks[level_idx].price:
                        level_idx = i
                
                if self.asks[level_idx].price > order.price:
                    break # Best ask is too expensive
                
                # We have a match!
                curr = self.asks[level_idx].head
                while curr != NULL and order.size > 0:
                    match_size = order.size if order.size < curr.order.size else curr.order.size
                    match_price = self.asks[level_idx].price
                    
                    order.size -= match_size
                    curr.order.size -= match_size
                    
                    # Generate executions for both sides
                    self.add_execution(out_buf, out_hdr, curr.order.order_id, match_price, match_size, curr.order.timestamp, get_time_ns())
                    self.add_execution(out_buf, out_hdr, order.order_id, match_price, match_size, order.timestamp, get_time_ns())
                    
                    if curr.order.size == 0:
                        # Remove node
                        self.asks[level_idx].head = curr.next
                        curr = curr.next
                    else:
                        break
                        
                if self.asks[level_idx].head == NULL:
                    # Remove price level
                    self.num_asks -= 1
                    self.asks[level_idx] = self.asks[self.num_asks]
                    
            # If still size left, add to bids
            if order.size > 0:
                level_idx = -1
                for i in range(self.num_bids):
                    if self.bids[i].price == order.price:
                        level_idx = i
                        break
                if level_idx == -1:
                    level_idx = self.num_bids
                    self.num_bids += 1
                    self.bids[level_idx].price = order.price
                    self.bids[level_idx].head = NULL
                    self.bids[level_idx].tail = NULL
                
                curr = self.alloc_node(order)
                if curr != NULL:
                    if self.bids[level_idx].head == NULL:
                        self.bids[level_idx].head = curr
                        self.bids[level_idx].tail = curr
                    else:
                        self.bids[level_idx].tail.next = curr
                        self.bids[level_idx].tail = curr

        else: # SELL
            # Match against Bids (highest to lowest)
            while order.size > 0 and self.num_bids > 0:
                # Find max bid
                level_idx = 0
                for i in range(1, self.num_bids):
                    if self.bids[i].price > self.bids[level_idx].price:
                        level_idx = i
                        
                if self.bids[level_idx].price < order.price:
                    break # Best bid is too cheap
                    
                # We have a match!
                curr = self.bids[level_idx].head
                while curr != NULL and order.size > 0:
                    match_size = order.size if order.size < curr.order.size else curr.order.size
                    match_price = self.bids[level_idx].price
                    
                    order.size -= match_size
                    curr.order.size -= match_size
