# Zero-Copy IPC Synchronization Protocols

## 1. Shared Memory Architecture

ChronosMatch implements inter-process communication using **Windows Named Shared Memory** via Python's built-in `mmap` module:

```python
# Fileno=-1 allocates memory backed by system pagefile (anonymous RAM)
# tagname binds the mapping into Windows Object Manager global namespace
mm = mmap.mmap(-1, total_size, tagname=tagname)
```

The memory layout consists of a contiguous block divided into two regions:
1. **Control Header (24 bytes):** Contains `head`, `tail`, and `capacity` metadata.
2. **Payload Ring Buffer (`item_size * capacity` bytes):** Contiguous array of packed C structs (`Order` or `Execution`).

---

## 2. Lock-Free Single-Producer Single-Consumer (SPSC) Pattern

The primary high-frequency trading pipeline operates as a **Lock-Free SPSC queue**:

```
+-------------------------------------------------------------------------+
|                         SHARED MEMORY SEGMENT                           |
|  +--------------------+-----------------------------------------------+ |
|  | Header (24 Bytes)  | Data Buffer (65,536 Slots * 32/48 Bytes)      | |
|  | [head | tail | cap]| [Slot 0 | Slot 1 | ... | Slot 65535]          | |
|  +--------------------+-----------------------------------------------+ |
+-------------------------------------------------------------------------+
          ^            ^
          |            |
     Read by Engine   Written by Feed Producer
```

### 2.1 Synchronization Rules
- **Producer writes payload first:** The producer copies the struct into `data_array[tail % capacity]`, then increments `header.tail`.
- **Consumer reads payload before advancing head:** The consumer detects available orders when `tail > head`, processes the order at `head % capacity`, and advances `header.head`.
- **Atomic Operations on x86_64:** On 64-bit architectures, aligned 64-bit integer loads and stores (`head` and `tail`) are atomic at the hardware level.

### 2.2 Backpressure & Flow Control
When order arrival rates outpace engine consumption, the ring buffer prevents slot overwriting:
```python
if tail + batch_size - head >= capacity:
    # Buffer full: yield execution to allow consumer to drain
    await asyncio.sleep(0.001)
    continue
```

---

## 3. Multi-Producer Synchronization (Stress Testing)

When multiple producer processes write to the same inbound ring buffer concurrently:
- An IPC synchronization lock (`multiprocessing.Lock`) or atomic fetch-and-add is required when reserving buffer indices.
- Once an index ticket is reserved, producers can write their payload into their respective slots concurrently without memory corruption.

---

## 4. Python Buffer Protocol & Resource Lifecycle

When mapping C structs over shared memory with `ctypes.Structure.from_buffer(mm, offset)`, Python creates internal buffer views. To prevent `BufferError: cannot close exported pointers exist` on shutdown:
- All struct instances and view references must be cleared (`order = None; del header, data_array`) before invoking `mm.close()`.
