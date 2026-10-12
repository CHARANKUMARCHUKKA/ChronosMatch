from libc.stdint cimport uint8_t, uint32_t, uint64_t

# Action types
# 0: NEW, 1: CANCEL
cdef enum OrderAction:
    ACTION_NEW = 0
    ACTION_CANCEL = 1

# Execution types
# 0: FILL, 1: CANCELED
cdef enum ExecType:
    EXEC_FILL = 0
    EXEC_CANCELED = 1

cdef packed struct Order:
    uint64_t order_id
    uint64_t price
    uint32_t size
    uint8_t side          # 0: BUY, 1: SELL
    uint8_t action        # 0: NEW, 1: CANCEL
    uint8_t pad[2]        # 2 bytes alignment padding
    uint64_t timestamp

cdef packed struct Execution:
    uint64_t exec_id
    uint64_t order_id
    uint64_t price
    uint32_t size
    uint8_t exec_type     # 0: FILL, 1: CANCELED
    uint8_t pad[3]        # 3 bytes alignment padding
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
    OrderNode* prev

cdef struct PriceLevel:
    uint64_t price
    OrderNode* head
    OrderNode* tail
    uint32_t order_count
    uint64_t total_volume
