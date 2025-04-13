import asyncio
import logging
import queue
from typing import Optional
from aiohttp import web
from pathlib import Path

logger = logging.getLogger(__name__)

# Shared queue to send the connected wallet address back to the main thread
# This should be the same queue instance used by the main application
wallet_update_queue: Optional[queue.Queue] = None

# Path to the HTML file
HTML_FILE_PATH = Path(__file__).parent / "connect.html"

async def handle_connect(request: web.Request) -> web.Response:
    """Serves the connect.html file."""
    logger.info("Serving connect.html")
    try:
        return web.FileResponse(HTML_FILE_PATH)
    except Exception as e:
        logger.error(f"Error serving connect.html: {e}", exc_info=True)
        return web.Response(text="Error loading connection page.", status=500)

async def handle_callback(request: web.Request) -> web.Response:
    """Receives the wallet address from the JavaScript callback."""
    if request.method != "POST":
        logger.warning("Received non-POST request on /callback")
        return web.Response(text="Method Not Allowed", status=405)
        
    try:
        data = await request.json()
        wallet_address = data.get("walletAddress")
        
        if not wallet_address:
            logger.warning("Received callback without walletAddress.")
            return web.json_response({"status": "error", "message": "Missing walletAddress"}, status=400)

        logger.info(f"Received wallet address via callback: {wallet_address}")
        
        if wallet_update_queue:
            try:
                # Send address back to the main thread via the queue
                wallet_update_queue.put_nowait({"type": "wallet_update", "address": wallet_address})
                logger.info("Wallet address placed in update queue.")
                return web.json_response({"status": "success", "message": "Address received"})
            except queue.Full:
                logger.error("Wallet update queue is full. Cannot send address.")
                return web.json_response({"status": "error", "message": "Queue full"}, status=500)
            except Exception as qe:
                 logger.error(f"Error putting wallet address into queue: {qe}")
                 return web.json_response({"status": "error", "message": "Internal server error"}, status=500)
        else:
            logger.error("Wallet update queue is not set in local_server.")
            return web.json_response({"status": "error", "message": "Server configuration error"}, status=500)

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from /callback request.")
        return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error handling callback: {e}", exc_info=True)
        return web.json_response({"status": "error", "message": "Internal server error"}, status=500)

async def start_local_server(host='127.0.0.1', port=51345, update_queue: queue.Queue = None):
    """Starts the aiohttp web server."""
    global wallet_update_queue
    if update_queue is None:
         logger.error("Update queue must be provided to start_local_server.")
         raise ValueError("Update queue is required.")
         
    wallet_update_queue = update_queue
    
    app = web.Application()
    app.router.add_get('/connect', handle_connect)
    app.router.add_post('/callback', handle_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    
    try:
        await site.start()
        logger.info(f"Local web server started at http://{host}:{port}")
        # Keep server running until stopped externally (e.g., by cancelling the task)
        # We need a way to signal shutdown, asyncio.Event is good for this
        shutdown_event = asyncio.Event()
        # Store the event so it can be set from outside
        app['shutdown_event'] = shutdown_event 
        await shutdown_event.wait() 

    except OSError as e:
         logger.error(f"Failed to start local server on {host}:{port}. Port likely in use. Error: {e}")
         # Re-raise or handle appropriately
         raise 
    except Exception as e:
        logger.error(f"Error during local server execution: {e}", exc_info=True)
    finally:
        logger.info("Shutting down local web server...")
        await runner.cleanup()
        logger.info("Local web server stopped.")

async def stop_local_server(app: web.Application):
     """Signals the running server to shut down."""
     if 'shutdown_event' in app and not app['shutdown_event'].is_set():
          logger.info("Signalling local server shutdown...")
          app['shutdown_event'].set()
     else:
          logger.warning("Shutdown event not found or already set for local server.")

# Example of how to run this server (would typically be run in a thread from main.py)
# async def main():
#     q = queue.Queue()
#     server_task = asyncio.create_task(start_local_server(port=51345, update_queue=q))
#     # Keep it running for a bit or until stopped
#     await asyncio.sleep(60) 
#     # Get the app instance to signal stop (this is tricky across threads)
#     # Need a better way to manage the app/runner instance for shutdown
#     # await stop_local_server(???) 
#     await server_task 

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("Server stopped manually.")
