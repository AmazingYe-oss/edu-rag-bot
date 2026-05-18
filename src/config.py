import os
from dotenv import load_dotenv


def load_config():
    load_dotenv()

    config = {
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY"),
        "llm_model": os.getenv("DASHSCOPE_LLM_MODEL", "qwen-plus"),
        "embed_model": os.getenv("DASHSCOPE_EMBED_MODEL", "text-embedding-v3"),
        "data_dir": os.getenv("DATA_DIR", "data"),
        "persist_dir": os.getenv("PERSIST_DIR", "storage"),
        "similarity_top_k": int(os.getenv("SIMILARITY_TOP_K", "3")),
    }

    if not config["dashscope_api_key"]:
        raise ValueError("DASHSCOPE_API_KEY is not set in environment variables.")

    return config
