import gradio as gr

from src.config import load_config
from src.rag_service import RAGService


# 1. 加载配置
config = load_config()

# 2. 初始化 RAG 服务
rag_service = RAGService(config)


def answer_question(question):
    """
    Gradio 前端调用的后端函数
    """
    answer, context = rag_service.ask(question)
    return answer, context


with gr.Blocks(
    title="教育内容开发公司新员工答疑机器人"
) as demo:

    gr.Markdown(
        """
# 教育内容开发公司新员工答疑机器人

欢迎使用内部知识库答疑系统。  
你可以询问：
- 新员工入职流程
- 内容审核流程
- 题目编写规范
- 课程内容开发规范
- 系统权限申请方式
"""
    )

    with gr.Row():
        question_input = gr.Textbox(
            label="请输入你的问题",
            placeholder="例如：内容审核流程是什么？",
            lines=3
        )

    ask_button = gr.Button("提交问题", variant="primary")

    answer_output = gr.Markdown(
        label="回答"
    )

    with gr.Accordion("查看本次检索到的知识库内容", open=False):
        context_output = gr.Textbox(
            label="检索上下文",
            lines=12
        )

    gr.Examples(
        examples=[
            ["内容审核流程是什么？"],
            ["新员工遇到课程内容规范问题应该怎么办？"],
            ["题目编写时需要注意什么？"],
            ["如果遇到系统权限问题怎么办？"],
        ],
        inputs=question_input
    )

    # 关键：前后端绑定
    ask_button.click(
        fn=answer_question,
        inputs=question_input,
        outputs=[answer_output, context_output]
    )

    question_input.submit(
        fn=answer_question,
        inputs=question_input,
        outputs=[answer_output, context_output]
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860
    )

