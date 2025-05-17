from dotenv import load_dotenv
import os

load_dotenv()

PHONE_NUMBER = os.getenv("PHONE_NUMBER")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")
PHOTO_STORAGE = os.getenv("PHOTO_STORAGE")
SOURCE_STOGAGE: list[str | int] = [
    7783544651,
    "https://t.me/incrypted"
]