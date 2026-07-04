import streamlit as st
from openai import OpenAI
import os
import re

# --- Cấu hình Models ---
MODELS = {
    "GLM-5.2": {
        "id": "z-ai/glm-5.2",
        "api_key": "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"
    },
    "MiniMax-M3": {
        "id": "minimaxai/minimax-m3",
        "api_key": "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"
    },
    "Nemotron-3-Ultra": {
        "id": "nvidia/nemotron-3-ultra-550b-a55b",
        "api_key": "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"
    }
}

st.set_page_config(page_title="NVIDIA AI Coding Agent", page_icon="🤖", layout="wide")

st.title("🤖 NVIDIA NIM - AI Coding Agent")

# --- Thanh bên (Sidebar) ---
with st.sidebar:
    st.header("⚙️ Cấu hình Agent")
    selected_model = st.selectbox("Chọn Model:", list(MODELS.keys()))
    
    st.divider()
    
    st.header("📂 Ngữ cảnh (Context)")
    
    # Tính năng Upload File
    uploaded_file = st.file_uploader("Tải lên file văn bản/code", type=["txt", "py", "md", "csv", "json", "js", "html", "css"])
    if uploaded_file:
        file_content = uploaded_file.read().decode("utf-8")
        st.session_state["uploaded_file_context"] = f"Nội dung file {uploaded_file.name}:\n```\n{file_content}\n```\n"
        st.success(f"Đã nạp file: {uploaded_file.name}")
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
                # Bỏ qua các thư mục không cần thiết để tiết kiệm token
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['venv', 'env', '__pycache__', 'node_modules']]
                for file in files:
                    if file.endswith((".py", ".js", ".html", ".css", ".md", ".txt")):
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
    if st.button("Xóa lịch sử chat"):
        st.session_state.messages = []
        st.rerun()

# --- Khởi tạo Client API ---
@st.cache_resource(show_spinner=False)
def get_client(model_name):
    # Khởi tạo lại client nếu đổi model để dùng đúng API key
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=MODELS[model_name]["api_key"]
    )

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

# Xây dựng System prompt tổng hợp (kết hợp với file và codebase upload)
current_system_prompt = SYSTEM_PROMPT
if "uploaded_file_context" in st.session_state:
    current_system_prompt += "\n\n" + st.session_state["uploaded_file_context"]
if "codebase_context" in st.session_state:
    current_system_prompt += "\n\n" + st.session_state["codebase_context"]

# Cập nhật prompt vào lịch sử hiện tại
if st.session_state.messages:
    st.session_state.messages[0] = {"role": "system", "content": current_system_prompt}

# --- Hiển thị Chat và Lưu File ---
for i, message in enumerate(st.session_state.messages):
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Nếu là AI phản hồi, phân tích lấy khối code để hiển thị nút Lưu
            if message["role"] == "assistant":
                code_blocks = re.findall(r'```(\w+)?\n(.*?)```', message["content"], re.DOTALL)
                if code_blocks:
                    for j, (lang, code) in enumerate(code_blocks):
                        # Cố đoán tên file từ dòng đầu tiên
                        first_line = code.strip().split('\n')[0]
                        filename = f"generated_code_{i}_{j}.{lang if lang else 'txt'}"
                        if "File:" in first_line:
                            try:
                                filename = first_line.split("File:")[1].strip()
                            except: pass
                        
                        col1, col2 = st.columns([1, 5])
                        with col1:
                            if st.button("Lưu file này", key=f"save_{i}_{j}"):
                                try:
                                    # Lưu vào thư mục hiện hành hoặc thư mục cha nếu được chỉ định tuyệt đối
                                    save_path = os.path.join(os.getcwd(), os.path.basename(filename))
                                    with open(save_path, "w", encoding="utf-8") as f:
                                        f.write(code.strip())
                                    st.success(f"Đã lưu thành công: {save_path}")
                                except Exception as e:
                                    st.error(f"Lỗi: {e}")
                        with col2:
                            st.caption(f"Tên file đề xuất: {filename}")

# --- Nhập yêu cầu từ người dùng ---
if prompt := st.chat_input("Nhập câu hỏi hoặc yêu cầu (VD: Đọc codebase và tìm lỗi)..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        reasoning_response = ""
        
        try:
            # Cấu hình tham số API chung
            kwargs = {
                "model": MODELS[selected_model]["id"],
                "messages": st.session_state.messages,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "stream": True
            }
            
            # Xử lý đặc thù cho Nemotron (có chế độ suy nghĩ)
            if selected_model == "Nemotron-3-Ultra":
                kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}
                kwargs["max_tokens"] = 16384
            
            # Gọi API
            completion = client.chat.completions.create(**kwargs)
            
            # Đọc dữ liệu stream
            for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                
                delta = chunk.choices[0].delta
                
                # Nhận luồng suy luận của Nemotron
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    reasoning_response += reasoning
                    message_placeholder.markdown("*(Đang suy luận...)*\n\n```text\n" + reasoning_response + "\n```")
                
                # Nhận nội dung trả lời chính
                if getattr(delta, "content", None) is not None:
                    full_response += delta.content
                    
                    display_text = ""
                    if reasoning_response:
                        display_text += "### 🧠 Quá trình suy luận:\n```text\n" + reasoning_response + "\n```\n---\n"
                    display_text += full_response
                    
                    message_placeholder.markdown(display_text + "▌")
            
            # Hiển thị hoàn chỉnh khi stream kết thúc
            final_display = ""
            if reasoning_response:
                final_display += "### 🧠 Quá trình suy luận:\n```text\n" + reasoning_response + "\n```\n---\n"
            final_display += full_response
            message_placeholder.markdown(final_display)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.rerun() # Tải lại trang để render nút "Lưu file"
            
        except Exception as e:
            st.error(f"Lỗi API: {str(e)}")
