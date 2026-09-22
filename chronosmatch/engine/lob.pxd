from libc.stdint cimport uint8_t, uint32_t, uint64_t

cdef packed struct Order:
    uint64_t order_id
    uint64_t price
    uint32_t size
    uint8_t side
    uint8_t pad[3]
    uint64_t timestamp

cdef packed struct Execution:
    uint64_t exec_id
    uint64_t order_id
    uint64_t price
    uint32_t size
    uint32_t pad
    uint64_t ts_in
    uint64_t ts_out

cdef packed struct RingBufferHeader:
    uint64_t head
    uint64_t tail
    uint64_t capacity

# Nodes for the Limit Order Book linked lists
cdef struct OrderNode:
    Order order
    OrderNode* next

cdef struct PriceLevel:
    uint64_t price
    OrderNode* head
    OrderNode* tail
