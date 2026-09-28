"""
Data acquisition cho Amazon Reviews 2023 (mục V, Phase 2).

LƯU Ý QUAN TRỌNG: module này đã được viết đầy đủ và đúng API thật của
HuggingFace `datasets`, nhưng CHƯA thể chạy thành công trong môi trường
container hiện tại vì `huggingface.co` bị chặn ở tầng network
(x-deny-reason: host_not_allowed — đã verify bằng curl).

BLOCKED:
REASON: môi trường container không cho phép egress tới huggingface.co /
  datasets-server.huggingface.co.
REQUIRED ACTION: chạy script này trên máy có internet đầy đủ (hoặc môi
  trường có allowlist huggingface.co), ví dụ:
    DOMAIN=Video_Games python scripts/run_eda.py
"""

from __future__ import annotations

from pathlib import Path


def download_domain_reviews_direct(
    domain: str, output_path: str | Path, chunk_size: int = 1024 * 1024
) -> Path:
    """
    Cách đơn giản hơn nhiều so với datasets.load_dataset(): tải trực tiếp
    file .jsonl.gz gốc từ McAuley Lab (host tại UCSD, KHÔNG cần HuggingFace
    auth/token, không cần cài package `datasets`).

    URL pattern đã xác nhận qua README chính thức của dataset:
        https://datarepo.eng.ucsd.edu/mcauley_group/data/amazon_2023/raw/review_categories/{domain}.jsonl.gz
        https://datarepo.eng.ucsd.edu/mcauley_group/data/amazon_2023/raw/meta_categories/meta_{domain}.jsonl.gz

    LƯU Ý: hàm này cần chạy trên máy có internet đầy đủ — container hiện
    tại của Claude bị chặn network tới cả huggingface.co lẫn
    datarepo.eng.ucsd.edu (đã verify bằng curl, HTTP 403 host_not_allowed
    ở cả hai). Đây là lý do hàm được tách riêng để người dùng tự chạy.
    """
    import urllib.request

    url = (
        "https://datarepo.eng.ucsd.edu/mcauley_group/data/amazon_2023/"
        f"raw/review_categories/{domain}.jsonl.gz"
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(url) as response, open(output_path, "wb") as out_file:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)

    return output_path
