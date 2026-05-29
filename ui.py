import os
import requests
import json
import uuid
import gradio as gr

API_URL = os.getenv("API_URL", "http://localhost:8000/api/chat")
UPLOAD_URL = os.getenv("UPLOAD_URL", "http://localhost:8000/api/upload")

# ==========================================
# 自定义 CSS（深蓝色科技感主题）
# ==========================================
custom_css = """
/* 隐藏 Gradio 默认页脚 */
footer {display: none !important;}

/* 全局字体 */
body, .gradio-container {font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;}

/* 左侧边栏 */
#sidebar {
    background: #f8f9fa;
    border-right: 1px solid #e0e0e0;
    padding: 20px;
    height: 100vh;
    overflow-y: auto;
}

/* 右侧主区域 */
#main-area {
    padding: 20px;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

/* Chatbot 容器 */
#chatbot-container {
    flex: 1;
    overflow-y: auto;
    margin-bottom: 10px;
}

/* Chatbot 组件 */
#chatbot {
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    height: 600px;
}

/* 输入区 */
#input-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
}

/* 输入框 */
#question-input {
    border-radius: 8px;
    border: 1px solid #d0d0d0;
    padding: 10px 14px;
    font-size: 14px;
    flex: 1;
}

/* 发送按钮 */
#send-button {
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    cursor: pointer;
    transition: background 0.2s;
}
#send-button:hover {background: #1557b0;}

/* 文件上传区域 */
#upload-section {
    background: #ffffff;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-top: 16px;
}

/* 上传按钮 */
#upload-button {
    background: #34a853;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    cursor: pointer;
    transition: background 0.2s;
}
#upload-button:hover {background: #2d8f47;}

/* 折叠面板 */
#context-accordion {
    margin-top: 8px;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
}

/* 标题 */
.sidebar-title {
    font-size: 20px;
    font-weight: 600;
    color: #1a73e8;
    margin-bottom: 4px;
}
.sidebar-subtitle {
    font-size: 13px;
    color: #666;
    margin-bottom: 20px;
}
"""


def answer_question(question, history, session_id):
    """
    前端调用的函数：接入 SSE 流式输出引擎
    使用 yield 实时推流到前端 UI
    """
    if not question or not question.strip():
        yield history, ""
        return

    # 将用户消息添加到历史记录
    history = history + [(question, None)]

    payload = {
        "question": question,
        "session_id": session_id
    }

    try:
        response = requests.post(API_URL, json=payload, stream=True, timeout=60)
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
                    
                    # 更新最后一条消息（AI 回复）
                    history[-1] = (question, full_answer)
                    yield history, final_context
                    
    except Exception as e:
        history[-1] = (question, f"系统开小差了，调用后端 API 失败: {str(e)}")
        yield history, ""


def upload_file_to_oss(file):
    """
    上传文件到阿里云 OSS（使用服务端上传）
    """
    if file is None:
        return "请先选择文件。"
    
    try:
        with open(file.name, "rb") as f:
            files = {"file": (os.path.basename(file.name), f, "application/octet-stream")}
            response = requests.post(UPLOAD_URL, files=files, timeout=120)
            response.raise_for_status()
            result = response.json()
            filename = result.get("oss_filename", "未知")
            url = result.get("url", "未知")
            return f"✅ 上传成功！\n文件名：{filename}\nURL：{url}"
    except Exception as e:
        return f"❌ 上传失败：{str(e)}"


# ==========================================
# Gradio 界面构建（左右分栏）
# ==========================================
with gr.Blocks(
    title="教育内容开发公司新员工答疑机器人"
) as demo:

    # 全局状态
    session_state = gr.State(lambda: str(uuid.uuid4()))
    chatbot_state = gr.State([])

    with gr.Row(equal_height=False):
        # ========== 左侧边栏 ==========
        with gr.Column(scale=1, min_width=280, elem_id="sidebar"):
            gr.Markdown(
                '<div class="sidebar-title">🤖 教育答疑机器人</div>'
                '<div class="sidebar-subtitle">基于内部知识库的智能问答系统</div>'
            )

            # 文件上传模块
            with gr.Group(elem_id="upload-section"):
                gr.Markdown("### 📁 知识库文件上传 (OSS)")
                file_input = gr.File(
                    label="选择文件",
                    file_types=[".txt", ".pdf", ".docx", ".md", ".ipynb", ".jpg", ".png", ".zip"],
                    interactive=True,
                    scale=1
                )
                with gr.Row():
                    upload_button = gr.Button("⬆️ 上传到 OSS", elem_id="upload-button", scale=1)
                upload_result = gr.Markdown(label="上传结果", value="")

            upload_button.click(
                fn=upload_file_to_oss,
                inputs=file_input,
                outputs=upload_result
            )

        # ========== 右侧主区域 ==========
        with gr.Column(scale=3, min_width=500, elem_id="main-area"):
            # Chatbot 组件
            chatbot = gr.Chatbot(
                label="对话",
                elem_id="chatbot",
                height=600,
                avatar_images=(None, None)
            )

            # 输入区
            with gr.Row(elem_id="input-row"):
                question_input = gr.Textbox(
                    label="",
                    placeholder="输入你的问题...",
                    lines=1,
                    max_lines=4,
                    elem_id="question-input",
                    scale=10
                )
                send_button = gr.Button("发送", elem_id="send-button", scale=1, variant="primary")

            # 检索来源折叠面板
            with gr.Accordion("📚 查看本次检索到的知识库内容", open=False, elem_id="context-accordion"):
                context_output = gr.Textbox(label="检索上下文", lines=8, interactive=False)

    # ========== 事件绑定 ==========
    def respond(question, history, session_id):
        for new_history, context in answer_question(question, history, session_id):
            yield new_history, context

    send_button.click(
        fn=respond,
        inputs=[question_input, chatbot_state, session_state],
        outputs=[chatbot, context_output]
    ).then(
        fn=lambda: "",
        outputs=question_input
    )

    question_input.submit(
        fn=respond,
        inputs=[question_input, chatbot_state, session_state],
        outputs=[chatbot, context_output]
    ).then(
        fn=lambda: "",
        outputs=question_input
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=gr.themes.Soft(),
        css=custom_css
    )
