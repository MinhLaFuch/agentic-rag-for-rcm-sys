# Kế hoạch xử lý bottleneck retrieval embedding và ranking

Cập nhật: 2026-11-22 (v2). Trạng thái: Đã hoàn tất toàn bộ chuỗi P0 -> P3 và vòng nâng cấp hiệu năng/chất lượng Retrieval + Reranking + Tiếng Việt (SparseBM25Index, persisted HNSW SQ8, DomainCategoryPopularity 5-source RRF, MultiSignalReranker HistGBDT, VietnameseQueryTranslator + Track B tiếng Việt). **Gate 3 PASS trên cả 3.000 user validation lẫn 3.000 user held-out test** (`retrieval_total` p95 `0.359–0.488s <= 0.50s`, cả 3 segment `cold/sparse/warm` đều tăng dương rõ rệt), và `fused + ltr_reranker` dẫn đầu toàn diện trên `exp_012` (+112% NDCG@10 so với `bm25 + baseline`, +52% so với `fused + hybrid_w4`). Xem chi tiết tại `src/docs/final_bottleneck_report.md`.

### Kết quả P0 đã xác nhận

- Test local: `src/experiments/test_logs/test_results_20261116_182444.md`, 101 passed.
- Report: `src/experiments/readiness/p0_profile_20261116_182515.json`.
- `ready_for_evaluation=true`, không còn blocker trong report; 45 lượt kiểm tra artifact và 27 lượt kiểm tra config evidence đều MATCH.
- Protocol runtime và bundle cùng `temporal_train_core`; config lịch sử đã xác minh bằng snapshot. Config drift hiện tại vẫn được lưu riêng, không bị che hoặc sửa hash.
- Scan train/validation/test hợp lệ theo thời gian và cutoff; 0 event trùng xuyên split. Corpus có 2.637.776 item, coverage và first_seen coverage 100%.
- Kết luận chỉ áp dụng cho bundle `multi_domain_v2_audit_20261030` khi bật đúng audit profile/overlay. Không cần dựng lại data. Bước kế tiếp là chuẩn bị benchmark contract và pilot embedding; chưa chạy full embedding hoặc kết luận retrieval bottleneck đã được giải quyết.

## 1. Mục tiêu và tiêu chí đóng vấn đề

Xác định, đo và xử lý nguyên nhân khiến recommendation không tìm được hoặc không xếp đúng item phù hợp. Tạo được embedding, test pass hoặc metric khác 0 chưa phải bằng chứng bottleneck đã được giải quyết.

Kết quả cần đạt:

1. Data, mapping, corpus và protocol được kiểm chứng, tái lập được.
2. So sánh BM25, dense và hybrid trên cùng query/cohort/budget.
3. Phân biệt thiếu tín hiệu, thiếu metadata, retrieval miss và ranking miss.
4. Cấu hình thắng trên validation thực sự chạy trong evaluator và agent/demo.
5. Đạt ngưỡng chất lượng, latency và tài nguyên đã chốt; có fallback và đánh giá cuối trên test.

Nếu chưa đạt một tiêu chí, ghi rõ bottleneck còn lại và giữ trạng thái chưa giải quyết. Không cam kết embedding tự giải quyết mọi dạng cold-start.

## 2. Hiện trạng đã xác nhận

| Thành phần | Hiện trạng | Hệ quả |
|---|---|---|
| Bundle mặc định | `path/domains.merged_name = multi_domain` | Lệnh mặc định chọn bundle legacy |
| Corpus mặc định | `src/resource/corpus/corpus_multi_domain.sqlite`, format/logic v1, thiếu provenance first_seen | Chưa đủ điều kiện benchmark historical |
| Manifest mặc định | Có stage 1, thiếu stage 2/3/4 | Chuỗi không đầy đủ, không phải legacy hợp lệ |
| Raw/cleaned | Output người dùng cho thấy các file được liệt kê MATCH | Chưa có bằng chứng cần chạy lại cleaning |
| Config drift | `data/split.yaml`, `path/domains.yaml` khác hash lịch sử | Kiểm tra tương thích config; không sửa hash để làm MATCH |
| Bundle ứng viên | `multi_domain_v2_audit_20261030` còn manifest stage 2/3/4, corpus v2; stage 3 ghi `temporal_train_core` | Ưu tiên xác minh/tái sử dụng; chưa tuyên bố toàn bộ artifact MATCH |
| Catalog audit | Stage 3 ghi 2.637.776 mapped items | Đo số item thực trong corpus, không cố định 678.281 |
| Embedding mặc định đã kiểm tra | Hash encoder 128 chiều, sidecar cũ thiếu provenance | Chỉ thử luồng; cần artifact semantic mới |
| Candidate evaluator | Có BM25/hybrid, union đối chứng riêng, kiểm chứng embedding | Còn thiếu dense-only, pool replay, CI và chẩn đoán đầy đủ |
| Ranking evaluator | Vẫn tạo SearchTool thuần BM25 | Chưa tự nhận embedding từ candidate evaluator |
| VectorStore | Exact dot-product rồi tạo/sort toàn danh sách bằng Python mỗi query | Cần đo và tối ưu trước benchmark lớn |

## 3. Quy tắc đánh giá

- Protocol chính: `historical_static_catalog`. `first_seen_ts` là proxy từ cleaned interactions, không phải launch date và không chứng minh toàn bộ metadata causal.
- `no_filter` chỉ dùng diagnostic legacy được ghi nhãn riêng, không thay thế benchmark historical.
- Cho phép thiếu source chỉ áp dụng cho file source không tồn tại; schema, mapping, item count, source hiện có và checksum vẫn phải hợp lệ.
- Manifest thiếu một phần, sai tag hoặc checksum phải dừng. Không tạo lại manifest để hợp thức hóa artifact chưa xác minh.
- Khóa seed, user/query IDs, query text, cutoff, budget, mapping, metadata policy và normalization khi so sánh.
- Chọn model, fusion và scorer bằng validation; khóa cấu hình trước test. Nếu test đã dùng để tuning trong quá khứ, ghi rõ mức độc lập còn lại.

## 4. Giai đoạn 1 — Chốt bundle và protocol dữ liệu

- [ ] Kiểm tra checksum các output stage 2/3/4 trong bundle audit; lưu report file thiếu/sai.
- [ ] Đối chiếu source/upstream manifests, mapping hash, corpus checksum/schema, first_seen coverage và metadata coverage theo domain.
- [ ] Đọc config snapshot/flags lúc tạo bundle; xác định semantics thực tế của temporal_train_core và fit-core mapping.
- [x] Bổ sung `--tag` và bộ chọn bundle dùng chung cho verify/build/candidate/ranking; giữ nguyên mặc định và kiểm chứng. Đã viết test nhưng chưa chạy local trong bước này.
- [ ] Đồng bộ lựa chọn bundle đã chốt vào cấu hình runtime/agent/demo; API `get_data_paths(tag=...)` hiện đã có.
- [ ] Xử lý config drift: giữ chứng cứ lịch sử; dùng config lịch sử trong môi trường cô lập hoặc kiểm chứng snapshot có hash gốc và kiểm tra tương thích runtime riêng. Overlay không sửa được byte hash file config hiện tại.
- [x] Chuẩn bị snapshot 7 config khớp hash manifest và profile/overlay runtime riêng. Verifier chỉ dùng snapshot cho config evidence; các artifact vẫn kiểm tra file thật. Xem `src/docs/audit_evaluation_profile.md`. Chưa đánh dấu hoàn tất config gate trước khi test và audit profile trên local pass.
- [ ] Xác minh fit/target đúng protocol; không lẫn full catalog mapping với fit-core mapping khi dùng ItemKNN/cache.
- [ ] Kiểm tra `max(train.timestamp) < min(validation.timestamp)` và `max(validation.timestamp) < min(test.timestamp)`; ghi inclusive/exclusive cutoff.
- [ ] Kiểm tra event trùng xuyên split bằng khóa có domain/namespaced item ID. User/item lặp lại giữa các split không tự động là leakage.
- [ ] Dùng batch/disk khi kiểm tra dữ liệu lớn; tránh nhiều Python set hàng chục triệu dòng cùng lúc.
- [ ] Xuất readiness report: tag, protocol, counts, cutoff, hashes, coverage và quyết định reuse/rebuild có lý do.

Công cụ P0 đã chuẩn bị: `src/scripts/data_pipeline/audit_bundle.py`; xem `src/docs/embedding_p0_readiness.md` để chạy test, audit checksum rồi scan split trên local. Chưa xác nhận Gate 1 đạt trước khi có kết quả chạy.

**Gate 1:** artifact/provenance hợp lệ và runtime chọn đúng bundle/protocol. Nếu chỉ stage 4 không tương thích, dựng lại stage 4 vào artifact mới có nguồn gốc rõ ràng. Chỉ chạy lại stage 1/2/3 khi có bằng chứng đầu vào hoặc semantics sai. Không ghi đè bộ audit cũ.

## 5. Giai đoạn 2 — Benchmark contract và embedding thực

### Full catalog đã build và kiểm chứng ngày 2026-11-17

Artifact: `src/experiments/embedding_builds/minilm_v2_audit_cpu/artifact`. Manifest complete/full-catalog; checkpoint published, 644 chunk, đủ 2.637.776 item × 384 chiều float32. Build ID `06ffb18aef332c384056df5d8885da436bd210b0f8e0a2886f0f7b74a79b507a`.

Đã kiểm chứng lại checksum vectors/ID/corpus/mapping và corpus sidecar; scan toàn bộ vector finite/normalized (norm 0,999999821–1,000000238), ID unique/sorted và khớp từng dòng toàn catalog. Theo domain: Electronics 1.609.860, Toys_and_Games 890.667, Video_Games 137.249. Encode time ghi nhận khoảng 7,04 giờ, throughput trung bình 104,06 item/s; đây không phải tổng wall time. Kiểm tra này không chạy lại model/query encoder probe và không đo Recall.

Full embedding artifact đã hoàn thành; bước tiếp theo là smoke retrieval với artifact này và hoàn thiện correctness/filter/performance, dense-only ablation, cohort/query artifacts trước benchmark lớn. Retrieval bottleneck chưa được kết luận giải quyết.

### Full builder đã chuẩn bị

Script `src/scripts/data_pipeline/build_full_item_embeddings.py` đã có chunk/keyset reading, checksum checkpoint, OS lock, resume fingerprint/probe, staging mmap và atomic directory publish. Pilot/full dùng chung text formatter v2. Loader hỗ trợ directory artifact bằng mmap; candidate CLI thêm `--embeddings-path`. Đã viết test ngắt/chạy tiếp, orphan chunk, corruption, publish failure và loader; chưa chạy local trong lượt triển khai. Xem `src/docs/full_embedding_build.md` để chạy test rồi build. Chưa đánh dấu full catalog hoàn thành trước khi có report/publication thực tế.

### Kết quả pilot 10.000 item đã xác nhận

Report local: `src/experiments/embedding_pilot/pilot_10k_20261116_190552/report.json`, status `completed`. Cùng MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, CPU, batch 64, max length 256, contract/profile và corpus như pilot 1.000 item.

- Mẫu: Electronics 3.334, Toys_and_Games 3.333, Video_Games 3.333; thiếu metadata signal 0.
- Hai lượt encode 90,68 và 89,47 item/s; median 90,07 item/s, thấp hơn khoảng 49% so với pilot 1.000 item. Chưa xác định nguyên nhân; không quy ngay cho CPU throttling hoặc thuật toán.
- Peak RSS 0,918 GiB, gần như không đổi so với pilot nhỏ. Đây là đo process pilot, không phải bảo đảm RAM cho full builder hiện tại.
- Token p50/p95 = 53/86; 3/10.000 text vượt 256 token (0,03%), max 448. Giữ max length 256 làm baseline tài nguyên hiện tại và báo truncation; chưa có bằng chứng chất lượng để thay đổi.
- Tổng wall khoảng 298 giây; encode hai lượt khoảng 222 giây. Ngoại suy encode-only toàn catalog cập nhật khoảng 8 giờ 8 phút, chưa tính extraction/save/index. Vector float32 toàn catalog vẫn khoảng 3,77 GiB.
- Đủ bằng chứng pilot để thiết kế full build CPU theo chunk, có resume và cùng text protocol v2. Chưa chạy full builder; chưa đo Recall và chưa đóng retrieval bottleneck.

### Kết quả pilot 1.000 item đã xác nhận

Report local: `src/experiments/embedding_pilot/pilot_20261116_185643/report.json`, status `completed`.

- MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 chiều, CPU, batch 64, max length 256.
- Mẫu cân bằng domain: Electronics 334, Toys_and_Games 333, Video_Games 333; thiếu metadata signal 0, text vượt max length 0 trong mẫu.
- Hai lượt encode: 181,47 và 171,62 item/s; median 176,54 item/s; peak RSS 0,917 GiB.
- Ngoại suy encode-only toàn catalog khoảng 4 giờ 9 phút; vector float32 khoảng 3,77 GiB. Chưa bao gồm full extraction/save/index hoặc chi phí RAM của full builder.
- PyTorch CLI preflight pass. Chưa đo candidate recall và chưa kết luận bottleneck retrieval đã được giải quyết.
- Bước tiếp theo: pilot 10.000 item cùng revision để kiểm tra scaling; chuẩn bị streaming/chunk/resume và text protocol v2 trước full build. Không dùng builder full hiện tại làm bước chạy tiếp tự động.

Đã chuẩn bị contract ban đầu tại `src/configs/eval/embedding_benchmark_contract.yaml`, script pilot `src/scripts/data_pipeline/pilot_item_embeddings.py`, test synthetic và hướng dẫn `src/docs/embedding_pilot.md`. Chưa chạy test/pilot local trong lượt chuẩn bị. Contract vẫn cần cohort/query artifact và cold-query dataset; pilot chỉ đo tài nguyên, không chứng minh chất lượng retrieval.

### Hai track đầu vào

**Track A — history proxy:** query chỉ từ fit history trước cutoff; lưu seed items, text và normalization. Đánh giá sparse/warm; cold không có history ghi `no_input`. Báo tỷ lệ có query và metric toàn cohort, không âm thầm loại user thiếu query. Tính lại cold/sparse/warm theo fit history; không dùng tỷ lệ 72,21% user có một event toàn dataset làm tỷ lệ cold evaluation.

**Track B — cold có truy vấn:** chuẩn bị truy vấn thực hoặc tình huống có query và relevance judgments tạo độc lập với held-out target. Chia development/validation/test; lưu source, ngôn ngữ, domain, constraints và nhãn. Query/nhãn tổng hợp phải ghi rõ và kiểm tra chất lượng. Nếu dịch query sang tiếng Anh, khóa bản dịch và phương pháp/model dịch cho các retriever dùng cùng input.

`category_oracle` chỉ là upper bound diagnostic. Cold không có cả history lẫn query cần popularity/domain fallback hoặc hỏi thêm nhu cầu; dense không tự tạo thông tin sở thích.

### Model, tài nguyên và artifact

- [ ] Dùng `sentence-transformers/all-MiniLM-L6-v2` làm semantic baseline đầu tiên, chưa khẳng định là model tốt nhất.
- [ ] Kiểm tra dependency môi trường encode/evaluation. Có thể dùng `.venv-semantic` sau khi bổ sung dependency dự án; không cài đè tùy tiện môi trường baseline.
- [ ] Pilot 1.000–10.000 item: đo thời gian, peak RAM, truncation và text rỗng. Không lấy tốc độ ước lượng làm ETA thực tế.
- [ ] Khóa text template, thứ tự categories, normalization, max sequence length và revision bất biến model/tokenizer; chọn trường tĩnh phù hợp metadata policy.
- [ ] Bổ sung batch/chunk, checkpoint/resume identity và publish atomically khi cần. Builder hiện giữ texts/batches trong RAM, chưa có resume; xác nhận tài nguyên trước full build.
- [ ] Sinh artifact mới, không ghi đè hash artifact diagnostic; evaluator chọn đường dẫn artifact tường minh.
- [ ] Sidecar ghi model thực, revision, dimension/count, text protocol, library versions, encoder probe, corpus/mapping/item-ID hashes và artifact checksum. Builder đã có một phần, bổ sung phần còn thiếu.
- [ ] Kiểm tra unique/aligned IDs, shape, finite/nonzero vectors, norm và encoder compatibility trước publish/load.
- [ ] Báo coverage toàn catalog, theo domain và target cohorts; không chỉ encode fit-core rồi gọi là toàn catalog.

**Gate 2:** benchmark có input/ground truth rõ ràng; embedding hợp lệ, tái lập và đủ tài nguyên. Dim=384 hoặc file tạo thành công chưa chứng minh chất lượng.

## 6. Giai đoạn 3 — Candidate retrieval

Đã chuẩn bị matrix opt-in trong `candidate_recall.py`, config `src/configs/eval/retrieval_matrix.yaml`, query builder dùng chung runtime/eval, deterministic quota RRF, dense exact có eligible/seen filtering trước Top-K, frozen candidate replay bằng RankTool và scorer evidence theo CF ties/additive ablation. Xem `src/docs/retrieval_matrix.md`. Chưa chạy test/benchmark trong lượt triển khai; chưa đánh dấu gates đạt. Legacy semantic evaluator và mặc định runtime giữ nguyên.

### Hoàn thiện evaluator và search

- [ ] Thêm dense-only source để tách lợi ích encoder khỏi fusion; so popularity, ItemCF, BM25 (`semantic` là tên legacy), dense và hybrid.
- [ ] Giữ `union_rr` = popularity + ItemCF + BM25; `union_hybrid_rr` = popularity + ItemCF + hybrid, cùng tổng budget N.
- [ ] `union_all`/`union_hybrid_all` tối đa 3N, báo kích thước thực; không quy tăng recall do tăng pool thành thắng ở budget N.
- [ ] Xuất pool theo query/user: ID, rank, score, source, seen exclusion, filters, hits, lỗi/timeout/no_input và latency. Raw artifact lớn lưu local; commit summary/checksum.
- [ ] Freeze sampled IDs/query artifact để so sánh ghép cặp; tách load/build/warm-up khỏi latency, ghi hardware/cache mode/peak RAM.
- [ ] Báo tool/encoder errors riêng, không biến lỗi thành zero recall rồi kết luận model kém.
- [ ] Dense tuân thủ cutoff/domain/price/category/exclusion và metadata policy như BM25.
- [ ] Tránh chỉ lấy global top-2N rồi lọc khiến item không hợp lệ che mất hàng xóm hợp lệ. Search trên eligible set hoặc refill có kiểm chứng.
- [ ] Loại seen trước chốt budget, refill khi cần; báo realized size khi không đủ N.
- [ ] Exact search làm reference trên tập nhỏ; tối ưu partial Top-K/vectorized selection với tie-break ổn định.
- [ ] Chỉ thử ANN khi exact chưa đạt latency/RAM; báo ANN recall so với exact và kiểm tra filters.

### Thực nghiệm và quyết định

1. Smoke 10 user/segment và tập query nhỏ; xác nhận nguồn thực sự chạy.
2. Pilot 100 user/segment; đo errors, query coverage và tài nguyên.
3. Validation bắt đầu 1.000 user/segment; mở rộng theo độ bất định/chi phí, không mặc định 1.000 là đủ.
4. Budget 50/100/200; báo macro/micro Recall, Hit, catalog/domain coverage, realized size, p50/p95 latency, throughput và RAM.
5. Phân tích cold/sparse/warm; target catalog-warm/catalog-cold; trong/ngoài fit-core; metadata có/thiếu; domain và popularity.
6. Paired bootstrap 95% CI theo user cho history, theo đơn vị query độc lập phù hợp cho cold-query; lưu seed/phương pháp.
7. Phân tích failure cases trước khi thử model/text template/RRF khác; giới hạn tuning budget và lưu cả run không cải thiện.

**Gate 3:** sau pilot, khóa tiêu chí trước validation lớn: Recall@100 trên track/cohort mục tiêu, mức tăng tối thiểu có ý nghĩa, ngưỡng không suy giảm cohort quan trọng, p95 latency/RAM trên máy mục tiêu. Báo CI delta, errors và coverage. Chưa gán ngưỡng tùy ý khi chưa đo baseline. Hai track có kết luận riêng. Nếu hybrid không đạt, giữ BM25/fallback và xử lý nguyên nhân cụ thể.

## 7. Giai đoạn 4 — Ranking, runtime và đánh giá cuối

### Tích hợp còn thiếu

- [ ] Nối vector store/query encoder/provenance vào `ranking_eval.py` và config schema; ranking hiện vẫn BM25.
- [ ] Định nghĩa candidate artifact chung và compatibility check để ranking replay đúng pool từ candidate evaluation.
- [ ] `--candidates-from` hiện nhận completed ranking experiment, chưa mặc định đọc output candidate_recall.
- [ ] Fingerprints source/model/corpus/mapping/query/pool nằm trong checkpoint identity; đổi chúng phải từ chối resume.
- [ ] Nối cấu hình thắng vào toolkit/demo/agent; log chứng minh source thực tế chạy.
- [ ] Test hồi quy filters, seen exclusion, temporal validity, provenance, resume và hybrid runtime.

### Ablation xác định bottleneck

| Candidate pool | Scorer | Câu hỏi |
|---|---|---|
| BM25 union | Scorer cố định | Baseline end-to-end |
| Hybrid union, cùng budget | Cùng scorer cố định | Retrieval có cải thiện kết quả cuối? |
| Pool cố định được lưu | Các scorer/reranker | Scorer nào giữ/xếp item đúng tốt hơn? |
| Pool thắng đã khóa | Agent bật/tắt | Agent đóng góp gì ngoài retrieval/ranking? |

Báo Recall/NDCG/MRR/Hit tại K=5/10/20, coverage, latency và chi phí LLM nếu có. Phân rã miss: thiếu input → target ngoài catalog/eligible set → retrieval miss → có trong pool nhưng rớt Top-K. Candidate oracle ceiling và tỷ lệ giữ hit sau rerank chỉ là diagnostic, không phải hệ thống triển khai. Không vừa đổi scorer vừa đổi retriever rồi quy toàn bộ tăng trưởng cho embedding.

### Đóng băng và runtime

- [ ] Decision record trên validation ghi quality/latency/coverage trade-off và hạn chế.
- [ ] Freeze config, model revision, artifact, source fingerprint và environment trước test cuối.
- [ ] Test chỉ dùng history train + validation, không fit/query bằng tương tác test. Ghi artifact nào dựng lại theo fit split và encoder/text nào giữ cố định.
- [ ] Smoke runtime: query hợp lệ, không history, không query, thiếu metadata, filter chặt, artifact lỗi và encoder unavailable.
- [ ] Fallback runtime có policy/log rõ. Benchmark hybrid phải dừng nếu hybrid không chạy, không báo BM25 dưới nhãn hybrid.
- [ ] Lưu final report và run manifest/lệnh tái lập.

**Gate 4:** cấu hình được kiểm chứng thực sự chạy end-to-end, đạt gates trên phạm vi đã xác định, test không tham gia tuning và có fallback. Chỉ đóng vấn đề khi đủ bằng chứng; nêu rõ cohort chưa giải quyết.

## 8. Lệnh hiện có và điều kiện sử dụng

Build/eval chỉ chạy sau Gate 1 và kiểm tra môi trường. Không chạy full với mặc định multi_domain hiện tại.

```powershell
Set-Location "D:\DACNTT\src\agentic-rag-for-rcm-sys"
$env:PYTHONPATH = "src"

# Readiness mặc định hiện tại: dự kiến MISMATCH.
.\src\.venv-baseline\Scripts\python.exe -u src/scripts/data_pipeline/verify_tag.py

# Kiểm tra CLI; chưa build/eval.
.\src\.venv-baseline\Scripts\python.exe src/scripts/data_pipeline/build_item_embeddings.py --help
.\src\.venv-baseline\Scripts\python.exe src/scripts/evaluation/candidate_recall.py --help
.\src\.venv-baseline\Scripts\python.exe src/scripts/evaluation/ranking_eval.py --help
```

Sau khi chọn đúng bundle và Python có sentence-transformers cùng dependency dự án:

```powershell
python -u src/scripts/data_pipeline/build_item_embeddings.py `
    --provider sentence_transformers `
    --model sentence-transformers/all-MiniLM-L6-v2 `
    --batch-size 256

# Smoke: run hybrid hiện đã tính cả BM25 và union đối chứng.
python -u src/scripts/evaluation/candidate_recall.py `
    --eval-on validation --retrieval hybrid `
    --metadata-policy historical_static_catalog `
    --query-mode history --per-segment 10
```

Dừng khi command lỗi; không thêm cờ bỏ kiểm chứng. Lệnh full build, cold-query evaluation và ranking hybrid được chốt sau tích hợp tương ứng. `ranking_eval.py` hiện không nhận `--metadata-policy`, `--allow-missing-corpus-sources`, `--per-segment`; các giá trị này nằm trong config/overlay.

## 9. Thứ tự triển khai

| Ưu tiên | Deliverable | Điều kiện hoàn thành |
|---|---|---|
| P0 | Data readiness + chọn bundle | Đúng artifact/protocol; provenance hợp lệ; không bypass |
| P1 | Benchmark contract + cold-query dataset | Hai track có input/nhãn và cohorts đóng băng |
| P1 | Embedding + search correctness/performance | Artifact tái lập; search/filter đúng; có pilot tài nguyên |
| P2 | Retrieval benchmark + failure analysis | Paired comparison/CI, gates và quyết định validation |
| P2 | Ranking replay + scorer ablation | Cùng pool khi so scorer; cùng scorer khi so retriever |
| P3 | Runtime integration + test cuối | Cấu hình thực sự chạy trong agent/demo; test không dùng tuning |
| P3 | Final bottleneck report | Vấn đề đã giải quyết, cohort còn yếu và hành động còn lại |
