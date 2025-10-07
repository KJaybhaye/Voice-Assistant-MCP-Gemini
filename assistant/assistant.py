import threading
from dotenv import load_dotenv
import speech_recognition as sr
from faster_whisper import WhisperModel
import asyncio
import os
import time
from collections import deque
from queue import Queue, Empty
from datetime import datetime
import torch
from assistant.client import MCPClient
from assistant.tk_ui import ConversationUI
from assistant.utils import get_query
import tomllib
from kokoro import KPipeline
import numpy as np
import pyaudio

load_dotenv()
with open("config.toml", "rb") as f:
    config = tomllib.load(f)["assistant"]

whisper_model = config["whisper_model"]
start_word = config["start_word"]
json_path = config["server_config"]

recognizer = sr.Recognizer()
microphone = sr.Microphone()

PIPELINE = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
finish_token = object()
speak_queue = Queue()
audio_buffer = np.array([], dtype=np.float32)

if torch.cuda.is_available():
    model = WhisperModel(model_size_or_path=whisper_model, device="cuda")
    print("Whisper is using Cuda")
else:
    num_cores = os.cpu_count()
    if not num_cores:
        num_cores = 8
    model = WhisperModel(
        model_size_or_path=whisper_model,
        device="cpu",
        cpu_threads=num_cores // 2,
        num_workers=num_cores // 2,
    )


class Assistant:
    def __init__(
        self,
        client,
        message_queue=Queue(),
        conversation_history=deque(maxlen=100),
        return_queue=Queue(),
        ws_manager=None,
        ui_notification=Queue(),
    ):
        self.started = False
        self.m_started = False
        self.message_queue = message_queue
        self.conversation_history = conversation_history
        self.return_queue = return_queue
        self.ws_manager = ws_manager
        self.ui_notification = ui_notification
        self.th = None
        self.client = client
        self.speak_queue = Queue(50)

    def listen(self, path: str = "audio.wav") -> str:
        """Listen for audio and save to file"""
        audio = recognizer.listen(microphone)
        with open(path, "wb") as f:
            f.write(audio.get_wav_data())  # type: ignore
        return path

    def transcribe(self, path: str = "audio.wav") -> str:
        """Recognize text from audio"""
        segs, _ = model.transcribe(
            path,
            beam_size=5,
            language="en",
            condition_on_previous_text=False,
            log_prob_threshold=0.4,
            no_speech_threshold=0.5,
            hotwords=f"{start_word}",
        )
        text = "".join([s.text for s in segs])
        return text

    async def process_query(self, query: str | None) -> None:
        """Get response from LLM-MCP client and process it"""
        if not query:
            return
        print("User: ", query)
        self.ui_notification.put("Processing")
        await self.add_to_history("user", query)
        response_text = self.client.process_query(query)
        await self.process_response(response_text)
        self.ui_notification.put("Listening")

    async def foreground_chat(self, query: str | None = None) -> None:
        """Voice chat loop"""
        if query:
            await self.process_query(query)
        else:
            self.ui_notification.put("Listening")
            speak("Hello User!")
            await self.add_to_history("assistant", "Hello User!")

        if self.stop_listening is not None:
            self.stop_listening(wait_for_stop=False)
        while True:
            if not self.return_queue.empty():
                query = self.return_queue.get()
            else:
                audio_p = self.listen()
                query = self.transcribe(audio_p)
            if query == "quit" or query == "exit":
                self.start_background_chat()
                print("foreground chat stopped!")
                return
            await self.process_query(query)

    def start_foreground_chat(self, recognizer, audio) -> None:
        """Callback that starts voice chat loop when start word is detected"""
        try:
            with open("audio.wav", "wb") as f:
                f.write(audio.get_wav_data())
            query = self.transcribe("audio.wav")
            # print("pp query", query)
            # to do
            query = get_query(query, start_word)
            if query is None:
                return
            asyncio.run(self.foreground_chat(query))
        except Exception as e:
            print(f"Error: {e}")

    def background_callback(self, recognizer, audio) -> None:
        """Experimental backgroun chat loop"""
        try:
            if not self.return_queue.empty():
                query = self.return_queue.get()
                if query == "Tars":
                    self.started = True
                    self.ui_notification.put("Listening.")
                    return
            else:
                with open("audio.wav", "wb") as f:
                    f.write(audio.get_wav_data())
                query = self.transcribe("audio.wav")
                if not self.started:
                    query = get_query(query, start_word)
                    if query:
                        self.started = True
                        self.ui_notification.put("Listening.")
                    return
            print("User: ", query)
            if query == "quit" or query == "exit":
                self.started = False
                return
            asyncio.run(self.add_to_history("user", query))
            response_text = self.client.process_query(query)
            asyncio.run(self.process_response(response_text))

            self.ui_notification.put("Listening")

        except Exception as e:
            print("Error in callback chat; {0}".format(e))

    def start_background_chat(self) -> None:
        """Start background listening"""
        if not self.m_started:
            print("Adjusting for ambient noise...")
            with microphone as source:
                recognizer.energy_threshold = 500
                recognizer.adjust_for_ambient_noise(source, 3)
                recognizer.dynamic_energy_threshold = True
            self.m_started = True
        print("Listening...")
        self.ui_notification.put(f"Say {start_word} to start conversation")
        self.stop_listening = recognizer.listen_in_background(
            microphone, self.start_foreground_chat
        )
        # self.stop_listening = recognizer.listen_in_background(m, self.background_callback)
        while True:
            time.sleep(0.5)

    async def add_to_history(self, role: str, content: str):
        """Add message to history and queue for UI update"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversation_history.append(message)
        self.message_queue.put(message)

        if self.ws_manager:
            await self.ws_manager.broadcast(message)

    async def generate_audio(self, response, f=None):
        """Generate audio from response object and add to history"""
        try:
            print("Assistant: ")
            full_text = ""
            curr_text = ""
            sentence_terminators = {".", "!", "?"}
            async for w in response:
                print(w, end="")
                full_text += w
                curr_text += w
                if curr_text.rstrip()[-1] in sentence_terminators:
                    for _, _, aud in PIPELINE(curr_text, voice="af_heart"):
                        speak_queue.put(np.array(aud.tolist(), dtype=np.float32))  # type: ignore
                    curr_text = ""
            speak_queue.put(finish_token)
            print("\n")
            if f:
                f.set_result(full_text)
                return full_text
            else:
                await self.add_to_history("assistant", full_text)
        except Exception as e:
            print(f"Error in audio generation: {e}")
            speak_queue.put(finish_token)

    async def process_response(self, response_text):
        """Process response from LLM-MCP client"""
        future = asyncio.Future()
        t = asyncio.get_event_loop().create_task(
            self.generate_audio(response_text, future)
        )

        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=24000,
            output=True,
            frames_per_buffer=1024,
            stream_callback=pyaudio_callback,
        )

        stream.start_stream()

        try:
            await t
            while stream.is_active():
                time.sleep(0.1)
            await self.add_to_history("assistant", future.result())
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()


def speak(text):
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paFloat32,
        channels=1,
        rate=24000,
        frames_per_buffer=1024,
        output=True,
    )

    try:
        for _, _, aud in PIPELINE(text, voice="af_heart"):
            data = np.array(aud.tolist(), dtype=np.float32)  # type: ignore
            stream.write(data.tobytes())
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


def pyaudio_callback(in_data, frame_count, time_info, status):
    global audio_buffer

    try:
        while len(audio_buffer) < frame_count:
            try:
                data = speak_queue.get_nowait()
                if data is finish_token:
                    # If we have remaining data, return it
                    if len(audio_buffer) > 0:
                        if len(audio_buffer) < frame_count:
                            padding = np.zeros(
                                frame_count - len(audio_buffer), dtype=np.float32
                            )
                            audio_buffer = np.concatenate([audio_buffer, padding])
                        output_data = audio_buffer[:frame_count]
                        audio_buffer = np.array([], dtype=np.float32)
                        return (output_data.tobytes(), pyaudio.paComplete)
                    else:
                        return (
                            np.zeros(frame_count, dtype=np.float32).tobytes(),
                            pyaudio.paComplete,
                        )

                audio_buffer = np.concatenate([audio_buffer, data])
            except Empty:
                break

        if len(audio_buffer) >= frame_count:  # enough data
            output_data = audio_buffer[:frame_count]
            audio_buffer = audio_buffer[frame_count:]  # Keep remaining data
            return (output_data.tobytes(), pyaudio.paContinue)
        else:
            # Not enough data, pad with zeros
            if len(audio_buffer) > 0:
                padding = np.zeros(frame_count - len(audio_buffer), dtype=np.float32)
                output_data = np.concatenate([audio_buffer, padding])
                audio_buffer = np.array([], dtype=np.float32)
            else:
                output_data = np.zeros(frame_count, dtype=np.float32)

            return (output_data.tobytes(), pyaudio.paContinue)

    except Exception as e:
        print(f"Error in callback: {e}")
        return (np.zeros(frame_count, dtype=np.float32).tobytes(), pyaudio.paComplete)


def run_ui():
    """Function to run UI in separate thread"""
    ui = ConversationUI(message_queue, conversation_history, return_queue)
    ui.run()


async def main():
    ass = Assistant(client, message_queue, conversation_history, return_queue)
    try:
        await client.connect_to_server()
        await client.init_chat()

        bg_thread = threading.Thread(target=ass.start_background_chat, daemon=True)
        bg_thread.start()

        ui_thread = threading.Thread(target=run_ui, daemon=True)
        ui_thread.start()
        await asyncio.Event().wait()

    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    # asyncio.run(main(json_path))
    client = MCPClient()

    message_queue = Queue()
    conversation_history = deque(maxlen=100)
    return_queue = Queue()
    notification_queue = Queue()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
