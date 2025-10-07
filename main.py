import asyncio
from collections import deque
from queue import Queue
import threading
import sys
import warnings

if not sys.warnoptions:
    warnings.simplefilter("ignore")

from assistant.assistant import Assistant
from assistant.client import MCPClient
from assistant.tk_ui import ConversationUI


def run_ui():
    """Function to run UI in separate thread"""
    ui = ConversationUI(
        message_queue, conversation_history, return_queue, notification_queue
    )
    ui.run()


async def main() -> None:
    try:
        await client.connect_to_server()
        await client.init_chat()

        bg_thread = threading.Thread(
            target=assistant.start_background_chat, daemon=True
        )
        bg_thread.start()
        ui_thread = threading.Thread(target=run_ui, daemon=True)
        ui_thread.start()

        # Keep main async loop running
        await asyncio.Event().wait()

    finally:
        await client.cleanup()


if __name__ == "__main__":
    client = MCPClient()
    message_queue = Queue()
    conversation_history = deque(maxlen=100)
    return_queue = Queue()
    notification_queue = Queue()

    assistant = Assistant(
        client,
        message_queue,
        conversation_history,
        return_queue,
        ui_notification=notification_queue,
    )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
