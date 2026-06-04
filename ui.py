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


def _batch_upload_url() -> str:
    return f"{API_BASE}/documents/batch"


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


def upload_file_to_oss(file, user_id):
    if file is None:
        return "请先选择文件"
    if not user_id or not user_id.strip():
        return "请输入用户 ID"
    try:
        with open(file.name, "rb") as f:
            files = {"file": (os.path.basename(file.name), f, "application/octet-stream")}
            data = {"user_id": user_id}
            response = requests.post(_upload_url(), files=files, data=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            filename = result.get("filename", "未知")
            indexed = result.get("indexed", False)
            index_msg = result.get("index_message", "")
            summary = result.get("summary", "")
            status = "✅ 已入库" if indexed else "⚠️ 未入库"
            return f"✅ 上传成功！{status}\n文件: {filename}\n{index_msg}\n\n📝 摘要: {summary}"
    except Exception as e:
        return f"❌ 上传失败：{str(e)}"


def batch_upload_files(files, user_id):
    if not files:
        return "请先选择文件"
    if not user_id or not user_id.strip():
        return "请输入用户 ID"
    try:
        files_data = [("files", (os.path.basename(f.name), open(f.name, "rb"), "application/octet-stream")) for f in files]
        data = {"user_id": user_id}
        response = requests.post(_batch_upload_url(), files=files_data, data=data, timeout=300)
        
        # 关闭文件句柄
        for _, (_, fh, _) in files_data:
            fh.close()
        
        response.raise_for_status()
        result = response.json()
        
        total = result.get("total", 0)
        success = result.get("success_count", 0)
        failed = result.get("failed_count", 0)
        
        output_lines = [f"📊 批量上传完成：共 {total} 个文件，成功 {success} 个，失败 {failed} 个\n"]
        
        for i, item in enumerate(result.get("results", []), 1):
            fname = item.get("filename", "未知")
            indexed = item.get("indexed", False)
            index_msg = item.get("index_message", "")
            summary = item.get("summary", "")
            status = "✅" if indexed else "❌"
            output_lines.append(f"{i}. {status} {fname}\n   {index_msg}\n   摘要: {summary}\n")
        
        return "\n".join(output_lines)
    except Exception as e:
        return f"❌ 批量上传失败：{str(e)}"


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
            
            **📁 文档入库 (OSS)**
            """)
            
            user_id_input = gr.Textbox(label="用户 ID", placeholder="请输入用户 ID", value="user_default")
            
            gr.Markdown("**单文件上传**")
            file_input = gr.File(label="", file_count="single", type="filepath")
            upload_button = gr.Button("⬆️ 上传单个文件", variant="secondary")
            upload_result = gr.Markdown(value="")
            
            gr.Markdown("**批量上传 (最多 10 个)**")
            batch_file_input = gr.File(label="", file_count="multiple", type="filepath", file_types=[".pdf", ".docx", ".txt", ".md"])
            batch_upload_button = gr.Button("📤 批量上传", variant="primary")
            batch_upload_result = gr.Markdown(value="")
                
            upload_button.click(fn=upload_file_to_oss, inputs=[file_input, user_id_input], outputs=upload_result)
            batch_upload_button.click(fn=batch_upload_files, inputs=[batch_file_input, user_id_input], outputs=batch_upload_result)

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
