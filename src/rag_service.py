import os

from llama_index.core import (
    Settings,
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.llms.dashscope import DashScope as DashScopeLLM
from llama_index.embeddings.dashscope import DashScopeEmbedding

from src.prompts import build_system_prompt
from src.document_loader import load_documents_from_directory


class RAGService:
    """
    RAG 服务类：
    负责文档加载、索引构建、索引持久化、检索和大模型问答
    """

    def __init__(self, config):
        self.config = config
        self.llm = None
        self.index = None
        self.retriever = None
        self.system_prompt = build_system_prompt()

        self._configure_models()
        self._load_or_build_index()

    def _configure_models(self):
        """
        配置 DashScope LLM 和 Embedding 模型。
        """
        self.llm = DashScopeLLM(
            model=self.config["llm_model"],
            api_key=self.config["dashscope_api_key"],
        )

        embed_model = DashScopeEmbedding(
            model=self.config["embed_model"],
            api_key=self.config["dashscope_api_key"],
        )

        Settings.llm = self.llm
        Settings.embed_model = embed_model

    def _load_documents(self):
        """
        使用自定义文档加载器读取 PDF / DOCX / TXT / MD / IPYNB。
        """
        data_dir = self.config["data_dir"]
        return load_documents_from_directory(data_dir)

    def _has_persisted_index(self):
        """
        判断本地是否已经存在持久化索引。
        """
        persist_dir = self.config["persist_dir"]

        if not os.path.exists(persist_dir):
            return False

        # 不同版本 LlamaIndex 生成的文件名可能略有不同。
        # 这里用核心文件判断。
        required_files = [
            "docstore.json",
            "index_store.json",
        ]

        return all(
            os.path.exists(os.path.join(persist_dir, file))
            for file in required_files
        )

    def _load_or_build_index(self):
        """
        如果本地已有索引，则加载；
        如果没有，则从文档构建索引并保存。
        """
        persist_dir = self.config["persist_dir"]

        if self._has_persisted_index():
            print(f"检测到已有索引，正在从 {persist_dir} 加载...")

            storage_context = StorageContext.from_defaults(
                persist_dir=persist_dir
            )

            self.index = load_index_from_storage(storage_context)

        else:
            print("未检测到已有索引，正在从文档构建新索引...")

            documents = self._load_documents()

            self.index = VectorStoreIndex.from_documents(documents)

            self.index.storage_context.persist(
                persist_dir=persist_dir
            )

            print(f"索引已保存到：{persist_dir}")

        self.retriever = self.index.as_retriever(
            similarity_top_k=self.config["similarity_top_k"]
        )

    def _retrieve_context(self, question):
        """
        根据用户问题检索相关知识片段。
        """
        nodes = self.retriever.retrieve(question)

        if not nodes:
            return "未检索到相关知识库内容。"

        context_list = []

        for i, node in enumerate(nodes, start=1):
            content = node.get_content()
            metadata = node.metadata or {}

            file_name = metadata.get("file_name", "未知文件")

            context_list.append(
                f"【参考资料 {i}｜来源：{file_name}】\n{content}"
            )

        return "\n\n".join(context_list)

    def _build_user_prompt(self, question, context):
        """
        构建 user role 内容。
        """
        user_prompt = f"""
下面是从知识库中检索到的上下文资料：

---------------------
{context}
---------------------

请基于以上上下文资料回答用户问题。

用户问题：
{question}
"""
        return user_prompt.strip()

    def ask(self, question):
        """
        对外问答入口。
        """
        if not question or not question.strip():
            return "请输入有效的问题。", ""

        context = self._retrieve_context(question)

        user_prompt = self._build_user_prompt(
            question=question,
            context=context
        )

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=self.system_prompt
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt
            ),
        ]

        response = self.llm.chat(messages)

        answer = response.message.content

        return answer, context
