import asyncio
from contextlib import AsyncExitStack
from typing import AsyncIterator
from mcp import ClientSession, StdioServerParameters, types as mcp_types
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
import tomllib
# import streamlit as st

load_dotenv()

with open("config.toml", "rb") as f:
    config = tomllib.load(f)["client"]

sys_message = config["SYS_INST"]
MODEL = config["MODEL"]
server_config_path = config["server_config"]


class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client()
        self.mcp_config: types.GenerateContentConfig | None = None
        self.mcp_chat = None
        self.mcp_tools: list[mcp_types.Tool] = []
        self.parameters: dict[str, dict] = {}

    async def connect_to_server(self) -> bool:
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server config file (.json)
        """
        print("Connecting to MCP Server...")
        try:
            with open(server_config_path, "r") as f:
                params = json.load(f)

            all_tools = []
            tool_to_params = {}
            for name, params in params["mcpServers"].items():
                server_param = StdioServerParameters(
                    command=params["command"],
                    args=params["args"],
                )
                async with stdio_client(server_param) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        response = await session.list_tools()
                        all_tools.extend(response.tools)
                        for tool in response.tools:
                            tool_to_params[tool.name] = server_param

            self.mcp_tools = all_tools
            self.parameters = tool_to_params
            print(
                "\nConnected to server with tools:", [tool.name for tool in all_tools]
            )
            return True
        except Exception as e:
            print("Could not setup MCP connection: ", e)
            return False

    async def init_chat(self) -> None:
        """Intialize LLM chat object"""
        mcp_config = genai.types.GenerateContentConfig(
            tools=self.mcp_tools,  # type: ignore
            system_instruction=[sys_message],
            candidate_count=1,  # type: ignore
        )
        self.mcp_config = mcp_config
        self.mcp_chat = self.client.aio.chats.create(model=MODEL, config=mcp_config)

    async def get_response(self, m) -> AsyncIterator[types.GenerateContentResponse]:
        """Get response from LLM"""
        if not self.mcp_chat:
            raise Exception("Chat is not initialized.")
        res = await self.mcp_chat.send_message_stream(m, config=self.mcp_config)
        return res

    async def call_tool(self, name: str, args: dict[str, str]) -> str | dict[str, str]:
        "Call MCP tool and return result or error message"
        params = self.parameters[name]
        async with stdio_client(params) as (read, write):  # type: ignore
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                res = await session.call_tool(name, args)
                if res.isError:
                    return res.content[0].text  # type: ignore
        return res.structuredContent["result"]  # type: ignore

    async def process_query(self, query: str):
        """Process a query using model and available tools"""
        curr_query = types.Part(text=query)
        i = 0
        while i < 5:
            response = await self.get_response(curr_query)
            f_call = False

            async for chunk in response:
                if fun_call := chunk.candidates[0].content.parts[0].function_call:  # type: ignore
                    f_call = True
                    tool_name = fun_call.name
                    tool_args = fun_call.args

                    result = await self.call_tool(tool_name, tool_args)  # type: ignore
                    print(f"\n[Calling tool {tool_name} with args {tool_args}]")
                    curr_query = types.Part(
                        text=f"Tool_name: {tool_name}, Tool_response: {result}"
                    )
                    break
                else:
                    yield (chunk.text)
            i += 1
            if not f_call:
                return

    async def chat_loop(self) -> None:
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                res = self.process_query(query)
                async for c in res:
                    print(c, end="")
                print("\n")

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server()
        await client.init_chat()
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
