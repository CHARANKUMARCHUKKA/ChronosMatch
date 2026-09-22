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
