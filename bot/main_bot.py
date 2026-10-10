"""Discord front end. It only relays messages; all interview logic lives in the API."""
import os

import aiohttp
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/chat")
DISCORD_LIMIT = 2000  # maximum characters per Discord message

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def split_message(text: str, limit: int = DISCORD_LIMIT) -> list[str]:
    """Split on line breaks where possible so long reports stay readable."""
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    async with message.channel.typing():
        payload = {"user_id": str(message.author.id), "message": message.content}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(BACKEND_URL, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        await message.channel.send(f"Backend error (HTTP {response.status}). Please resend.")
                        return
                    data = await response.json()
        except aiohttp.ClientError:
            await message.channel.send("Cannot reach the interview backend. Is the API running?")
            return

    for part in split_message(data["reply"]):
        await message.channel.send(part)


if __name__ == "__main__":
    client.run(TOKEN)
