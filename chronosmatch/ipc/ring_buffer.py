import ctypes
import mmap
import os

# Ensure memory structures have exact alignment with C/Cython
class Order(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("order_id", ctypes.c_uint64),
        ("price", ctypes.c_uint64),
        ("size", ctypes.c_uint32),
        ("side", ctypes.c_uint8),  # 0 for Buy, 1 for Sell
        ("pad", ctypes.c_uint8 * 3), # Padding to align timestamp to 8 bytes
        ("timestamp", ctypes.c_uint64),
    ] # Total: 32 bytes

class Execution(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("exec_id", ctypes.c_uint64),
        ("order_id", ctypes.c_uint64),
        ("price", ctypes.c_uint64),
        ("size", ctypes.c_uint32),
        ("pad", ctypes.c_uint32), # Padding to align
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
    """
    header_size = ctypes.sizeof(RingBufferHeader)
