import streamlit as st
from openai import OpenAI
import os
import re
import requests
import base64
import json

# --- Cấu hình Models ---
MODELS = {
    "GLM-5.2": {
        "id": "z-ai/glm-5.2",
        "api_key": "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",
        "type": "text",
        "params": {"temperature": 1.0, "top_p": 1.0, "max_tokens": 16384}
    },
    "MiniMax-M3": {
        "id": "minimaxai/minimax-m3",
        "api_key": "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",
        "type": "multimodal",
        "params": {"temperature": 1.0, "top_p": 0.95, "max_tokens": 8192}
    },
    "Nemotron-3-Ultra": {
        "id": "nvidia/nemotron-3-ultra-550b-a55b",
        "api_key": "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",
        "type": "text",
        "params": {
            "temperature": 1.0, "top_p": 0.95, "max_tokens": 16384,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}
        }
    },
    "DeepSeek-V4-Pro": {
        "id": "deepseek-ai/deepseek-v4-pro",
        "api_key": "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",
        "type": "text",
        "params": {
            "temperature": 1.0, "top_p": 0.95, "max_tokens": 16384,
            "extra_body": {"chat_template_kwargs": {"thinking": True}}
        }
    },
    "Qwen-3.5-397B": {
        "id": "qwen/qwen3.5-397b-a17b",
        "api_key": "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",
        "type": "text",
        "params": {
            "temperature": 0.60, "top_p": 0.95, "max_tokens": 16384,
            "presence_penalty": 0,
            "extra_body": {"top_k": 20, "repetition_penalty": 1}
        }
    },
    "Nemotron-Page-Elements": {
        "id": "nvidia/nemotron-page-elements-v3",
        "api_key": "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",
        "type": "vision-only"
    }
}

st.set_page_config(page_title="NVIDIA NIM AI Agent", page_icon="🚀", layout="wide")

st.title("🚀 NVIDIA NIM - AI Coding Agent")
st.caption("Powered by NVIDIA VIM - Hỗ trợ đa mô hình với thiết lập tối ưu cho từng Model")

# --- Thanh bên (Sidebar) ---
with st.sidebar:
    st.header("⚙️ Cấu hình Agent")
    selected_model = st.selectbox("Chọn Model:", list(MODELS.keys()))
    
    # Hiển thị thông tin model hiện tại
    model_type = MODELS[selected_model]["type"]
    if model_type == "text":
        st.info("📝 Model xử lý văn bản/code.")
    elif model_type == "multimodal":
        st.success("🎨 Model đa phương thức (Hỗ trợ Ảnh + Text).")
    elif model_type == "vision-only":
        st.warning("👁️ Model chuyên biệt cho hình ảnh (Trích xuất thành phần trang web).")
        
    st.divider()
    
    st.header("📂 Ngữ cảnh (Context)")
    
    # Tính năng Upload Ảnh
    image_file = st.file_uploader("🖼️ Tải lên hình ảnh", type=["png", "jpg", "jpeg"], help="Dành cho MiniMax-M3 hoặc Nemotron Page Elements")
    if image_file:
        image_b64 = base64.b64encode(image_file.read()).decode()
        st.session_state["uploaded_image_b64"] = image_b64
        st.image(image_file, caption="Ảnh đã tải lên", use_container_width=True)
    else:
        if "uploaded_image_b64" in st.session_state:
            del st.session_state["uploaded_image_b64"]

    # Hàm hỗ trợ đọc đa định dạng file
    def extract_text_from_file(file):
        filename = file.name.lower()
        if filename.endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(file)
                return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            except ImportError:
                st.error("Thiếu thư viện đọc PDF. Vui lòng chạy: `pip install pypdf`")
                return ""
            except Exception as e:
                st.error(f"Lỗi đọc PDF: {e}")
                return ""
        elif filename.endswith((".docx", ".doc")):
            try:
                import docx
                doc = docx.Document(file)
                return "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                st.error("Thiếu thư viện đọc DOCX. Vui lòng chạy: `pip install python-docx`")
                return ""
            except Exception as e:
                st.error(f"Lỗi đọc DOCX: {e}")
                return ""
        else:
            # Mặc định đọc như file text
            try:
                return file.read().decode("utf-8")
            except Exception as e:
                st.error(f"Không thể đọc nội dung file text: {e}")
                return ""

    # Tính năng Upload File Document/Code
    uploaded_file = st.file_uploader("📄 Tải lên file tài liệu/code", type=["txt", "py", "md", "csv", "json", "js", "html", "css", "pdf", "docx", "doc"])
    if uploaded_file:
        file_content = extract_text_from_file(uploaded_file)
        if file_content:
            st.session_state["uploaded_file_context"] = f"Nội dung file {uploaded_file.name}:\n```\n{file_content}\n```\n"
            st.success(f"Đã nạp file: {uploaded_file.name} (Độ dài: {len(file_content)} ký tự)")
    else:
        if "uploaded_file_context" in st.session_state:
            del st.session_state["uploaded_file_context"]

    # Tính năng Đọc Codebase
    folder_path = st.text_input("Đường dẫn thư mục Codebase:", placeholder="VD: e:\\Study\\NVIDIA_VIM")
    if st.button("Load Codebase"):
        if os.path.isdir(folder_path):
            codebase_context = ""
            file_count = 0
            for root, dirs, files in os.walk(folder_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['venv', 'env', '__pycache__', 'node_modules']]
                for file in files:
                    if file.endswith((".py", ".js", ".html", ".css", ".md", ".txt", ".json", ".yaml", ".sh")):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                                codebase_context += f"--- Bắt đầu file: {file_path} ---\n{content}\n--- Kết thúc file ---\n\n"
                                file_count += 1
                        except Exception:
                            pass
            
            if file_count > 0:
                st.session_state["codebase_context"] = f"Tài liệu Codebase ({file_count} files):\n{codebase_context}"
                st.success(f"Đã nạp {file_count} files vào bộ nhớ.")
            else:
                st.warning("Không tìm thấy file hợp lệ trong thư mục này.")
                if "codebase_context" in st.session_state:
                    del st.session_state["codebase_context"]
        else:
            st.error("Đường dẫn thư mục không tồn tại.")

    st.divider()
    if st.button("🗑️ Xóa lịch sử chat"):
        st.session_state.messages = []
        st.rerun()

# --- Khởi tạo Client API ---
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=MODELS[selected_model]["api_key"]
)

# --- Khởi tạo Lịch sử và System Prompt ---
SYSTEM_PROMPT = """Bạn là một chuyên gia AI Coding Assistant xuất sắc.
Khi bạn viết mã nguồn (code), hãy sử dụng thẻ markdown (```ngôn_ngữ ... ```).
Ở ngay dòng đầu tiên trong khối code, hãy dùng comment để chỉ định tên file (ví dụ: `# File: main.py` hoặc `// File: index.js`).
Điều này sẽ giúp hệ thống tự động nhận diện và đề xuất lưu file chính xác cho người dùng.
"""

if "messages" not in st.session_state or not st.session_state.messages:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# Xây dựng System prompt tổng hợp
current_system_prompt = SYSTEM_PROMPT
if "uploaded_file_context" in st.session_state:
    current_system_prompt += "\n\n" + st.session_state["uploaded_file_context"]
if "codebase_context" in st.session_state:
    current_system_prompt += "\n\n" + st.session_state["codebase_context"]

if st.session_state.messages:
    st.session_state.messages[0] = {"role": "system", "content": current_system_prompt}

# --- Hiển thị Chat và Lưu File ---
for i, message in enumerate(st.session_state.messages):
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            # Xử lý hiển thị text nếu là multimodal list
            if isinstance(message["content"], list):
                text_content = next((item["text"] for item in message["content"] if item.get("type") == "text"), "")
                st.markdown(text_content)
                str_content = text_content
            else:
                st.markdown(message["content"])
                str_content = message["content"]
            
            # Logic "Lưu file này" cho assistant
            if message["role"] == "assistant":
                code_blocks = re.findall(r'```(\w+)?\n(.*?)```', str_content, re.DOTALL)
                if code_blocks:
                    for j, (lang, code) in enumerate(code_blocks):
                        first_line = code.strip().split('\n')[0]
                        filename = f"generated_code_{i}_{j}.{lang if lang else 'txt'}"
                        if "File:" in first_line:
                            try:
                                filename = first_line.split("File:")[1].strip()
                            except: pass
                        
                        col1, col2 = st.columns([1, 5])
                        with col1:
                            if st.button("💾 Lưu file", key=f"save_{i}_{j}"):
                                try:
                                    save_path = os.path.join(os.getcwd(), os.path.basename(filename))
                                    with open(save_path, "w", encoding="utf-8") as f:
                                        f.write(code.strip())
                                    st.success(f"Đã lưu: {save_path}")
                                except Exception as e:
                                    st.error(f"Lỗi: {e}")
                        with col2:
                            st.caption(f"Tên file đề xuất: {filename}")

# --- Xử lý User Input ---
if prompt := st.chat_input("Nhập câu hỏi (VD: Tạo một website React đơn giản)..."):
    
    # Định dạng tin nhắn Multimodal
    if MODELS[selected_model].get("type") == "multimodal" and "uploaded_image_b64" in st.session_state:
        msg_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{st.session_state['uploaded_image_b64']}"}}
        ]
    else:
        msg_content = prompt

    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": msg_content})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        reasoning_response = ""
        
        try:
            # 1. Xử lý riêng cho Vision-only Model (Nemotron Page Elements)
            if MODELS[selected_model].get("type") == "vision-only":
                if "uploaded_image_b64" not in st.session_state:
                    st.error("⚠️ Model này yêu cầu phải tải ảnh lên ở thanh bên!")
                else:
                    message_placeholder.markdown("*(Đang phân tích hình ảnh...)*")
                    invoke_url = "https://ai.api.nvidia.com/v1/cv/nvidia/nemotron-page-elements-v3"
                    headers = {
                        "Authorization": f"Bearer {MODELS[selected_model]['api_key']}",
                        "Accept": "application/json"
                    }
                    payload = {
                        "input": [{"type": "image_url", "url": f"data:image/png;base64,{st.session_state['uploaded_image_b64']}"}]
                    }
                    response = requests.post(invoke_url, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        res_json = response.json()
                        full_response = f"**Kết quả phân tích JSON:**\n```json\n{json.dumps(res_json, indent=2)}\n```"
                    else:
                        full_response = f"**Lỗi API:** {response.status_code} - {response.text}"
                        
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.rerun()

            # 2. Xử lý cho các model chuẩn OpenAI API
            else:
                params = MODELS[selected_model].get("params", {})
                kwargs = {
                    "model": MODELS[selected_model]["id"],
                    "messages": st.session_state.messages,
                    "stream": True,
                    "temperature": params.get("temperature", 0.7),
                    "top_p": params.get("top_p", 1.0),
                    "max_tokens": params.get("max_tokens", 8192)
                }
                
                # Truyền các tham số mở rộng
                if "presence_penalty" in params:
                    kwargs["presence_penalty"] = params["presence_penalty"]
                if "extra_body" in params:
                    kwargs["extra_body"] = params["extra_body"]
                
                completion = client.chat.completions.create(**kwargs)
                
                for chunk in completion:
                    if not getattr(chunk, "choices", None):
                        continue
                    
                    delta = chunk.choices[0].delta
                    
                    # Trích xuất luồng suy luận (Reasoning)
                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        reasoning_response += reasoning
                        message_placeholder.markdown("*(Đang suy luận...)*\n\n```text\n" + reasoning_response + "\n```")
                    
                    # Trích xuất nội dung chính
                    if getattr(delta, "content", None) is not None:
                        full_response += delta.content
                        
                        display_text = ""
                        if reasoning_response:
                            display_text += "### 🧠 Quá trình suy luận:\n```text\n" + reasoning_response + "\n```\n---\n"
                        display_text += full_response
                        
                        message_placeholder.markdown(display_text + "▌")
                
                # Hoàn tất hiển thị
                final_display = ""
                if reasoning_response:
                    final_display += "### 🧠 Quá trình suy luận:\n```text\n" + reasoning_response + "\n```\n---\n"
                final_display += full_response
                message_placeholder.markdown(final_display)
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.rerun()
                
        except Exception as e:
            st.error(f"Lỗi hệ thống: {str(e)}")
