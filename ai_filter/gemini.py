###############################
#           system libs
#------------------------------
import os
import re
import json
from typing import List
###############################
#           my moduls
#------------------------------
from .prompts import prompt
###############################
#            FAST API
#------------------------------
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
###############################
#       other libs/frameworks
#------------------------------
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

class PostBatch(BaseModel):
    posts: List[str]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=    ["*"],  
    allow_methods=    ["*"],
    allow_headers=    ["*"],
    allow_credentials=True,
)



def process_posts(posts: list[str], prompt_template: str = prompt) -> list[str]:
    prompt = prompt_template + "\n\n" + "\n".join(f"- {p}" for p in posts)

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        print("📥 GEMINI RAW RESPONSE:")
        print(raw)

        # 1. Если markdown-обёртка ```json ... ```, вырезаем содержимое
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # 2. Если просто массив без markdown
        if raw.startswith("[") and raw.endswith("]"):
            return json.loads(raw)

        # 3. Не получилось — распарсим как строки
        lines = raw.splitlines()
        return [line.strip("-• ").strip() for line in lines if line and not line.startswith("Вот")]

    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return []


@app.post('/gemini/filter')
async def multi_filter(data: PostBatch):
    result = process_posts(posts=data.posts)
    return {
        'status': 'success',
        'result': result,
    }
