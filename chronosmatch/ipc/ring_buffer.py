import ctypes
import mmap
import os

# Action types
ACTION_NEW = 0
ACTION_CANCEL = 1

# Side types
SIDE_BUY = 0
SIDE_SELL = 1

# Execution types
EXEC_FILL = 0
EXEC_CANCELED = 1

# Ensure memory structures have exact alignment with C/Cython
class Order(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("order_id", ctypes.c_uint64),
        ("price", ctypes.c_uint64),
        ("size", ctypes.c_uint32),
        ("side", ctypes.c_uint8),    # 0 for Buy, 1 for Sell
        ("action", ctypes.c_uint8),  # 0 for New, 1 for Cancel
        ("pad", ctypes.c_uint8 * 2), # 2 bytes padding to align timestamp to 8 bytes
        ("timestamp", ctypes.c_uint64),
    ] # Total: 32 bytes

class Execution(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("exec_id", ctypes.c_uint64),
        ("order_id", ctypes.c_uint64),
        ("price", ctypes.c_uint64),
        ("size", ctypes.c_uint32),
        ("exec_type", ctypes.c_uint8), # 0 for Fill, 1 for Canceled
        ("pad", ctypes.c_uint8 * 3),   # 3 bytes padding to align ts_in
        ("ts_in", ctypes.c_uint64),
        ("ts_out", ctypes.c_uint64),
    ] # Total: 48 bytes

class RingBufferHeader(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("head", ctypes.c_uint64),
        ("tail", ctypes.c_uint64),
        ("capacity", ctypes.c_uint64),
    ] # Total: 24 bytes

def get_ring_buffer(tagname: str, struct_type, capacity: int, create: bool = False):
    """
    Creates or attaches to a named shared memory ring buffer.
    Uses Windows Named Shared Memory (fileno=-1 with tagname) or POSIX anonymous memory.
    """
    header_size = ctypes.sizeof(RingBufferHeader)
    item_size = ctypes.sizeof(struct_type)
    total_size = header_size + (item_size * capacity)
    
    # On Windows, mmap with fileno=-1 and a tagname creates/opens named shared memory
    mm = mmap.mmap(-1, total_size, tagname=tagname)
    
    header = RingBufferHeader.from_buffer(mm, 0)
    
    if create:
        header.head = 0
        header.tail = 0
        header.capacity = capacity
        
    array_type = struct_type * capacity
    data_array = array_type.from_buffer(mm, header_size)
    
    return mm, header, data_array
