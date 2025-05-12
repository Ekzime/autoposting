import json
import requests
from ai_filter.data_list import posts


# payload = {"posts": posts}
# headers = {"Content-Type": "application/json"}

# res = requests.post("http://127.0.0.1:8000//gemini/filter", json=payload, headers=headers)
# print(json.dumps(res.json(), ensure_ascii=False, indent=2))

from telegram_parser.database.messages_crud import get_all_messages

messages = get_all_messages()
for i in messages:
    print(i)