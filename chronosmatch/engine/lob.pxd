from libc.stdint cimport uint8_t, uint32_t, uint64_t

cdef packed struct Order:
    uint64_t order_id
    uint64_t price
    uint32_t size
    uint8_t side
    uint8_t pad[3]
    uint64_t timestamp

cdef packed struct Execution:
