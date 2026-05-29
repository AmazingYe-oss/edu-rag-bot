import os
import requests
import json
import uuid
import gradio as gr

API_URL = os.getenv("API_URL", "http://localhost:8000/api/chat")
UPLOAD_URL = os.getenv("UPLOAD_URL", "http://localhost:8000/api/upload")

# 极简 CSS：绝对不写死颜色！全靠 Gradio 自身的变量自适应
custom_css = """
footer {display: none !important;}
/* 让输入区像一个精致的圆角对话框 */
#input-row { 
    border-radius: 12px; 
    border: 1px solid var(--border-color-primary); 
    background: var(--background-fill-primary); 
    padding: 6px; 
}
"""

def user_submit(user_message, history):
    if not user_message.strip():
        return "", history
    # 6.0 唯一指定的字典格式
    history.append({"role": "user", "content": user_message})
    return "", history

def answer_question(history, session_id):
    if not history or history[-1]["role"] != "user":
        yield history, ""
        return

    # 🔪 核心修复：剥开 Gradio 6.0 的多模态“马甲”，提取纯文本
    raw_content = history[-1]["content"]
    if isinstance(raw_content, list) and len(raw_content) > 0 and isinstance(raw_content[0], dict):
        # 如果是 [{'text': '我是谁', 'type': 'text'}] 这种格式，提取 'text'
        question = raw_content[0].get("text", "")
    else:
        # 如果它乖乖的是字符串，直接转字符串
        question = str(raw_content)

    # 组装给后端的 Payload，此时 question 已经是纯正的 "我是谁" 了
    req_payload = {"question": question, "session_id": session_id}

    history.append({"role": "assistant", "content": ""})

    try:
        response = requests.post(API_URL, json=req_payload, stream=True, timeout=60)
        response.raise_for_status()

        full_answer = ""
        final_context = ""

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_json = json.loads(decoded_line[6:])
                    delta = data_json.get("delta", "")
                    full_answer += delta

                    if "context" in data_json:
                        final_context = data_json["context"]

                    history[-1]["content"] = full_answer
                    yield history, final_context

    except Exception as e:
        history[-1]["content"] = f"⚠️ 系统连接失败: {str(e)}"
        yield history, ""


def upload_file_to_oss(file):
    if file is None:
        return "请先选择文件"
    try:
        with open(file.name, "rb") as f:
            files = {"file": (os.path.basename(file.name), f, "application/octet-stream")}
            response = requests.post(UPLOAD_URL, files=files, timeout=120)
            response.raise_for_status()
            result = response.json()
            filename = result.get("oss_filename", "未知")
            return f"✅ 上传成功！云端路径：\n{filename}"
    except Exception as e:
        return f"❌ 上传失败：{str(e)}"

# 选用清爽的 Soft 靛蓝色主题
theme = gr.themes.Soft(
    primary_hue="indigo",
    neutral_hue="slate"
)

# ⚠️ 修复 1：把 css 和 theme 从这里去掉了
with gr.Blocks(title="AI 知识库助手", fill_height=True) as demo:
    session_state = gr.State(lambda: str(uuid.uuid4()))

    with gr.Row(equal_height=True):
        # ========== 左侧边栏 ==========
        with gr.Column(scale=1, min_width=260, variant="panel"):
            gr.Markdown("""
            ### 🎓 知识库助手
            <span style="color: gray; font-size: 13px;">Edu RAG Backend v5.0</span>
            
            ---
            
            **📁 内部文档入库 (OSS)**
            """)
            
            file_input = gr.File(label="", file_count="single", type="filepath")
            upload_button = gr.Button("⬆️ 同步至云端", variant="secondary")
            upload_result = gr.Markdown(value="")
                
            upload_button.click(fn=upload_file_to_oss, inputs=file_input, outputs=upload_result)

        # ========== 右侧主舞台 ==========
        with gr.Column(scale=4):
            # ⚠️ 修复 2：去掉了报错的 type 参数
            chatbot = gr.Chatbot(
                show_label=False,
                scale=1, 
                avatar_images=("👤", "🤖")
            )

            # 输入区
            with gr.Row(elem_id="input-row"):
                question_input = gr.Textbox(
                    show_label=False,
                    placeholder="想问点什么？按 Enter 快速发送...",
                    container=False,
                    scale=8
                )
                send_button = gr.Button("发送 ✨", variant="primary", scale=1, min_width=100)

            with gr.Accordion("🔍 溯源追踪 (查看检索到的原始资料)", open=False):
                context_output = gr.Textbox(show_label=False, lines=3, interactive=False, container=False)

    # ========== 事件绑定 ==========
    send_button.click(
        fn=user_submit, 
        inputs=[question_input, chatbot], 
        outputs=[question_input, chatbot],
        queue=False
    ).then(
        fn=answer_question, 
        inputs=[chatbot, session_state], 
        outputs=[chatbot, context_output]
    )

    question_input.submit(
        fn=user_submit, 
        inputs=[question_input, chatbot], 
        outputs=[question_input, chatbot],
        queue=False
    ).then(
        fn=answer_question, 
        inputs=[chatbot, session_state], 
        outputs=[chatbot, context_output]
    )

if __name__ == "__main__":
    # ⚠️ 修复 3：按照 6.0 官方规范，把 theme 和 css 放在 launch 里！
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=theme, css=custom_css)
