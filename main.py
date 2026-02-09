import os
import aiohttp
import json
from fastapi_poe import PoeBot, make_app
from fastapi_poe.types import ProtocolMessage
from typing import AsyncIterable

# Lấy Key từ biến môi trường
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
POE_ACCESS_KEY = os.environ.get("POE_ACCESS_KEY")

# Cấu hình Model - dùng model đơn giản trước để test
MODEL_ID = "openai/gpt-oss-120b"  # Đổi sang model ổn định hơn

class OpenRouterBot(PoeBot):
    async def get_response(self, request) -> AsyncIterable[ProtocolMessage]:
        try:
            # 1. Kiểm tra API Key
            if not OPENROUTER_API_KEY:
                yield self.text_event("🚨 Lỗi: Thiếu OpenRouter API Key!")
                return

            # 2. Lấy tin nhắn cuối
            last_message = request.query[-1]
            user_text = last_message.content or ""
            
            # 3. Chỉ xử lý text trước (đơn giản hóa)
            if not user_text:
                yield self.text_event("🤔 Xin lỗi, tôi chỉ hỗ trợ văn bản trong phiên bản này.")
                return

            # 4. Chuẩn bị headers cho OpenRouter
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://poe.com",
                "X-Title": "Poe Bot"
            }

            # 5. Chuẩn bị payload
            payload = {
                "model": MODEL_ID,
                "messages": [
                    {
                        "role": "system",
                        "content": "Bạn là trợ lý AI hữu ích. Trả lời ngắn gọn và thân thiện."
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
                ],
                "stream": True
            }

            # 6. Gửi request đến OpenRouter
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        yield self.text_event(f"🚨 Lỗi từ OpenRouter: {response.status}")
                        return

                    # 7. Xử lý stream response
                    buffer = ""
                    async for line in response.content:
                        if line:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                if data_str == '[DONE]':
                                    break
                                
                                try:
                                    data = json.loads(data_str)
                                    if 'choices' in data and len(data['choices']) > 0:
                                        delta = data['choices'][0].get('delta', {})
                                        if 'content' in delta and delta['content']:
                                            content = delta['content']
                                            buffer += content
                                            
                                            # Flush buffer khi đủ dài hoặc có dấu câu
                                            if len(buffer) > 50 or content in ['.', '!', '?', '\n']:
                                                yield self.text_event(buffer)
                                                buffer = ""
                                except json.JSONDecodeError:
                                    continue
                    
                    # Yield phần còn lại
                    if buffer:
                        yield self.text_event(buffer)

        except Exception as e:
            # Log lỗi để debug
            print(f"ERROR: {str(e)}")
            yield self.text_event(f"⚠️ Có lỗi xảy ra: {str(e)[:100]}")

# Khởi chạy bot
bot = OpenRouterBot()
app = make_app(bot, access_key=POE_ACCESS_KEY)