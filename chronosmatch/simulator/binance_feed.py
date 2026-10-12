import asyncio
import json
import time
import websockets
from chronosmatch.ipc.ring_buffer import (
    get_ring_buffer,
    Order,
    ACTION_NEW,
    SIDE_BUY,
    SIDE_SELL
)

async def run_binance_feed(tagname="ChronosMatchInbound", capacity=65536):
    """
    Connects to live Binance BTC/USDT WebSocket trade stream and ingests
    micro-ticks directly into the zero-copy shared memory ring buffer.
    Prices are scaled by 100 into fixed-point integer cents.
    """
    print("[BINANCE FEED] Initializing live connection to wss://stream.binance.com:9443/ws/btcusdt@trade...")
    mm, header, data_array = get_ring_buffer(tagname, Order, capacity, create=True)
    
    uri = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    order_id = 1
    
    try:
        while True:
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as websocket:
                    print("[BINANCE FEED] Connected! Streaming real-time BTC/USDT trades into IPC Buffer...")
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        # Fixed-point integer scaling: price in cents ($100.25 -> 10025)
                        price = int(round(float(data['p']) * 100))
                        size = max(1, int(float(data['q']) * 1000))
                        side = SIDE_SELL if data['m'] else SIDE_BUY
                        
                        tail = header.tail
                        head = header.head
                        
                        # Backpressure flow control
                        if tail + 1 - head >= capacity:
                            await asyncio.sleep(0.001)
                            continue
                        
                        idx = tail % capacity
                        order = data_array[idx]
                        
                        order.order_id = order_id
                        order.price = price
                        order.size = size
                        order.side = side
                        order.action = ACTION_NEW
                        order.timestamp = time.perf_counter_ns()
                        
                        header.tail = tail + 1
                        order_id += 1
            except asyncio.CancelledError:
                print("[BINANCE FEED] Feed task cancelled. Shutting down...")
                break
            except Exception as e:
                print(f"[BINANCE FEED] Connection lost: {e}. Reconnecting in 2 seconds...")
                await asyncio.sleep(2)
    finally:
        del header, data_array
        mm.close()

if __name__ == "__main__":
    asyncio.run(run_binance_feed())
