import requests
import json

url = "http://127.0.0.1:8000/api/chat"
payload = {
    "question": "解释一下什么是向量数据库，并举个生活中的例子",
    "session_id": "test_user_001"
}

print("🔥 正在发送请求...\n")
print("🤖 AI 回答: ", end="", flush=True)

# stream=True 是接住流式输出的关键
response = requests.post(url, json=payload, stream=True)

final_context = ""

# 迭代接收大模型吐出的每一个数据块
for line in response.iter_lines():
    if line:
        decoded_line = line.decode('utf-8')
        if decoded_line.startswith("data: "):
            # 解析 SSE 的 data 内容
            data_json = json.loads(decoded_line[6:])
            
            # 拿到每次吐出的字，并立刻打印到屏幕上
            delta = data_json.get("delta", "")
            print(delta, end="", flush=True)
            
            # 记录最后返回的参考上下文
            if "context" in data_json:
                final_context = data_json["context"]

print("\n\n" + "="*50)
if final_context:
    print(final_context)
