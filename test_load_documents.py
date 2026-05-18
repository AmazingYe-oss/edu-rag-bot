from src.document_loader import load_documents_from_directory


def main():
    documents = load_documents_from_directory("data")

    print(f"成功读取有效文档数量：{len(documents)}")

    for i, doc in enumerate(documents, start=1):
        print("=" * 80)
        print(f"文档 {i}")
        print("metadata:")
        print(doc.metadata)

        text = doc.text or ""
        print("内容预览:")
        print(text[:1000])


if __name__ == "__main__":
    main()
