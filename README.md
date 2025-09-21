# Voice Assistant: MCP + Gemini 
This is a voice assistant that can interact with user through audio and perform actions using MCP tools.

Features:
-
- MCP tool calling
- Speech To Text using Whisper Model
- Text To Speech
- Background listening and detection of command for assistant
- UI using Tkinter
- Gemini API support
- Continuos chat withou needing to press send button

Note:
-
- To use run Whisper model(for transcribing audio to text) on GPU, install PyTorch for GPU. [Official Intructions](https://pytorch.org/get-started/locally/)
- Create a `.env` file and add your Google API as a "GOOGLE_API_KEY" variable
- To add other local MCP files modify server_config.json file and provide full path to directory. E.g.  
```
"mcpServers": {
    "ankiServer": {
      "command": "uv",
      "args": [
        "--directory",
        "Path to server directory",
        "run",
        "MCP_script.py"
      ]
    }
  }
```    
- To change Gemini Model, Whisper model etc modify `config.toml`

