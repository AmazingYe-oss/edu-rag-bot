import os
import chromadb

from llama_index.core import (
    Settings,
    VectorStoreIndex,
    StorageContext,
)
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.llms.dashscope import DashScope as DashScopeLLM
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore  # <--- 【新增】ChromaDB 专用连接器

from src.prompts import build_system_prompt
from src.document_loader import load_documents_from_directory


class RAGService:
    """
    RAG 服务类：
    【V3.0 云原生架构版】状态彻底分离，向量索引持久化至 K8s 内部的 ChromaDB！
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

    def _load_or_build_index(self):
        """
        核心改造点：连向 K8s 内部的数据库，而不是操作本地磁盘！
        """
        print(" 正在连接 K8s 内部的 ChromaDB 向量数据库...")
        
        chroma_host = os.getenv("CHROMA_HOST", "chromadb-svc")
        chroma_client = chromadb.HttpClient(host=chroma_host, port=8000)


        collection_name = "edu_knowledge_base"
        chroma_collection = chroma_client.get_or_create_collection(collection_name)

    
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

    
        if chroma_collection.count() > 0:
        
            print(f"检测到 ChromaDB [ {collection_name} ] 中已有 {chroma_collection.count()} 条知识向量，直接极速挂载！")
            
            self.index = VectorStoreIndex.from_vector_store(
                vector_store,
            )
        else:
            print(f"⚠️ ChromaDB [ {collection_name} ] 为空，正在从本地文档读取并灌入数据库...")
            
            documents = self._load_documents()
            
            self.index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context
            )
            print(" 索引构建完成，知识向量已全部成功持久化至底层 PVC 网络硬盘！")

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

        context_list =[]

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

        messages =[
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
