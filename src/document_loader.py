import json
import asyncio
from pathlib import Path
from datetime import datetime

import docx2txt
from pypdf import PdfReader
from llama_index.core.schema import Document
from llama_index.core.node_parser import RecursiveCharacterTextSplitter
from llama_index.llms.dashscope import DashScope as DashScopeLLM


def read_txt_file(file_path: Path) -> str:
    """
    读取 txt / md 文件，兼容 UTF-8、GBK、GB18030。
    """
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb18030"]

    for encoding in encodings:
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"无法识别文件编码：{file_path}"
    )


def read_pdf_file(file_path: Path) -> str:
    """
    使用 pypdf 读取 PDF 文本。
    注意：扫描版 PDF 可能提取不出文字。
    """
    reader = PdfReader(str(file_path))

    texts = []

    for page_index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""

        if page_text.strip():
            texts.append(f"\n\n--- 第 {page_index} 页 ---\n{page_text}")

    return "\n".join(texts).strip()


def read_docx_file(file_path: Path) -> str:
    """
    使用 docx2txt 读取 Word 文档文本。
    """
    text = docx2txt.process(str(file_path))
    return text.strip() if text else ""


def read_ipynb_file(file_path: Path) -> str:
    """
    读取 ipynb 文件，只提取 markdown 和 code 单元格内容。
    如果你不想让 ipynb 入库，可以在 load_documents_from_directory 里跳过。
    """
    content = file_path.read_text(encoding="utf-8")
    notebook = json.loads(content)

    parts = []

    for cell in notebook.get("cells", []):
        cell_type = cell.get("cell_type", "")
        source = cell.get("source", [])

        if isinstance(source, list):
            source_text = "".join(source)
        else:
            source_text = str(source)

        if not source_text.strip():
            continue

        if cell_type == "markdown":
            parts.append(f"\n\n### Markdown 单元\n{source_text}")
        elif cell_type == "code":
            parts.append(f"\n\n### Code 单元\n{source_text}")

    return "\n".join(parts).strip()


async def generate_global_summary(text: str, api_key: str) -> str:
    """
    异步调用大模型生成全局摘要。
    """
    llm = DashScopeLLM(model="qwen-plus", api_key=api_key)
    prompt = f"请为以下文档生成一段100字以内的全局摘要，包含文档类别、核心主题和适用对象：\n\n{text[:3000]}"
    
    try:
        response = await llm.ainvoke(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"生成摘要失败: {e}")
        return "未生成摘要"


def chunk_document_with_metadata(
    text: str, 
    user_id: str, 
    filename: str, 
    summary: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50
) -> list[Document]:
    """
    智能切片并绑定多租户 Metadata。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separator="\n",
    )
    
    nodes = splitter.get_nodes_from_documents([Document(text=text)])
    
    upload_time = datetime.now().isoformat()
    metadata = {
        "user_id": user_id,
        "filename": filename,
        "upload_time": upload_time,
        "summary": summary,
    }
    
    # 为每个切片绑定相同的元数据
    for node in nodes:
        node.metadata.update(metadata)
        
    return nodes


def load_single_file(file_path: Path) -> Document | None:
    """
    根据文件类型读取单个文件，并封装成 LlamaIndex Document。
    """
    suffix = file_path.suffix.lower()

    try:
        if suffix in [".txt", ".md"]:
            text = read_txt_file(file_path)

        elif suffix == ".pdf":
            text = read_pdf_file(file_path)

        elif suffix == ".docx":
            text = read_docx_file(file_path)

        elif suffix == ".ipynb":
            # 如果不想让 ipynb 进入知识库，可以直接 return None
            text = read_ipynb_file(file_path)

        else:
            print(f"跳过不支持的文件类型：{file_path}")
            return None

        if not text or not text.strip():
            print(f"文件未提取到有效文本，已跳过：{file_path}")
            return None

        return Document(
            text=text,
            metadata={
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_type": suffix,
            }
        )

    except Exception as e:
        print(f"读取文件失败：{file_path}，原因：{e}")
        return None


def load_documents_from_directory(data_dir: str):
    """
    从目录递归加载文档。
    """
    data_path = Path(data_dir)

    if not data_path.exists():
        raise FileNotFoundError(f"知识库目录不存在：{data_dir}")

    documents = []

    for file_path in data_path.rglob("*"):
        if not file_path.is_file():
            continue

        document = load_single_file(file_path)

        if document is not None:
            documents.append(document)

    if not documents:
        raise ValueError(f"没有读取到有效文档，请检查目录：{data_dir}")

    print(f"成功加载有效文档数量：{len(documents)}")

    return documents
