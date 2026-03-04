import os
import discord
import aiohttp  # 引入异步请求库（我们的外卖小哥）
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 配置权限
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 💡 核心配置：我们 FastAPI 后端大脑的地址（马上就写）
BACKEND_URL = "http://127.0.0.1:8000/api/chat"

@client.event
async def on_ready():
    print(f'✅ 成功登录！我是 {client.user}，我已经准备好接客了。')

@client.event
async def on_message(message):
    # 避免机器人自己跟自己无限聊天
    if message.author == client.user:
        return

    print(f'📥 收到来自 {message.author.name} 的消息: {message.content}')

    # 触发 Discord 自带的 "正在输入..." 动画，让用户觉得 AI 在思考
    async with message.channel.typing():
        try:
            # 1. 召唤外卖小哥，准备包裹
            async with aiohttp.ClientSession() as session:
                payload = {
                    "user_id": str(message.author.id), # 记录是谁发的消息
                    "message": message.content         # 消息的具体内容
                }
                
                # 2. 把包裹 POST 发送给后厨 (FastAPI)
                async with session.post(BACKEND_URL, json=payload) as response:
                    if response.status == 200:
                        # 3. 如果后厨正常返回，解析 JSON 并把回复发给用户
                        data = await response.json()
                        reply = data.get("reply", "后端没有返回有效内容")
                        await message.channel.send(reply)
                    else:
                        await message.channel.send(f"⚠️ 后厨响应异常，状态码: {response.status}")
                        
        except aiohttp.ClientError:
            # 如果 FastAPI 根本没启动，就会触发这个错误
            print("❌ 无法连接到 FastAPI 后端")
            await message.channel.send("🚧 我的 AI 大脑（后端）似乎还没启动，请去服务器看一眼！")

if __name__ == "__main__":
    client.run(TOKEN)
