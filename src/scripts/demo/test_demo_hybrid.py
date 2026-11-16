import sys
from pathlib import Path

# Đảm bảo import được module package trong thư mục src
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import numpy as np
import pandas as pd
from package.corpus import ItemCorpus
from package.embeddings import VectorStore, TextEncoder
from package.tools.retrieval.search_tool import SearchTool

print("1. Đang khởi tạo ItemCorpus mẫu...")
df = pd.DataFrame({
    'parent_asin': ['g1', 'g2', 'e1'],
    'domain': ['Video_Games', 'Video_Games', 'Electronics'],
    'title': ['Super Mario Odyssey', 'The Legend of Zelda', 'Gaming Headset Pro'],
    'store': ['Nintendo', 'Nintendo', 'Logitech'],
    'categories': [['Games'], ['Games'], ['Audio']]
})
corpus = ItemCorpus.from_dataframe(df)

print("2. Đang khởi tạo VectorStore và TextEncoder...")
ids = ['Video_Games::g1', 'Video_Games::g2', 'Electronics::e1']
# g1 và g2 là game có vector gần [1.0, 0.0], e1 là tai nghe có vector [0.0, 1.0]
vecs = np.array([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]], dtype=np.float32)
store = VectorStore(item_ids=ids, embeddings=vecs)
encoder = TextEncoder(lambda texts: [[1.0, 0.0] for _ in texts], dimension=2)

print("3. Đang thực thi SearchTool với Hybrid RRF (BM25 + Dense)...")
tool = SearchTool(corpus, vector_store=store, query_encoder=encoder, rrf_k=60)
res = tool(query='mario', limit=3)

print("\n" + "=" * 60)
print("=== KẾT QUẢ RETRIEVAL HYBRID (RRF = BM25 + Dense Vector) ===")
print("=" * 60)
print(f"Chế độ truy vấn: {res.data.get('retrieval')}")
print(f"Số ứng viên dense tìm được: {res.data.get('dense_candidates')}\n")

for i, c in enumerate(res.data['candidates'], 1):
    sources = c['retrieval_sources']
    note = "Cả BM25 và Vector đều tìm thấy!" if len(sources) > 1 else ("Chỉ Vector tìm thấy (khắc phục điểm nghẽn)!" if 'dense' in sources else "Chỉ BM25 tìm thấy")
    print(f"-> Top {i}: {c['item_id']}")
    print(f"   Tên sản phẩm: {c['title']}")
    print(f"   Điểm RRF:     {c['score']:.4f}")
    print(f"   Nguồn tìm ra: {sources}  <-- {note}\n")
print("=" * 60)

