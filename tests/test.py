import json
import requests
from telegram_parser.database.messages_crud import get_all_messages

messages = get_all_messages()
def ai_post(messages):
    for post in messages:
        payload = {"posts": [post["text"]]}
        headers = {"Content-Type": "application/json"}

        res = requests.post("http://127.0.0.1:8000/gemini/filter", json=payload, headers=headers)
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