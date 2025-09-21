from typing import Optional, Any, Literal
import httpx
from mcp.server.fastmcp import FastMCP, Image as Mcp_Image
from PIL import ImageGrab, Image
import os
from io import BytesIO
import base64

mcp = FastMCP("utils")


@mcp.tool()
async def get_screenshot() -> str:
    """
    Returns screenshot image as base64 encoded string.
    """
    img = ImageGrab.grab()
    # dir_path = os.path.dirname(os.path.realpath(__file__))
    # path = os.path.join(dir_path, name)
    # return Mcp_Image(data=img.tobytes())

    buffered = BytesIO()
    # rgb = img.convert("RGB")
    img.save(buffered, format="jpeg")
    img_str = base64.b64encode(buffered.getvalue())
    # Convert bytes to string
    return img_str.decode("utf-8")


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
