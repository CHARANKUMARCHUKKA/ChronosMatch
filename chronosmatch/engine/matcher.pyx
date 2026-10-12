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
    
    # Sorted arrays for price levels:
    # Bids sorted descending (highest price at index 0)
    cdef PriceLevel* bids
    cdef uint32_t num_bids
    cdef uint32_t max_bids
    
    # Asks sorted ascending (lowest price at index 0)
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

    def get_num_bids(self):
        return self.num_bids
        
    def get_num_asks(self):
        return self.num_asks
        
    def get_best_bid(self):
        if self.num_bids > 0:
            return self.bids[0].price
        return 0
        
    def get_best_ask(self):
        if self.num_asks > 0:
            return self.asks[0].price
        return 0
        
    def get_pool_index(self):
        return self.pool_index
        
    def has_free_nodes(self):
        return self.free_list != NULL

    cdef OrderNode* alloc_node(self, Order* order) noexcept:
        cdef OrderNode* node = NULL
        if self.free_list != NULL:
            node = self.free_list
            self.free_list = node.next
        elif self.pool_index < self.pool_capacity:
            node = &self.order_pool[self.pool_index]
            self.pool_index += 1
        else:
            return NULL

        node.order = order[0]
        node.next = NULL
        node.prev = NULL
        return node

    cdef void free_node(self, OrderNode* node) noexcept:
        if node != NULL:
            node.next = self.free_list
            node.prev = NULL
            self.free_list = node

    cdef int find_ask_level(self, uint64_t price) noexcept:
        cdef int low = 0
        cdef int high = <int>self.num_asks - 1
        cdef int mid
        while low <= high:
            mid = (low + high) >> 1
            if self.asks[mid].price == price:
                return mid
            elif self.asks[mid].price < price:
                low = mid + 1
            else:
                high = mid - 1
        return -1

    cdef int insert_ask_level(self, uint64_t price) noexcept:
        if self.num_asks >= self.max_asks:
            return -1
        cdef int low = 0
        cdef int high = <int>self.num_asks - 1
        cdef int mid
        while low <= high:
            mid = (low + high) >> 1
            if self.asks[mid].price == price:
                return mid
            elif self.asks[mid].price < price:
                low = mid + 1
            else:
                high = mid - 1
        cdef int ins = low
        cdef int i
        for i in range(<int>self.num_asks, ins, -1):
            self.asks[i] = self.asks[i - 1]
        self.num_asks += 1
        self.asks[ins].price = price
        self.asks[ins].head = NULL
        self.asks[ins].tail = NULL
        self.asks[ins].order_count = 0
        self.asks[ins].total_volume = 0
        return ins

    cdef void delete_ask_level(self, int idx) noexcept:
        cdef int i
        self.num_asks -= 1
        for i in range(idx, <int>self.num_asks):
            self.asks[i] = self.asks[i + 1]

    cdef int find_bid_level(self, uint64_t price) noexcept:
        cdef int low = 0
        cdef int high = <int>self.num_bids - 1
        cdef int mid
        while low <= high:
            mid = (low + high) >> 1
            if self.bids[mid].price == price:
                return mid
            elif self.bids[mid].price > price:
                low = mid + 1
            else:
                high = mid - 1
        return -1

    cdef int insert_bid_level(self, uint64_t price) noexcept:
        if self.num_bids >= self.max_bids:
            return -1
        cdef int low = 0
        cdef int high = <int>self.num_bids - 1
        cdef int mid
        while low <= high:
            mid = (low + high) >> 1
            if self.bids[mid].price == price:
                return mid
            elif self.bids[mid].price > price:
                low = mid + 1
            else:
                high = mid - 1
        cdef int ins = low
        cdef int i
        for i in range(<int>self.num_bids, ins, -1):
            self.bids[i] = self.bids[i - 1]
        self.num_bids += 1
        self.bids[ins].price = price
        self.bids[ins].head = NULL
        self.bids[ins].tail = NULL
        self.bids[ins].order_count = 0
        self.bids[ins].total_volume = 0
        return ins

    cdef void delete_bid_level(self, int idx) noexcept:
        cdef int i
        self.num_bids -= 1
        for i in range(idx, <int>self.num_bids):
            self.bids[i] = self.bids[i + 1]

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

    cdef void cancel_order(self, Order* order, Execution* out_buf, RingBufferHeader* out_hdr) noexcept:
        cdef OrderNode* curr
        cdef int level_idx = -1
        cdef int i
        
        # Check Bids if BUY or unspecified
        if order.side == 0:
            if order.price > 0:
                level_idx = self.find_bid_level(order.price)
                if level_idx != -1:
                    curr = self.bids[level_idx].head
                    while curr != NULL:
                        if curr.order.order_id == order.order_id:
                            if curr.prev != NULL:
                                curr.prev.next = curr.next
                            else:
                                self.bids[level_idx].head = curr.next
                            if curr.next != NULL:
                                curr.next.prev = curr.prev
                            else:
                                self.bids[level_idx].tail = curr.prev
                            
                            self.add_execution(out_buf, out_hdr, curr.order.order_id, curr.order.price, curr.order.size, EXEC_CANCELED, curr.order.timestamp, get_time_ns())
                            self.free_node(curr)
                            if self.bids[level_idx].head == NULL:
                                self.delete_bid_level(level_idx)
                            return
                        curr = curr.next
            else:
                for i in range(<int>self.num_bids):
                    curr = self.bids[i].head
                    while curr != NULL:
                        if curr.order.order_id == order.order_id:
                            if curr.prev != NULL:
                                curr.prev.next = curr.next
                            else:
                                self.bids[i].head = curr.next
                            if curr.next != NULL:
                                curr.next.prev = curr.prev
                            else:
                                self.bids[i].tail = curr.prev
                            
                            self.add_execution(out_buf, out_hdr, curr.order.order_id, curr.order.price, curr.order.size, EXEC_CANCELED, curr.order.timestamp, get_time_ns())
                            self.free_node(curr)
                            if self.bids[i].head == NULL:
                                self.delete_bid_level(i)
                            return
                        curr = curr.next
        else:
            # Check Asks
            if order.price > 0:
                level_idx = self.find_ask_level(order.price)
                if level_idx != -1:
                    curr = self.asks[level_idx].head
                    while curr != NULL:
                        if curr.order.order_id == order.order_id:
                            if curr.prev != NULL:
                                curr.prev.next = curr.next
                            else:
                                self.asks[level_idx].head = curr.next
                            if curr.next != NULL:
                                curr.next.prev = curr.prev
                            else:
                                self.asks[level_idx].tail = curr.prev
                            
                            self.add_execution(out_buf, out_hdr, curr.order.order_id, curr.order.price, curr.order.size, EXEC_CANCELED, curr.order.timestamp, get_time_ns())
                            self.free_node(curr)
                            if self.asks[level_idx].head == NULL:
                                self.delete_ask_level(level_idx)
                            return
                        curr = curr.next
            else:
                for i in range(<int>self.num_asks):
                    curr = self.asks[i].head
                    while curr != NULL:
                        if curr.order.order_id == order.order_id:
                            if curr.prev != NULL:
                                curr.prev.next = curr.next
                            else:
                                self.asks[i].head = curr.next
                            if curr.next != NULL:
                                curr.next.prev = curr.prev
                            else:
                                self.asks[i].tail = curr.prev
                            
                            self.add_execution(out_buf, out_hdr, curr.order.order_id, curr.order.price, curr.order.size, EXEC_CANCELED, curr.order.timestamp, get_time_ns())
                            self.free_node(curr)
                            if self.asks[i].head == NULL:
                                self.delete_ask_level(i)
                            return
                        curr = curr.next

    cdef void process_order(self, Order* order, Execution* out_buf, RingBufferHeader* out_hdr) noexcept:
        cdef uint32_t match_size = 0
        cdef uint64_t match_price = 0
        cdef OrderNode* curr
        cdef OrderNode* dead_node
        cdef int level_idx
        
        if order.action == ACTION_CANCEL:
            self.cancel_order(order, out_buf, out_hdr)
            return

        if order.side == 0: # BUY
            while order.size > 0 and self.num_asks > 0:
                if self.asks[0].price > order.price:
                    break
                
                curr = self.asks[0].head
                while curr != NULL and order.size > 0:
                    match_size = order.size if order.size < curr.order.size else curr.order.size
                    match_price = self.asks[0].price
                    
                    order.size -= match_size
                    curr.order.size -= match_size
                    
                    self.add_execution(out_buf, out_hdr, curr.order.order_id, match_price, match_size, EXEC_FILL, curr.order.timestamp, get_time_ns())
                    self.add_execution(out_buf, out_hdr, order.order_id, match_price, match_size, EXEC_FILL, order.timestamp, get_time_ns())
                    
                    if curr.order.size == 0:
                        dead_node = curr
                        self.asks[0].head = curr.next
                        if self.asks[0].head != NULL:
                            self.asks[0].head.prev = NULL
                        else:
                            self.asks[0].tail = NULL
                        curr = curr.next
                        self.free_node(dead_node)
                    else:
                        break
                        
                if self.asks[0].head == NULL:
                    self.delete_ask_level(0)
                    
            if order.size > 0:
                level_idx = self.insert_bid_level(order.price)
                if level_idx != -1:
                    curr = self.alloc_node(order)
                    if curr != NULL:
                        if self.bids[level_idx].head == NULL:
                            self.bids[level_idx].head = curr
                            self.bids[level_idx].tail = curr
                        else:
                            curr.prev = self.bids[level_idx].tail
                            self.bids[level_idx].tail.next = curr
                            self.bids[level_idx].tail = curr

        else: # SELL
            while order.size > 0 and self.num_bids > 0:
                if self.bids[0].price < order.price:
                    break
                    
                curr = self.bids[0].head
                while curr != NULL and order.size > 0:
                    match_size = order.size if order.size < curr.order.size else curr.order.size
                    match_price = self.bids[0].price
                    
                    order.size -= match_size
                    curr.order.size -= match_size
                    
                    self.add_execution(out_buf, out_hdr, curr.order.order_id, match_price, match_size, EXEC_FILL, curr.order.timestamp, get_time_ns())
                    self.add_execution(out_buf, out_hdr, order.order_id, match_price, match_size, EXEC_FILL, order.timestamp, get_time_ns())
                    
                    if curr.order.size == 0:
                        dead_node = curr
                        self.bids[0].head = curr.next
                        if self.bids[0].head != NULL:
                            self.bids[0].head.prev = NULL
                        else:
                            self.bids[0].tail = NULL
                        curr = curr.next
                        self.free_node(dead_node)
                    else:
                        break
                
                if self.bids[0].head == NULL:
                    self.delete_bid_level(0)
                    
            if order.size > 0:
                level_idx = self.insert_ask_level(order.price)
                if level_idx != -1:
                    curr = self.alloc_node(order)
                    if curr != NULL:
                        if self.asks[level_idx].head == NULL:
                            self.asks[level_idx].head = curr
                            self.asks[level_idx].tail = curr
                        else:
                            curr.prev = self.asks[level_idx].tail
                            self.asks[level_idx].tail.next = curr
                            self.asks[level_idx].tail = curr

    def process_order_single(self, size_t order_addr, size_t out_buf_addr, size_t out_hdr_addr):
        cdef Order* order = <Order*>order_addr
        cdef Execution* out_buf = <Execution*>out_buf_addr
        cdef RingBufferHeader* out_hdr = <RingBufferHeader*>out_hdr_addr
        self.process_order(order, out_buf, out_hdr)

    def run(self, size_t in_buf_addr, size_t in_hdr_addr, size_t out_buf_addr, size_t out_hdr_addr):
        cdef Order* in_buf = <Order*>in_buf_addr
        cdef RingBufferHeader* in_hdr = <RingBufferHeader*>in_hdr_addr
        cdef Execution* out_buf = <Execution*>out_buf_addr
        cdef RingBufferHeader* out_hdr = <RingBufferHeader*>out_hdr_addr
        
        cdef uint64_t head = in_hdr.head
        cdef uint64_t cap = in_hdr.capacity
        cdef Order* order
        cdef int spin_count = 0
        
        print("Cython Matcher engine started. Polling ring buffer...")
        
        while True:
            if in_hdr.tail > head:
                order = &in_buf[head % cap]
                if order.order_id == 0:
                    print("Received STOP signal.")
                    break
                self.process_order(order, out_buf, out_hdr)
                head += 1
                in_hdr.head = head
                spin_count = 0
            else:
                spin_count += 1
                if spin_count > 5000:
                    time.sleep(0.0001)
                    spin_count = 0
