import os
import asyncio
import requests  # Thư viện này để tải file về nè sếp
from fastapi_poe import PoeBot, make_app
from openai import AsyncOpenAI

# Lấy Key từ biến môi trường
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
POE_ACCESS_KEY = os.environ.get("POE_ACCESS_KEY")

# Cấu hình Model (Sếp thích đổi thì đổi ở đây nha)
# Khuyên dùng dòng Gemini 2.0 hoặc GPT-4o để nhìn được ảnh
MODEL_ID = "xiaomi/mimo-v2-flash" 

class OpenRouterBot(PoeBot):
    async def get_response(self, request):
        # 1. Kiểm tra tiền nong (API Key)
        if not OPENROUTER_API_KEY:
            yield self.text_event("🚨 Lỗi: Sếp ơi quên nạp Key OpenRouter rồi kìa!")
            return

        # 2. Khởi tạo kết nối OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            # Thêm header để OpenRouter biết mình là ai (không bắt buộc nhưng nên có cho uy tín)
            default_headers={
                "HTTP-Referer": "https://poe.com", 
                "X-Title": "Poe Custom Bot"
            }
        )

        # 3. Xử lý tin nhắn cuối cùng từ người dùng
        last_message_obj = request.query[-1]
        user_text = last_message_obj.content
        
        # Danh sách nội dung sẽ gửi cho AI (định dạng đa phương tiện)
        final_content_block = []

        # --- XỬ LÝ TEXT CHÍNH ---
        # Luôn thêm câu hỏi của sếp vào đầu tiên
        if user_text:
            final_content_block.append({"type": "text", "text": user_text})

        # --- XỬ LÝ FILE ĐÍNH KÈM (ATTACHMENTS) ---
        for attachment in last_message_obj.attachments:
            # A. Nếu là ẢNH (Image) 📸
            if attachment.content_type.startswith("image"):
                final_content_block.append({
                    "type": "image_url",
                    "image_url": {
                        "url": attachment.url # Gửi thẳng link ảnh cho AI tự xem
                    }
                })
            
            # B. Nếu là FILE TEXT (Code, txt, md, json...) 📄
            # Lưu ý: OpenRouter không tự đọc file text qua link, mình phải tải về
            elif "text" in attachment.content_type or attachment.name.endswith(('.py', '.js', '.html', '.css', '.json', '.md')):
                try:
                    # Tải nội dung file về
                    print(f"DEBUG: Đang tải file {attachment.name}...")
                    response = requests.get(attachment.url)
                    response.raise_for_status() # Kiểm tra xem link còn sống không
                    
                    file_content = response.text
                    
                    # Nhồi nội dung file vào prompt dưới dạng text
                    file_prompt = f"\n\n--- FILE CONTENT: {attachment.name} ---\n{file_content}\n--- END FILE ---\n"
                    final_content_block.append({"type": "text", "text": file_prompt})
                    
                except Exception as e:
                    yield self.text_event(f"⚠️ Cảnh báo: Không đọc được file {attachment.name}. Lỗi: {e}")

            # C. Nếu là PDF (Ca này khó) 📚
            elif attachment.content_type == "application/pdf":
                # Để đọc PDF cần thư viện pypdf nặng nề, tạm thời báo lỗi nhẹ nhàng
                yield self.text_event(f"⚠️ Info: Em chưa biết đọc PDF '{attachment.name}' sếp ơi. Sếp copy text dán vào hoặc đổi sang file .txt nhé!")

        # 4. Gửi yêu cầu lên OpenRouter
        try:
            # Tạo message history (nếu sếp muốn nhớ ngữ cảnh cũ thì phải loop hết request.query)
            # Ở đây em chỉ lấy message cuối cùng để tiết kiệm token và tập trung vào file
            messages = [
                {
                    "role": "system", 
                    "content": "Bạn là trợ lý AI hữu ích, trả lời ngắn gọn, hài hước và dùng nhiều emoji. 😎"
                },
                {
                    "role": "user", 
                    "content": final_content_block # Chứa cả text, ảnh và nội dung file
                }
            ]

            stream = await client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
                stream=True
            )

            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield self.text_event(content)
                    
        except Exception as e:
            error_msg = str(e)
            if "402" in error_msg:
                yield self.text_event("💸 Hết tiền rồi sếp ơi! (Lỗi 402 Payment Required)")
            else:
                yield self.text_event(f"💥 Toang: {error_msg}")

# Khởi chạy bot
bot = OpenRouterBot()
app = make_app(bot, access_key=POE_ACCESS_KEY)
