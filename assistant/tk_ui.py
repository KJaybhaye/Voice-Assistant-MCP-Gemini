import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime
from queue import Queue
from collections import deque


class ConversationUI:
    def __init__(
        self,
        message_queue=Queue(),
        history=deque(maxlen=100),
        return_queue=None,
        ass_notification=Queue(),
    ):
        self.root = tk.Tk()
        self.root.title("Voice Assistant Conversation")
        self.root.geometry("800x600")

        style = ttk.Style()
        style.theme_use("clam")

        self.root.configure(bg="#191818")

        self.message_queue = message_queue
        self.return_queue = return_queue
        self.ass_notification = ass_notification
        self.setup_ui(history)
        self.poll_queue()

    def setup_ui(self, history):
        main_frame = tk.Frame(self.root, bg="#191818")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.status_text = tk.StringVar()
        self.status_text.set("Connecting")
        self.status_label = tk.Label(
            main_frame,
            # text="Connecting",
            textvariable=self.status_text,
            font=("Arial", 10),
            bg="#165919",
            fg="#F4E5E5",
            relief=tk.RIDGE,
            padx=10,
            pady=5,
        )
        self.status_label.pack(fill=tk.X, pady=(0, 10))

        conv_frame = tk.Frame(main_frame, bg="#302929", relief=tk.SUNKEN, bd=2)
        conv_frame.pack(fill=tk.BOTH, expand=True)

        self.conversation_display = scrolledtext.ScrolledText(
            conv_frame,
            wrap=tk.WORD,
            font=("Arial", 11),
            bg="#302929",
            fg="#C02424",
            padx=10,
            pady=10,
            state=tk.DISABLED,
            height=20,
        )
        self.conversation_display.pack(fill=tk.BOTH, expand=True)

        self.conversation_display.tag_config(
            "user_role", foreground="#4197EC", font=("Arial", 11, "bold")
        )
        self.conversation_display.tag_config(
            "assistant_role", foreground="#C86EEE", font=("Arial", 11, "bold")
        )
        self.conversation_display.tag_config(
            "user_msg",
            foreground="#F4E5E5",
            lmargin1=20,
            lmargin2=20,
        )
        self.conversation_display.tag_config(
            "assistant_msg", foreground="#F4E5E5", lmargin1=20, lmargin2=20
        )
        self.conversation_display.tag_config(
            "timestamp", foreground="#F4E5E5", font=("Arial", 9)
        )

        input_frame = tk.Frame(main_frame, bg="#433e3e")
        input_frame.pack(fill=tk.X, pady=(10, 5))
        self.text_input = tk.Text(
            input_frame,
            height=2,
            width=80,
            background="#302929",
            fg="#F4E5E5",
        )
        self.text_input.pack(side=tk.LEFT, padx=(10, 10))

        self.send_button = tk.Button(
            input_frame,
            text="Send Query",
            command=self.send_input,
            bg="#f44336",
            fg="#F4E5E5",
            font=("Arial", 10),
            padx=5,
            pady=5,
            relief=tk.RAISED,
            cursor="hand2",
        )
        self.send_button.pack(side=tk.RIGHT, padx=(0, 0))

        button_frame = tk.Frame(main_frame, bg="#433e3e")
        button_frame.pack(fill=tk.X, pady=(10, 0))
        self.clear_button = tk.Button(
            button_frame,
            text="Clear Display",
            command=self.clear_display,
            bg="#f44336",
            fg="#F4E5E5",
            font=("Arial", 10),
            padx=20,
            pady=5,
            relief=tk.RAISED,
            cursor="hand2",
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))

        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.message_counter = tk.Label(
            button_frame,
            text="Messages: 0",
            font=("Arial", 10),
            fg="#F4E5E5",
            bg="#3f2b2b",
        )
        self.message_counter.pack(side=tk.RIGHT, padx=20)

        # Load existing history
        self.load_history(history)

    def load_history(self, history):
        """Load existing conversation history"""
        for message in history:
            self.add_message_to_display(message)

    def add_message_to_display(self, message):
        """Add a single message to the display"""
        self.conversation_display.config(state=tk.NORMAL)
        role = message["role"].lower()

        timestamp = datetime.fromisoformat(message["timestamp"]).strftime("%H:%M:%S")

        if role == "user":
            self.conversation_display.insert(tk.END, "👤 User ", "user_role")
        else:
            self.conversation_display.insert(tk.END, "🤖 Assistant ", "assistant_role")

        # Add timestamp
        self.conversation_display.insert(tk.END, f"[{timestamp}]\n", "timestamp")

        # Add message content
        tag = "user_msg" if role == "user" else "assistant_msg"
        self.conversation_display.insert(tk.END, f"{message['content']}\n\n", tag)

        # Auto-scroll to bottom if enabled
        if self.auto_scroll_var.get():
            self.conversation_display.see(tk.END)

        self.conversation_display.config(state=tk.DISABLED)

        # Update message counter
        current_count = (
            len(self.conversation_display.get(1.0, tk.END).split("\n\n")) - 1
        )
        self.message_counter.config(text=f"Messages: {current_count}")

    def poll_queue(self):
        """Poll the message queue for new messages"""
        while not self.message_queue.empty():
            message = self.message_queue.get()
            self.add_message_to_display(message)

        self.update_ui()
        self.root.after(1000, self.poll_queue)

    def update_ui(self):
        while not self.ass_notification.empty():
            message = self.ass_notification.get()
            self.status_text.set(message)

    def clear_display(self):
        """Clear the conversation display"""
        self.conversation_display.config(state=tk.NORMAL)
        self.conversation_display.delete(1.0, tk.END)
        self.conversation_display.config(state=tk.DISABLED)
        self.message_counter.config(text="Messages: 0")

    def send_input(self):
        """Send input to caller"""
        query = self.text_input.get("1.0", "end-1c")
        if self.return_queue is not None:
            self.return_queue.put(query.strip())
        self.text_input.delete("1.0", "end-1c")

    def run(self):
        """Start the tkinter main loop"""
        self.root.mainloop()
