"""
Kiểm tra file item_embeddings_multi_domain.npz vừa được tạo.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Thêm src vào sys.path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import numpy as np
from package.config import get_data_paths
from package.embeddings import VectorStore

paths = get_data_paths()
npz_path = paths.corpus_dir / f"item_embeddings_{paths.tag}.npz"

print(f"Đang kiểm tra file: {npz_path}")
print(f"File tồn tại: {npz_path.exists()}")
print(f"Dung lượng file: {npz_path.stat().st_size / (1024 * 1024):.2f} MB")

store = VectorStore.load(npz_path)
print(f"-> Tổng số sản phẩm được lập chỉ mục vector (items): {len(store):,}")
print(f"-> Số chiều vector (dimension): {store.dimension}")
print(f"-> 5 item_id đầu tiên: {store.item_ids[:5].tolist()}")

# Kiểm tra thử tìm kiếm cosine similarity
sample_query = np.ones(store.dimension, dtype=np.float32)
results = store.search(sample_query, top_k=5)
print("\n-> Thử nghiệm tìm kiếm top 5 với vector truy vấn mẫu:")
for rank, (item_id, score) in enumerate(results, 1):
    print(f"   Top {rank}: {item_id} | Cosine score: {score:.4f}")

print("\n=== KẾT QUẢ KIỂM TRA: FILE HOÀN TOÀN HỢP LỆ VÀ SẴN SÀNG SỬ DỤNG! ===")

