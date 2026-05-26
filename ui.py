# ui.py
import os
import requests
import gradio as gr

API_URL = os.getenv("API_URL", "http://localhost:8000/api/chat")

def answer_question(question):
    """
    前端调用的函数：不再做本地计算，纯纯的 HTTP 调用！
    """
    if not question or not question.strip():
        return "请输入有效的问题。", ""
        
    try:
        response = requests.post(API_URL, json={"question": question}, timeout=60)
        response.raise_for_status() 
        data = response.json()
        return data.get("answer", "未能获取回答"), data.get("context", "")
    except Exception as e:
        return f"系统开小差了，调用后端 API 失败: {str(e)}", ""

with gr.Blocks(title="教育内容开发公司新员工答疑机器人") as demo:

    gr.Markdown("# 教育内容开发公司新员工答疑机器人\n欢迎使用内部知识库答疑系统...")

    with gr.Row():
        question_input = gr.Textbox(label="请输入你的问题", placeholder="例如：内容审核流程是什么？", lines=3)

    ask_button = gr.Button("提交问题", variant="primary")
    answer_output = gr.Markdown(label="回答")

    with gr.Accordion("查看本次检索到的知识库内容", open=False):
        context_output = gr.Textbox(label="检索上下文", lines=12)
    ask_button.click(fn=answer_question, inputs=question_input, outputs=[answer_output, context_output])
    question_input.submit(fn=answer_question, inputs=question_input, outputs=[answer_output, context_output])
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
