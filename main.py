import os
import asyncio
import httpx
import io
from fastapi_poe import PoeBot, make_app
from openai import AsyncOpenAI
from pypdf import PdfReader
from docx import Document

# Lấy Key (Nhớ set env var nha sếp) 🔑
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
POE_ACCESS_KEY = os.environ.get("POE_ACCESS_KEY")

class OpenRouterBot(PoeBot):
    async def get_response(self, request):
        if not OPENROUTER_API_KEY:
            yield self.text_event("🆘 Lỗi: Quên chưa điền API Key OpenRouter rồi sếp ơi!")
            return

        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )

        # 1. Lấy tin nhắn mới nhất
        last_message = request.query[-1]
        user_text = last_message.content
        
        # 2. Xử lý file đính kèm (nếu có) 📂
        file_content_context = ""
        
        for attachment in last_message.attachments:
            try:
                # Tải file về 📥
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(attachment.url)
                    response.raise_for_status()
                    file_bytes = io.BytesIO(response.content)

                # Xử lý theo từng loại file 🛠️
                content_text = ""
                filename = attachment.name.lower()

                if filename.endswith(".pdf"):
                    reader = PdfReader(file_bytes)
                    for page in reader.pages:
                        content_text += page.extract_text() + "\n"
                        
                elif filename.endswith(".docx"):
                    doc = Document(file_bytes)
                    content_text = "\n".join([para.text for para in doc.paragraphs])
                    
                elif filename.endswith((".txt", ".md")):
                    content_text = response.content.decode("utf-8", errors="ignore")
                
                else:
                    content_text = "[File này định dạng lạ quá, em đọc không được nha sếp!]"

                # Gộp nội dung file vào context
                if content_text.strip():
                    file_content_context += f"\n\n--- Nội dung file '{attachment.name}': ---\n{content_text}\n"

            except Exception as e:
                file_content_context += f"\n[Lỗi khi đọc file {attachment.name}: {str(e)}]\n"

        # 3. Tạo prompt cuối cùng gửi cho AI 🧠
        # Kết hợp nội dung file + câu hỏi của user
        final_prompt = f"{user_text}\n{file_content_context}"

        # Chọn model (Lưu ý: Model này phải hỗ trợ context dài nếu file dài nha)
        model_id = "openai/gpt-3.5-turbo" # Hoặc gpt-4o-mini cho rẻ mà khôn

        try:
            stream = await client.chat.completions.create(
                model=model_id,
                messages=[
                    # System prompt để nhắc nó biết nhiệm vụ
                    {"role": "system", "content": "Bạn là trợ lý AI hữu ích. Hãy trả lời câu hỏi dựa trên nội dung file được cung cấp (nếu có)."},
                    {"role": "user", "content": final_prompt}
                ],
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield self.text_event(chunk.choices[0].delta.content)
                    
        except Exception as e:
            yield self.text_event(f"💥 Toang rồi sếp ơi: {str(e)}")

# Khởi chạy bot 🚀
bot = OpenRouterBot()
app = make_app(bot, access_key=POE_ACCESS_KEY)
