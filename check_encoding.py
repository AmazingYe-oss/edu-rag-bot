from pathlib import Path
from charset_normalizer import from_path

data_dir = Path("data")

for file_path in data_dir.rglob("*"):
    if file_path.is_file():
        result = from_path(file_path).best()
        if result:
            print(file_path, "=>", result.encoding, "confidence:", result.percent_coherence)
        else:
            print(file_path, "=> 无法识别")
