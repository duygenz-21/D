import os
import asyncio
import aiohttp  # Thay requests bằng aiohttp cho async
from fastapi_poe import PoeBot, make_app
from fastapi_poe.types import ProtocolMessage
from typing import AsyncIterable
import json

# Lấy Key từ biến môi trường
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
POE_ACCESS_KEY = os.environ.get("POE_ACCESS_KEY")

# Cấu hình Model
MODEL_ID = "xiaomi/mimo-v2-flash"

class OpenRouterBot(PoeBot):
    async def get_response(self, request) -> AsyncIterable[ProtocolMessage]:
        # 1. Kiểm tra API Key
        if not OPENROUTER_API_KEY:
            yield self.text_event("🚨 Lỗi: Sếp ơi quên nạp Key OpenRouter rồi kìa!")
            return

        # 2. Xử lý tin nhắn cuối cùng từ người dùng
        last_message = request.query[-1]
        user_text = last_message.content
        
        # Danh sách nội dung sẽ gửi cho AI
        final_content = []

        # --- XỬ LÝ TEXT CHÍNH ---
        if user_text:
            final_content.append({"type": "text", "text": user_text})

        # --- XỬ LÝ FILE ĐÍNH KÈM ---
        if hasattr(last_message, 'attachments') and last_message.attachments:
            async with aiohttp.ClientSession() as session:
                for attachment in last_message.attachments:
                    # A. Nếu là ẢNH
                    if attachment.content_type and attachment.content_type.startswith("image/"):
                        final_content.append({
                            "type": "image_url",
                            "image_url": {"url": attachment.url}
                        })
                    
                    # B. Nếu là FILE TEXT
                    elif (attachment.content_type and "text" in attachment.content_type) or \
                         (attachment.name and any(attachment.name.endswith(ext) for ext in ['.py', '.js', '.html', '.css', '.json', '.md', '.txt'])):
                        try:
                            async with session.get(attachment.url) as response:
                                if response.status == 200:
                                    file_content = await response.text()
                                    file_prompt = f"\n\n--- FILE: {attachment.name} ---\n{file_content}\n--- END FILE ---\n"
                                    final_content.append({"type": "text", "text": file_prompt})
                                else:
                                    yield self.text_event(f"⚠️ Không tải được file {attachment.name}: HTTP {response.status}")
                        except Exception as e:
                            yield self.text_event(f"⚠️ Lỗi đọc file {attachment.name}: {str(e)}")
                    
                    # C. Nếu là PDF hoặc file không hỗ trợ
                    elif attachment.content_type == "application/pdf":
                        yield self.text_event(f"📄 PDF '{attachment.name}' hiện chưa hỗ trợ. Sếp copy text dán vào hoặc đổi sang .txt nhé!")
                    else:
                        yield self.text_event(f"📎 File '{attachment.name}' ({attachment.content_type}) chưa hỗ trợ xử lý.")

        # 3. Nếu không có nội dung nào
        if not final_content:
            yield self.text_event("🤔 Sếp gửi gì vậy? Em không thấy nội dung nào cả.")
            return

        # 4. Gửi yêu cầu lên OpenRouter
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://poe.com",
            "X-Title": "Poe Custom Bot"
        }

        # Chuẩn bị messages
        messages = [
            {
                "role": "system",
                "content": "Bạn là trợ lý AI hữu ích, trả lời ngắn gọn, hài hước và dùng nhiều emoji. 😎"
            },
            {
                "role": "user",
                "content": final_content
            }
        ]

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": MODEL_ID,
                    "messages": messages,
                    "stream": True
                }

                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        if response.status == 402:
                            yield self.text_event("💸 Hết tiền rồi sếp ơi! Vui lòng nạp thêm credit tại OpenRouter.")
                        else:
                            yield self.text_event(f"🚨 Lỗi từ OpenRouter ({response.status}): {error_text[:200]}")
                        return

                    # Xử lý stream response
                    buffer = ""
                    async for chunk in response.content:
                        if chunk:
                            chunk_str = chunk.decode('utf-8')
                            lines = chunk_str.split('\n')
                            
                            for line in lines:
                                if line.strip().startswith('data: '):
                                    data = line[6:].strip()
                                    if data == '[DONE]':
                                        break
                                    
                                    try:
                                        json_data = json.loads(data)
                                        if 'choices' in json_data and len(json_data['choices']) > 0:
                                            delta = json_data['choices'][0].get('delta', {})
                                            if 'content' in delta and delta['content']:
                                                content = delta['content']
                                                buffer += content
                                                
                                                # Yield từng phần nhỏ để hiển thị từ từ
                                                if len(buffer) > 20 or '\n' in content:
                                                    yield self.text_event(buffer)
                                                    buffer = ""
                                    except json.JSONDecodeError:
                                        continue
                    
                    # Yield phần còn lại
                    if buffer:
                        yield self.text_event(buffer)

        except Exception as e:
            yield self.text_event(f"💥 Lỗi kết nối: {str(e)}")

# Khởi chạy bot
bot = OpenRouterBot()
app = make_app(bot, access_key=POE_ACCESS_KEY)