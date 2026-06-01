import os
import requests
import json
import uuid
import gradio as gr

API_BASE = os.getenv("API_BASE", "http://localhost:8000/api/v1")


def _conversation_url(conversation_id: str) -> str:
    return f"{API_BASE}/conversations/{conversation_id}/messages"


def _upload_url() -> str:
    return f"{API_BASE}/documents"


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
    history.append({"role": "user", "content": user_message})
    return "", history

def answer_question(history, session_id):
    if not history or history[-1]["role"] != "user":
        yield history, ""
        return


    raw_content = history[-1]["content"]
    if isinstance(raw_content, list) and len(raw_content) > 0 and isinstance(raw_content[0], dict):
        question = raw_content[0].get("text", "")
    else:
        question = str(raw_content)

    req_payload = {"content": question}

    history.append({"role": "assistant", "content": ""})

    try:
        url = _conversation_url(session_id)
        response = requests.post(url, json=req_payload, stream=True, timeout=60)
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
            response = requests.post(_upload_url(), files=files, timeout=120)
            response.raise_for_status()
            result = response.json()
            filename = result.get("filename", "未知")
            indexed = result.get("indexed", False)
            index_msg = result.get("index_message", "")
            status = "✅ 已入库" if indexed else "⚠️ 未入库"
            return f"✅ 上传成功！{status}\n文件: {filename}\n{index_msg}"
    except Exception as e:
        return f"❌ 上传失败：{str(e)}"


theme = gr.themes.Soft(
    primary_hue="indigo",
    neutral_hue="slate"
)


with gr.Blocks(title="AI 知识库助手", fill_height=True) as demo:
    session_state = gr.State(lambda: str(uuid.uuid4()))

    with gr.Row(equal_height=True):
        with gr.Column(scale=1, min_width=260, variant="panel"):
            gr.Markdown("""
            ### 🎓 知识库助手
            <span style="color: gray; font-size: 13px;">Edu RAG API v6.0</span>
            
            ---
            
            **📁 内部文档入库 (OSS)**
            """)
            
            file_input = gr.File(label="", file_count="single", type="filepath")
            upload_button = gr.Button("⬆️ 同步至云端", variant="secondary")
            upload_result = gr.Markdown(value="")
                
            upload_button.click(fn=upload_file_to_oss, inputs=file_input, outputs=upload_result)

        with gr.Column(scale=4):
            chatbot = gr.Chatbot(
                show_label=False,
                scale=1, 
                avatar_images=("👤", "🤖")
            )

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
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=theme, css=custom_css)
