import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from api.interview import Interviewer
from database.db_manager import init_db, save_report

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
)
MODEL = os.getenv("LLM_MODEL", "glm-4-flash")


async def call_llm(messages: list[dict]) -> str:
    response = await client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0.7, max_tokens=800
    )
    return response.choices[0].message.content


app = FastAPI(title="AI Interviewer")
interviewer = Interviewer(call_llm)
init_db()


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    finished: bool


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        reply = await interviewer.handle(request.user_id, request.message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="LLM request failed, please resend your message") from exc

    if reply.finished:
        save_report(request.user_id, reply.report, reply.scores)
    return ChatResponse(reply=reply.text, finished=reply.finished)
