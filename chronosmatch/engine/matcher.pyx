# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: initializedcheck=False

from libc.stdlib cimport malloc, free
from libc.string cimport memset
from libc.stdint cimport uint8_t, uint32_t, uint64_t
import time

from .lob cimport Order, Execution, RingBufferHeader, OrderNode, PriceLevel, OrderAction, ExecType, ACTION_NEW, ACTION_CANCEL, EXEC_FILL, EXEC_CANCELED

cdef inline uint64_t get_time_ns() noexcept:
    return <uint64_t>time.perf_counter_ns()

cdef class Matcher:
    cdef OrderNode* order_pool
    cdef uint32_t pool_capacity
    cdef uint32_t pool_index
    cdef OrderNode* free_list
    
    # Simple arrays for price levels
    cdef PriceLevel* bids
    cdef uint32_t num_bids
    cdef uint32_t max_bids
    
    cdef PriceLevel* asks
    cdef uint32_t num_asks
    cdef uint32_t max_asks
    
    cdef uint64_t execution_counter

    def __cinit__(self, uint32_t max_orders=1000000, uint32_t max_levels=10000):
        self.pool_capacity = max_orders
        self.order_pool = <OrderNode*>malloc(sizeof(OrderNode) * max_orders)
        self.pool_index = 0
        self.free_list = NULL
        
        self.bids = <PriceLevel*>malloc(sizeof(PriceLevel) * max_levels)
        self.asks = <PriceLevel*>malloc(sizeof(PriceLevel) * max_levels)
        self.num_bids = 0
        self.num_asks = 0
        self.max_bids = max_levels
        self.max_asks = max_levels
        self.execution_counter = 0

    def __dealloc__(self):
        if self.order_pool != NULL:
            free(self.order_pool)
        if self.bids != NULL:
            free(self.bids)
        if self.asks != NULL:
            free(self.asks)

    cdef OrderNode* alloc_node(self, Order* order) noexcept:
        cdef OrderNode* node = NULL
        # 1. Pop from reusable free-list if available (O(1) recycling)
        if self.free_list != NULL:
            node = self.free_list
            self.free_list = node.next
        # 2. Otherwise allocate from pre-warmed pool
        elif self.pool_index < self.pool_capacity:
            node = &self.order_pool[self.pool_index]
            self.pool_index += 1
        else:
            return NULL # Pool exhausted

        node.order = order[0]
        node.next = NULL
        node.prev = NULL
        return node

    cdef void free_node(self, OrderNode* node) noexcept:
        if node != NULL:
            node.next = self.free_list
            node.prev = NULL
            self.free_list = node

    cdef void add_execution(self, Execution* out_buf, RingBufferHeader* out_hdr, uint64_t order_id, uint64_t price, uint32_t size, uint8_t exec_type, uint64_t ts_in, uint64_t ts_out) noexcept:
        cdef uint64_t tail = out_hdr.tail
        cdef uint64_t cap = out_hdr.capacity
        cdef uint64_t idx = tail % cap
        
        self.execution_counter += 1
        out_buf[idx].exec_id = self.execution_counter
        out_buf[idx].order_id = order_id
        out_buf[idx].price = price
        out_buf[idx].size = size
        out_buf[idx].exec_type = exec_type
        out_buf[idx].ts_in = ts_in
        out_buf[idx].ts_out = ts_out
        
        out_hdr.tail = tail + 1

    cdef void process_order(self, Order* order, Execution* out_buf, RingBufferHeader* out_hdr) noexcept:
        cdef uint32_t match_size = 0
        cdef uint64_t match_price = 0
        cdef OrderNode* curr
        cdef OrderNode* dead_node
        cdef int level_idx
        cdef int i
        
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
                
                # Match against orders at this price level
                curr = self.asks[level_idx].head
                while curr != NULL and order.size > 0:
                    match_size = order.size if order.size < curr.order.size else curr.order.size
                    match_price = self.asks[level_idx].price
                    
                    order.size -= match_size
                    curr.order.size -= match_size
                    
                    # Generate executions for both sides (FILL)
                    self.add_execution(out_buf, out_hdr, curr.order.order_id, match_price, match_size, EXEC_FILL, curr.order.timestamp, get_time_ns())
                    self.add_execution(out_buf, out_hdr, order.order_id, match_price, match_size, EXEC_FILL, order.timestamp, get_time_ns())
                    
                    if curr.order.size == 0:
                        dead_node = curr
                        self.asks[level_idx].head = curr.next
                        curr = curr.next
                        self.free_node(dead_node) # Recycle node memory
                    else:
                        break
                        
                if self.asks[level_idx].head == NULL:
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
                    
                curr = self.bids[level_idx].head
                while curr != NULL and order.size > 0:
                    match_size = order.size if order.size < curr.order.size else curr.order.size
                    match_price = self.bids[level_idx].price
                    
                    order.size -= match_size
                    curr.order.size -= match_size
                    
                    self.add_execution(out_buf, out_hdr, curr.order.order_id, match_price, match_size, EXEC_FILL, curr.order.timestamp, get_time_ns())
                    self.add_execution(out_buf, out_hdr, order.order_id, match_price, match_size, EXEC_FILL, order.timestamp, get_time_ns())
                    
                    if curr.order.size == 0:
                        dead_node = curr
                        self.bids[level_idx].head = curr.next
                        curr = curr.next
                        self.free_node(dead_node) # Recycle node memory
                    else:
                        break
                
                if self.bids[level_idx].head == NULL:
                    self.num_bids -= 1
                    self.bids[level_idx] = self.bids[self.num_bids]
                    
            if order.size > 0:
                level_idx = -1
                for i in range(self.num_asks):
                    if self.asks[i].price == order.price:
                        level_idx = i
                        break
                if level_idx == -1:
                    level_idx = self.num_asks
                    self.num_asks += 1
                    self.asks[level_idx].price = order.price
                    self.asks[level_idx].head = NULL
                    self.asks[level_idx].tail = NULL
                    
                curr = self.alloc_node(order)
                if curr != NULL:
                    if self.asks[level_idx].head == NULL:
                        self.asks[level_idx].head = curr
                        self.asks[level_idx].tail = curr
                    else:
                        self.asks[level_idx].tail.next = curr
                        self.asks[level_idx].tail = curr

    def run(self, size_t in_buf_addr, size_t in_hdr_addr, size_t out_buf_addr, size_t out_hdr_addr):
        cdef Order* in_buf = <Order*>in_buf_addr
        cdef RingBufferHeader* in_hdr = <RingBufferHeader*>in_hdr_addr
        cdef Execution* out_buf = <Execution*>out_buf_addr
        cdef RingBufferHeader* out_hdr = <RingBufferHeader*>out_hdr_addr
        
        cdef uint64_t head = in_hdr.head
        cdef uint64_t cap = in_hdr.capacity
        cdef Order* order
        
        print("Cython Matcher engine started. Polling ring buffer...")
        
        while True:
            if in_hdr.tail > head:
                order = &in_buf[head % cap]
                # Special exit condition: order_id == 0 means STOP
                if order.order_id == 0:
                    print("Received STOP signal.")
                    break
                self.process_order(order, out_buf, out_hdr)
                head += 1
                in_hdr.head = head
            else:
                pass
