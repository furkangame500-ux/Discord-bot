import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")
GUILD_ID = int(os.getenv("GUILD_ID") or 0)

BRAND = os.getenv("BRAND_NAME", "BXProject")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://bxproject.com")
YOUTUBE_URL = os.getenv("YOUTUBE_URL", "https://youtube.com/@bxproject-1")
YOUTUBE_HANDLE = os.getenv("YOUTUBE_HANDLE", "@bxproject-1")
YOUTUBE_NAME_HINT = os.getenv("YOUTUBE_NAME_HINT", "BXProject")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

CURRENCY = os.getenv("CURRENCY_NAME", "BX Coin")

COLOR_JOIN = 0xF5A623
COLOR_LEAVE = 0xED4245
COLOR_OK = 0x57F287
COLOR_INFO = 0x5865F2
COLOR_WARN = 0xFEE75C
