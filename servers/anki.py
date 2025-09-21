from typing import Optional, Any, Literal
import httpx
from mcp.server.fastmcp import FastMCP
import re
import logging
from bs4 import BeautifulSoup


mcp = FastMCP("anki")

BASE_URL = "http://127.0.0.1:8765"
USER_AGENT = "anki-app/1.0"


async def invoke(action, method="GET", **params):
    req_json = {"action": action, "params": params, "version": 6}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(method, BASE_URL, json=req_json)
            response.raise_for_status()
            response = response.json()
            if len(response) != 2:
                raise Exception("response has an unexpected number of fields")
            if "error" not in response:
                raise Exception("response is missing required error field")
            if "result" not in response:
                raise Exception("response is missing required result field")
            if response["error"] is not None:
                raise Exception(response["error"])
            return response["result"]
        except Exception as e:
            raise e


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("div")
    if div:
        return div.text
    return ""


def clean_info(info: dict[str, str]) -> dict:
    keys = ["cardId", "fields", "modelName", "deckName"]
    clean = {k: info[k] for k in keys}
    clean["question"] = clean_html(info["question"])
    clean["answer"] = clean_html(info["answer"])
    return clean


@mcp.tool()
async def get_deck_names() -> list[str]:
    """
    Get all anki deck names.

    Returns:
        Dictionary containing deck names and their ids.
    """

    return await invoke(action="deckNames")


@mcp.tool()
async def get_cards_from_deck(
    deck: Optional[str] = "*",
    status: Optional[Literal["due", "learn", "new", "review"]] = "due",
    count: Optional[int] = 1,
) -> list[int]:
    """
    Get cards belonging to given deck.

    Args:
        deck(str): name of deck. Defaults to * which selects all decks.
        status(optional, str): filter by status of card. Can be due, learn(cards in learning),
        new, review(cards in review both due and not due). Defaults to due.
        count(optional, int): how many cards to get. Defaults to 1 card.

    Returns:
        list of card ids.
    """

    res = await invoke(
        "findCards", query=f"deck:{deck} is:{status}"
    )  # is:due  “New/review order: Show before reviews”

    return res[:count]


@mcp.tool()
async def get_cards_info(ids: list[int]) -> list[dict]:
    """
    Get content of each card.

    Args:
        ids(list[int]): list of card ids

    Returns:
        list of card information, each entry being a dictonary
    """

    res = await invoke("cardsInfo", cards=ids)
    return [clean_info(i) for i in res]


@mcp.tool()
async def get_media(filename: str) -> str | None:
    """
    Get base64-encoded content of media file

    Args:
        filename(str): name of the file

    Returns:
        base64-encoded content of media file
    """

    res = await invoke("retrieveMediaFile", filename=filename)
    return res


@mcp.tool()
async def answer_card(id: int, ease: int) -> bool:
    """
    Anser card and set how easy it is.

    Arg
        id(int): id of card
        ease(int): integer denoting easiness of card. From 1(relearn) to 4(easy)

    Returns:
        True if card exists False otherwise.
    """

    result = await invoke(
        "answerCards", method="POST", answers=[{"cardId": id, "ease": ease}]
    )
    return result[0]


if __name__ == "__main__":
    mcp.run(transport="stdio")
