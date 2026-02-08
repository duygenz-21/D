import os
import asyncio
from fastapi_poe import PoeBot, make_app
from openai import AsyncOpenAI

# Lấy Key từ biến môi trường (Cài đặt bên Vercel sau)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
POE_ACCESS_KEY = os.environ.get("POE_ACCESS_KEY")

class OpenRouterBot(PoeBot):
    async def get_response(self, request):
        # Kiểm tra xem có Key chưa
        if not OPENROUTER_API_KEY:
            yield self.text_event("Lỗi: Chưa điền API Key OpenRouter trong Vercel Settings nha sếp!")
            return

        # Kết nối OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )

        # Lấy tin nhắn cuối cùng
        last_message = request.query[-1].content
        
        # Chọn model (Có thể đổi model khác ở đây)
        # Ví dụ: "openai/gpt-3.5-turbo" hoặc "meta-llama/llama-3-8b-instruct:free"
        model_id = "openai/gpt-oss-120b"

        try:
            stream = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": last_message}],
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield self.text_event(chunk.choices[0].delta.content)
                    
        except Exception as e:
            yield self.text_event(f"Toang rồi: {str(e)}")

# Khởi chạy bot
bot = OpenRouterBot()
app = make_app(bot, access_key=POE_ACCESS_KEY)
