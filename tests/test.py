import os
import json
import requests
from telegram_parser.database.messages_crud import get_all_messages
from dotenv import load_dotenv

load_dotenv()
AI_URL = os.getenv("AI_API_URL")

messages = get_all_messages()
def ai_post(messages):
    for post in messages:
        payload = {"posts": [post["text"]]}
        headers = {"Content-Type": "application/json"}

        res = requests.post(AI_URL, json=payload, headers=headers)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))


def print_data():
    for post in messages:
        mini_map = {
            "id": post["id"],
            "text": post["text"],
        }
        print(json.dumps(mini_map, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    ai_post(messages)
    #print_data()