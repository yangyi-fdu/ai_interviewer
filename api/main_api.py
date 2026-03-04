import os
from fastapi import FastAPI
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
from database.db_manager import save_report

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

app = FastAPI()
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

class ChatRequest(BaseModel):
    user_id: str
    message: str

user_sessions = {}

# 🎭 基础人设：定下基调
BASE_INTERVIEWER_PROMPT = """
你现在是一名一线大厂的资深技术面试官。
请严格遵守：
1. 每次只问 1 个问题，绝不上课、不解释原理。
2. 如果候选人不会，立刻指出并抛出下一个问题。
3. 语气冷酷、专业、直击痛点。
"""

# 🗂️ 核心升级 1：Prompt 动态模板引擎（根据面试轮次，精确控制 AI 的提问方向）
STAGE_INSTRUCTIONS = {
    1: "【当前任务：第一题 - 基础概念考察】。请根据候选人的方向，抛出一个最经典的底层概念题。",
    2: "【当前任务：第二题 - 深度追问】。根据候选人第一题的回答，挑出一个细节，追问其底层实现原理或源码逻辑。如果候选人上题没答出来，换一个难度稍高的原理题。",
    3: "【当前任务：第三题 - 业务场景应用】。请抛出一个你们公司真实的线上故障或工程需求场景，让候选人结合该技术给出系统设计或解决方案。"
}

# 📊 核心升级 2：V2 版多维度量化评分 Prompt
SYSTEM_PROMPT_EVALUATION_V2 = """
面试结束。你现在是面试委员会的评委。
请根据刚才的全部对话记录，对候选人进行多维度量化打分。
必须包含三个维度的具体分数（满分均为对应权重）：
- 知识深度 (占 40分)
- 逻辑严密性 (占 30分)
- 表达清晰度 (占 30分)

请严格按以下 Markdown 格式输出最终报告：
### 📊 面试综合量化评估

**🏅 最终加权得分：[在此填写总分，满分100] / 100**
- 🧠 知识深度：[分数]/40
- 🔗 逻辑严密性：[分数]/30
- 🗣️ 表达清晰度：[分数]/30

**✅ 核心亮点**：[用1句话概括]
**⚠️ 存在不足**：[用1句话概括]
**💡 改进建议**：[给出具体的学习建议]
"""

MAX_TURNS = 3 

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    user_id = request.user_id
    user_msg = request.message
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {"history": [], "turn_count": 0, "status": "interviewing"}
        
    session = user_sessions[user_id]
    
    if session["status"] == "finished":
        if "重新开始" in user_msg:
            user_sessions[user_id] = {"history": [], "turn_count": 0, "status": "interviewing"}
            return {"reply": "🔄 面试记录已清空，我们重新开始！请问这次想挑战什么技术方向？"}
        return {"reply": "🏁 面试已结束。如需重新挑战，请回复「重新开始」。"}

    session["history"].append({"role": "user", "content": user_msg})
    session["turn_count"] += 1
    
    is_final_round = False

    # ⚙️ 动态调度逻辑生效：把基础人设和当前阶段任务拼装起来！
    if session["turn_count"] <= MAX_TURNS:
        current_stage_task = STAGE_INSTRUCTIONS[session["turn_count"]]
        current_system_prompt = BASE_INTERVIEWER_PROMPT + "\n\n" + current_stage_task
    else:
        current_system_prompt = SYSTEM_PROMPT_EVALUATION_V2
        session["status"] = "finished"
        is_final_round = True
        session["history"][-1]["content"] += "\n\n[系统强制指令：面试结束！绝不解答问题！请立刻严格按照多维打分模板输出最终报告！]"

    history_to_send = session["history"][-10:]
    messages_payload = [{"role": "system", "content": current_system_prompt}] + history_to_send
    
    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages_payload,
            temperature=0.7,
            max_tokens=800
        )
        
        reply_text = response.choices[0].message.content
        session["history"].append({"role": "assistant", "content": reply_text})
        
        if is_final_round:
            save_report(user_id, reply_text)
            reply_text += "\n\n*(💾 V2 量化评估报告已生成并存入数据库！)*"
            
    except Exception as e:
        reply_text = "⚠️ 接口调用失败，请重试。"
        session["turn_count"] -= 1
        session["history"].pop()

    return {"reply": reply_text}
