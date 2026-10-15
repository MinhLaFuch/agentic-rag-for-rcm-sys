# Ablation Comparison Protocol

Tài liệu hướng dẫn sử dụng công cụ so sánh thí nghiệm ablation cho hệ gợi ý sản phẩm LLM agent.

## Tổng quan

Công cụ này so sánh kết quả giữa hai (hoặc nhiều) cấu hình agent để đánh giá tác động của các thay đổi framework (ví dụ: plan-reflect, Memory, Inference mode). Đây là **base template** - framework còn thay đổi, nên công cụ được thiết kế chung, không gắn cứng vào ablation cụ thể nào.

## Cách khai báo nhóm và contrast

### File cấu hình

Mọi cấu hình nằm trong `configs/agent/ablation.yaml`. Ví dụ:

```yaml
ablation:
  bootstrap_resamples: 10000
  confidence: 0.95
  min_n_warn: 20
  seed: 42
  metrics:
    - task_success
    - recall@{k}
    - ndcg@{k}
    - constraint_satisfaction
    - first_attempt_ok
    - reflections
    - llm_latency_seconds
    - completion_tokens

  groups:
    # Nhóm A: cấu hình baseline (reflect_rounds=0)
    config_no_reflect: [exp_001, exp_002]

    # Nhóm B: cấu hình với reflect_rounds=1
    config_with_reflect: [exp_003, exp_004]

  contrasts:
    # So planner với và không reflect
    - name: reflect_effect
      a: [planner, config_no_reflect]
      b: [planner, config_with_reflect]

    # So type1 và planner trên cùng lần chạy
    - name: agents_comparison
      a: [type1, config_no_reflect]
      b: [planner, config_no_reflect]
      kinds: [similar]  # chỉ so kind "similar"
```

### Nhóm (Groups)

Một **group** là một nhãn + danh sách các thư mục `exp_NNN` chứa các lần chạy của cùng cấu hình.

- Nếu group có 1 exp: chỉ có 1 lần chạy
- Nếu group có nhiều exp: nhiều lần lặp cho cùng cấu hình (để tính phương sai)

Thư mục exp là tương đối `experiments_dir/agent_eval/` (ví dụ: `exp_001` → `experiments/agent_eval/exp_001/`).

### Contrast

Một **contrast** là một so sánh giữa:
- `a`: `[agent, group]` - agent và group A
- `b`: `[agent, group]` - agent và group B
- `kinds` (tuỳ chọn): chỉ so các kind được liệt kê, bỏ qua thì so tất cả

**Ví dụ so sánh hai agent trong cùng một lần chạy:**
```yaml
- name: same_run_comparison
  a: [type1, config_a]
  b: [planner, config_a]
```

**Ví dụ so sánh cùng agent giữa hai cấu hình khác nhau:**
```yaml
- name: reflect_effect
  a: [planner, config_no_reflect]
  b: [planner, config_with_reflect]
```

## Cách đọc từng con số

### Kết quả trong report.md

#### Header
```
# Ablation Comparison: reflect_effect

**Agent A:** planner (group: config_no_reflect)
**Agent B:** planner (group: config_with_reflect)
**Bootstrap resamples:** 10000
**Confidence level:** 95%
**k:** 10

**Number of paired requests:** 40
```

- `Number of paired requests`: số cặp request có kết quả cho cả A và B
- Nếu n < `min_n_warn` (mặc định 20), sẽ có cảnh báo ⚠️

#### Bảng metric

```
| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.8000 | 0.9000 | +0.1000 | [0.0500, 0.1500] | 40 |
```

- `Mean A`: trung bình metric của agent A
- `Mean B`: trung bình metric của agent B
- `Diff (B-A)`: hiệu B trừ A (dương = B tốt hơn A)
- `95% CI`: khoảng tin cậy bootstrap 95% cho hiệu (nếu không chứa 0 → có ý nghĩa thống kê)
- `n`: số cặp request được dùng để tính

#### McNemar test (cho metric nhị phân)

```
|  | McNemar: b=8, c=2, p=0.032 | | | | |
```

- `b`: số cặp A đúng B sai
- `c`: số cặp A sai B đúng
- `p`: p-value (nhỏ < 0.05 → khác biệt có ý nghĩa)

**Lưu ý:** McNemar chỉ hiển thị khi có đủ cặp không nhất quán (b + c ≥ 10).

#### Variance info

```
**Variance:**
- Group A runs: 2
- Group B runs: 2
```

Nếu chỉ có 1 lần chạy:
```
**Variance:** Only 1 run per group, cannot compute variance
```

### File CSV

`comparison.csv` có các cột:
- `contrast`: tên contrast
- `agent_a`, `agent_b`: tên agent
- `group_a`, `group_b`: tên group
- `kind`: kind của request
- `segment`: segment của request (hoặc "all" nếu gộp)
- `metric`: tên metric
- `mean_a`, `mean_b`: trung bình
- `diff`: hiệu B - A
- `ci_lower`, `ci_upper`: khoảng tin cậy
- `n`: số cặp
- `is_oracle`: true nếu kind là ORACLE (constrained, cold_text)

Dùng file này để vẽ biểu đồ (ví dụ: plot diff vs kind).

### File JSON

`comparison.json` chứa đầy đủ kết quả (kể cả chi tiết từng kind × segment) để phân tích thêm.

### File disagreements.jsonl

Mỗi dòng là một request mà hai agent khác nhau về `task_success`:
```json
{
  "request_id": "similar-sparse-0",
  "text": "Tôi là user...",
  "kind": "similar",
  "segment": "sparse",
  "a_trajectory": {
    "plan": [...],
    "steps": [...],
    "reflections": 0
  },
  "b_trajectory": {
    "plan": [...],
    "steps": [...],
    "reflections": 1
  }
}
```

Dùng file này để phân tích chi tiết tại sao agent thất bại/thành công.

## Các lỗi suy luận cần tránh

### 1. ORACLE là cận trên, không phải query thật

Kinds `constrained` và `cold_text` lấy ràng buộc (category, price) từ held-out items. Đây là **cận trên (upper bound)** - không đại diện cho query thật trong production.

- **Không so sánh ORACLE với kinds khác** (similar, personalized) như thể chúng cùng loại.
- Khi báo cáo, phải ghi rõ ORACLE là kịch bản lý tưởng.

### 2. n nhỏ → kết quả không đáng tin cậy

Nếu `n < min_n_warn` (mặc định 20), khoảng tin cậy sẽ rất rộng. Không nên kết luận gì từ kết quả này.

- Hãy chạy với `per_segment` lớn hơn (ví dụ: 20 → 50).
- Hoặc chạy nhiều lần lặp và gộp kết quả.

### 3. Nhiễu LLM: kết quả không tái lập hoàn toàn

LLM có độ ngẫu nhiên nội tại → cùng cấu hình, cùng request có thể trả kết quả khác nhau giữa các lần chạy.

- **Không so sánh hai lần chạy khác nhau** trừ khi bạn đã trung bình qua nhiều lần lặp.
- Khi báo cáo, ghi rõ kết quả LLM có nhiễu.
- Sử dụng bootstrap CI để biểu diễn uncertainty.

### 4. So sánh khi hai cấu hình khác tập request

Hai cấu hình chỉ nên so sánh khi:
- `seed` giống nhau (tập request giống nhau)
- `per_segment` giống nhau
- `eval_on` giống nhau (validation/test)
- `language` giống nhau
- `k` giống nhau

Nếu không khớp, công cụ sẽ từ chối và in lý do:
```
ERROR: seed mismatch: 42 vs 43
```

**Không ép buộc so sánh** khi điều kiện không thỏa - kết quả không có ý nghĩa.

### 5. McNemar test khi b + c quá nhỏ

McNemar test chỉ chính xác khi có đủ cặp không nhất quán (b + c ≥ 10). Nếu quá ít, công cụ sẽ không hiển thị p-value.

- Không suy luận từ McNemar khi b + c < 10.
- Hãy tăng n để có nhiều cặp không nhất quán hơn.

## Lệnh PowerShell chính xác

### Chạy so sánh với config mặc định

```powershell
$env:PYTHONPATH="."
python scripts/compare_experiments.py
```

### Chạy với config file khác

```powershell
$env:PYTHONPATH="."
python scripts/compare_experiments.py --config agent/ablation_custom
```

### Kết quả đầu ra

Kết quả được lưu trong `experiments/agent_eval/ablation/<contrast_name>/`:
- `report.md` - báo cáo markdown (dán thẳng vào báo cáo)
- `comparison.json` - kết quả đầy đủ JSON
- `comparison.csv` - dữ liệu để vẽ biểu đồ
- `disagreements.jsonl` - request khác nhau để phân tích

## Lưu ý quan trọng

### Kết quả LLM không tái lập hoàn toàn

Kết quả thật chưa được đo - mọi số liệu trong ví dụ là giả định.

Khi bạn chạy thật trên máy:
- Ghi rõ số lần lặp và khoảng tin cậy.
- Ghi rõ LLM model và API endpoint.
- Nếu thấy kết quả bất thường, hãy chạy nhiều lần lặp để kiểm tra.

### Không so sánh ngược chiều

Công cụ luôn tính `Diff = B - A`. Nếu bạn muốn hiển thị `A - B`, hãy đổi thứ tự trong config.

### Không kết luận thay người

Báo cáo chỉ có số, khoảng tin cậy, cảnh báo. Không có câu "A tốt hơn B" hay "khác biệt có ý nghĩa" - đó là suy luận của bạn.

## Framework còn thay đổi

Công cụ này là base template. Khi framework ổn định:
- Định nghĩa ablation cụ thể bằng thêm groups/contrasts vào YAML.
- Không cần sửa code.
- Khi tầng Inference thêm cột `answer_*`, công cụ sẽ tự bỏ qua các cột chưa có.
- Khi cần phân tích riêng cho reflect/Memory, chỉ cần thêm contrast mới.
