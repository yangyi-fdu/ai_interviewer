import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

# 加载环境和 API Key
load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

# 🎭 V1 简陋版 Prompt：只给一个总分
PROMPT_V1 = """
你是一个技术面试官。请根据候选人的回答，给出一个0-100的综合得分。
只需输出一行字，格式必须为：【最终得分：XX分】。不要解释。
"""

# 🎭 V2 大厂版 Prompt：多维度强制拆解
PROMPT_V2 = """
你是一个技术面试官。请根据候选人的回答，分别给出知识(40分)、逻辑(30分)、表达(30分)的得分，并汇总。
必须严格输出以下格式，不要有废话：
【知识深度】：XX/40
【逻辑严密】：XX/30
【表达清晰】：XX/30
【最终得分】：XX分
"""

# 模拟真实的面试场景
QUESTION = "请解释一下什么是快速排序（QuickSort），以及它的时间复杂度？"

# 准备 3 个不同段位的“虚拟候选人”
CANDIDATES = {
    "🏆 大神局": "快速排序基于分治思想。选择一个基准值pivot，将数组分为小于和大于pivot的两部分，递归排序。平均时间复杂度O(NlogN)，最坏O(N^2)，空间复杂度O(logN)。",
    "🤡 嘴强王者局": "快速排序就是排得很快的算法！它的时间复杂度是O(N)，它巧妙地用到了二叉树和哈希表的结构，在企业里用的非常多，我非常精通这个牛逼的算法！",
    "🏳️ 摆烂局": "额，我不清楚，没复习到这个。"
}

async def evaluate(prompt, answer):
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"面试官问题：{QUESTION}\n候选人回答：{answer}"}
    ]
    response = await client.chat.completions.create(
        model="deepseek-chat", messages=messages, temperature=0.1 # 调低温度，让打分更稳定
    )
    return response.choices[0].message.content.strip()

async def main():
    print("🚀 开始 AI 面试官打分评测 (Eval) 对比实验...\n")
    print(f"📌 面试问题：{QUESTION}\n" + "="*50)
    
    for name, answer in CANDIDATES.items():
        print(f"\n👤 候选人类型: {name}")
        print(f"💬 他的回答: {answer}\n")
        
        v1_score = await evaluate(PROMPT_V1, answer)
        print(f"🔴 [V1 综合打分（老好人模式）] -> {v1_score}")
        
        v2_score = await evaluate(PROMPT_V2, answer)
        print(f"🟢 [V2 维度打分（大厂严苛模式）] -> \n{v2_score}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
