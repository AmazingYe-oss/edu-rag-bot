import os
import dashvector
from typing import Any
from pydantic import PrivateAttr

from llama_index.core import (
    Settings,
    VectorStoreIndex,
    StorageContext,
)
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.llms.dashscope import DashScope as DashScopeLLM
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.vector_stores.dashvector import DashVectorStore as OriginalDashVectorStore

class DashVectorStore(OriginalDashVectorStore):
    _client: Any = PrivateAttr(default=None)
    _support_sparse_vector: bool = PrivateAttr(default=False)

    @property
    def client(self) -> Any:
        return self._client


from src.prompts import build_system_prompt
from src.document_loader import load_documents_from_directory


class RAGService:
    """
    RAG 服务类：
    【V5.0 Serverless + SSE 流式终极版】
    状态彻底分离，接入阿里云 DashVector，并支持打字机流式输出！
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
        使用自定义文档加载器读取数据。
        """
        data_dir = self.config["data_dir"]
        return load_documents_from_directory(data_dir)

    def _load_or_build_index(self):
        """
        核心改造点：挂载阿里云 Serverless DashVector。
        """
        print("🚀 正在连接阿里云 DashVector 云端向量数据库...")

        dv_api_key = os.getenv("DASHVECTOR_API_KEY")
        dv_endpoint = os.getenv("DASHVECTOR_ENDPOINT")

        if not dv_api_key or not dv_endpoint:
            raise ValueError("🚨 致命错误：未找到 DASHVECTOR_API_KEY 或 DASHVECTOR_ENDPOINT 环境变量！")

        client = dashvector.Client(api_key=dv_api_key, endpoint=dv_endpoint)
        collection_name = "edu_knowledge_base"

        response = client.list()
        collections = response.output if response else []

        is_empty = True
        
        if collection_name not in collections:
            print(f"⚠️ 云端未找到集合 [{collection_name}]，正在阿里云创建 (维度: 1536)...")
            client.create(name=collection_name, dimension=1536)
        
        collection = client.get(collection_name)
        stats = collection.stats()
        try:
            if isinstance(stats.output, dict):
                doc_count = int(stats.output.get("total_doc_count", 0))
            else:
                doc_count = int(getattr(stats.output, "total_doc_count", 0))
            
            if doc_count > 0:
                is_empty = False
                print(f"✅ 检测到 DashVector 中已有 {doc_count} 条知识向量，准备极速挂载！")
        except Exception as e:
            print(f"获取集合统计信息失败，默认按空集合处理: {e}")

        vector_store = DashVectorStore(
            collection=collection
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        if not is_empty:
            self.index = VectorStoreIndex.from_vector_store(
                vector_store,
            )
        else:
            print(f"⏳ 云端集合为空，正在从本地文档读取并灌入阿里云数据库...")
            documents = self._load_documents()
            self.index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context
            )
            print("🎉 索引构建完成，知识向量已全部成功持久化至阿里云 Serverless 节点！")

        self.retriever = self.index.as_retriever(
            similarity_top_k=self.config.get("similarity_top_k", 3)
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
        对外问答入口 (旧版普通阻塞输出，保留用于兼容)。
        """
        if not question or not question.strip():
            return "请输入有效的问题。", ""

        context = self._retrieve_context(question)
        user_prompt = self._build_user_prompt(question=question, context=context)

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=self.system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        response = self.llm.chat(messages)
        return response.message.content, context

    def stream_ask(self, question):
        """
        💥 对外问答入口 (V5.0 SSE 纯流式输出版)。
        大厂必备，让大模型像打字机一样一个字一个字往外吐！
        """
        if not question or not question.strip():
            raise ValueError("请输入有效的问题。")

        context = self._retrieve_context(question)
        user_prompt = self._build_user_prompt(question=question, context=context)

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=self.system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        # 🚨 核心突变：使用 stream_chat 替换 chat，返回生成器
        response_generator = self.llm.stream_chat(messages)

        return response_generator, context
