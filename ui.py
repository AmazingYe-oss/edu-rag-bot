import os
import requests
import json
import uuid
import gradio as gr

API_URL = os.getenv("API_URL", "http://localhost:8000/api/chat")
UPLOAD_URL = os.getenv("UPLOAD_URL", "http://localhost:8000/api/upload")

def answer_question(question, session_id):
    """
    前端调用的函数：接入 SSE 流式输出引擎
    使用 yield 实时推流到前端 UI
    """
    if not question or not question.strip():
        # 如果没有问题，立刻返回
        yield "请输入有效的问题。", ""
        return

    # 把问题和前端生成的专属 session_id 发给后端
    payload = {
        "question": question,
        "session_id": session_id
    }

    try:
        # 🚨 核心突变 1：增加 stream=True 参数，告诉 requests 不要死等结果
        response = requests.post(API_URL, json=payload, stream=True, timeout=60)
        response.raise_for_status()
        
        full_answer = ""
        final_context = ""
        
        # 🚨 核心突变 2：逐行读取后端吐出的 SSE 流式数据
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                
                # 过滤出符合 SSE 标准的数据行
                if decoded_line.startswith("data: "):
                    # 剥离 "data: " 前缀，解析纯 JSON
                    data_json = json.loads(decoded_line[6:])
                    
                    # 取出每次新吐出的片段 (delta) 和 上下文
                    delta = data_json.get("delta", "")
                    full_answer += delta
                    
                    if "context" in data_json:
                        final_context = data_json["context"]
                    
                    # 🚨 核心突变 3：使用 yield 动态更新 Gradio 的页面组件
                    # Gradio 只要检测到 yield，就会立刻把当前的 full_answer 刷新到屏幕上！
                    yield full_answer, final_context
                    
    except Exception as e:
        yield f"系统开小差了，调用后端 API 失败: {str(e)}", ""


def upload_file_to_oss(file):
    """
    上传文件到阿里云 OSS（使用预签名 URL）
    """
    if file is None:
        return "请先选择文件。"
    
    try:
        # 1. 获取预签名上传 URL
        presigned_response = requests.post(
            f"{UPLOAD_URL}/presigned",
            json={"filename": os.path.basename(file.name)},
            timeout=30
        )
        presigned_response.raise_for_status()
        presigned_data = presigned_response.json()
        upload_url = presigned_data["upload_url"]
        oss_filename = presigned_data["oss_filename"]
        
        # 2. 使用预签名 URL 上传文件
        with open(file.name, "rb") as f:
            upload_response = requests.put(
                upload_url,
                data=f,
                timeout=120
            )
            upload_response.raise_for_status()
        
        # 3. 构造可访问的 URL
        file_url = f"https://{os.getenv('OSS_BUCKET_NAME', 'public')}.{os.getenv('OSS_ENDPOINT', 'oss-cn-shanghai.aliyuncs.com')}/{oss_filename}"
        
        return f"✅ 上传成功！\n文件名：{oss_filename}\nURL：{file_url}"
    except Exception as e:
        return f"❌ 上传失败：{str(e)}"


# ==========================================
# Gradio 界面构建
# ==========================================
with gr.Blocks(title="教育内容开发公司新员工答疑机器人") as demo:

    gr.Markdown("# 🤖 教育内容开发公司新员工答疑机器人\n欢迎使用内部知识库答疑系统（已接入阿里云打字机引擎）")

    # 🚨 核心突变 4：使用 gr.State 为每个打开网页的用户自动生成唯一的 Session ID
    # 这样甲和乙同时打开网页，他们的 Redis 记忆是完全独立的！
    session_state = gr.State(lambda: str(uuid.uuid4()))

    with gr.Row():
        question_input = gr.Textbox(label="请输入你的问题", placeholder="例如：内容审核流程是什么？", lines=3)

    ask_button = gr.Button("🚀 提交问题", variant="primary")
    answer_output = gr.Markdown(label="回答 (实时生成中...)")

    with gr.Accordion("📚 查看本次检索到的知识库内容", open=False):
        context_output = gr.Textbox(label="检索上下文", lines=12)
        
    # 绑定点击事件，注意要把 session_state 传进去
    ask_button.click(
        fn=answer_question, 
        inputs=[question_input, session_state], 
        outputs=[answer_output, context_output]
    )
    
    # 绑定回车事件
    question_input.submit(
        fn=answer_question, 
        inputs=[question_input, session_state], 
        outputs=[answer_output, context_output]
    )

    # ==========================================
    # 文件上传区域
    # ==========================================
    gr.Markdown("---")
    gr.Markdown("## 📁 文件上传到阿里云 OSS")

    with gr.Row():
        file_input = gr.File(
            label="选择要上传的文件",
            file_types=[".txt", ".pdf", ".docx", ".md", ".ipynb", ".jpg", ".png", ".zip"],
            interactive=True
        )
        upload_button = gr.Button("⬆️ 上传到 OSS", variant="secondary")

    upload_result = gr.Markdown(label="上传结果")

    upload_button.click(
        fn=upload_file_to_oss,
        inputs=file_input,
        outputs=upload_result
    )

if __name__ == "__main__":
    # 启动 Gradio 前端
    demo.launch(server_name="0.0.0.0", server_port=7860)
