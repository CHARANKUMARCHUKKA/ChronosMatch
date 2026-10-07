import asyncio
import websockets
import json
import time
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Order

async def run_binance_feed(tagname="ChronosMatchInbound", capacity=65536):
    print("[BINANCE FEED] Initializing live connection to wss://stream.binance.com:9443/ws/btcusdt@trade...")
    mm, header, data_array = get_ring_buffer(tagname, Order, capacity, create=True)
    
    uri = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    order_id = 1
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("[BINANCE FEED] Connected! Streaming real-time BTC/USDT trades into IPC Buffer...")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Binance JSON Payload: 
                    # 'p': price, 'q': quantity, 'm': is_buyer_maker (True=Sell, False=Buy)
                    price = int(float(data['p']))
                    # Scale fractional Bitcoin (e.g. 0.05 BTC) to an integer (50) for the C-Struct
                    size = max(1, int(float(data['q']) * 1000))
                    side = 1 if data['m'] else 0
                    
                    tail = header.tail
                    head = header.head
                    
                    # Check space in ring buffer
                    if tail + 1 - head >= capacity:
                        await asyncio.sleep(0.001)
                        continue
                    
                    idx = tail % capacity
                    order = data_array[idx]
                    
                    order.order_id = order_id
                    order.price = price
                    order.size = size
                    order.side = side
                    order.timestamp = time.perf_counter_ns()
                    
                    header.tail = tail + 1
                    order_id += 1
        except Exception as e:
            print(f"[BINANCE FEED] Connection lost: {e}. Reconnecting in 2 seconds...")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run_binance_feed())

# [Data] Connecting to wss://stream.binance.com:9443

# [Data] Scaling fractional BTC sizes for uint32

# [IPC] Pushing live market data to ring buffer

# [Feed] Async websockets consumer for binance.com live trades

# [Feed] Fixed-point integer precision scaling for sub-satoshi trades
