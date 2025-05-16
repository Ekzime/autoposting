from dotenv import load_dotenv
import os

load_dotenv()

PHONE_NUMBER = os.getenv("PHONE_NUMBER")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")
PHOTO_STORAGE = os.getenv("PHOTO_STORAGE")
SOURCE_STOGAGE: list[str | int] = [
    5223667706,
    8080656368,
    "https://t.me/novosti",
    "https://t.me/blumcrypto"
]