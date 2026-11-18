# Dữ liệu và artifact riêng

Không có dataset/checkpoint/prediction learner-level trong Git. Nhận dữ liệu ASSISTments qua nguồn chính thức hoặc bản lưu được phép của nhóm, kiểm tra điều kiện sử dụng rồi đặt ở các vị trí sau. Repo không khẳng định quyền tái phân phối raw.

| File riêng | Vị trí tương đối | SHA-256 của snapshot benchmark |
|---|---|---|
| Skill Builder | data/assistment_2009/skill_builder_data_corrected_collapsed.csv | 162ef8d2d28bcbfea6591a282994062bd8d5eaa00636544292a0d268dca6e5da |
| Non-Skill | data/assistment_2009/non_skill_builder_data_new.csv | 79d663ccf98ab4766897e7b9516a9d71df118b6cd453dab673b27cce4acc9eaf |

Skill preprocessing kiểm tra checksum bắt buộc; cấu hình cp1252, single-skill, original=1, binary correct, user split seed 42. Non-Skill đọc UTF-8-sig và lọc tương ứng. Thư mục output giữ nguyên layout gốc để tránh đổi import/đường dẫn. Không dùng Full làm training nguồn mới.

Để khôi phục **dashboard benchmark cũ**, nhận bộ artifact riêng từ người giữ project gốc và đặt đúng layout:

- `results/assist2009_phase2a/`: toàn bộ artifact preprocessing, đặc biệt test/histories.jsonl; validate còn cần events.csv, target_eligibility.csv, skill_mapping.json, split_manifest.json và histories cả ba split.
- `results/assist2009_non_skill/`: các artifact tương ứng của Non-Skill.
- `results/assist2009_phase2c/`: dkt_seed42.ckpt, dkt_seed42_history.json, predictions_dkt_seed42_test.csv, predictions_bkt_test.csv, metrics.json. metrics.json phải là bản benchmark ba seed.
- `results/assist2009_phase2b_run3/`: predictions_baseline_test.csv và metrics.json. Không lấy BKT Phase 2B lỗi context.
- `results/assist2009_non_skill_training/`: dkt_seed43.ckpt, dkt_seed43_history.json, predictions_dkt_seed43_test.csv, predictions_bkt_test.csv, predictions_baseline_test.csv, metrics.json.

Dashboard dùng history test + ba prediction CSV + training history; không cần checkpoint cho từng click. `kt_demo/validate.py` mới cần checkpoint cùng preprocessing đầy đủ và đối chiếu hash `presentation/ARTIFACT_MANIFEST.csv`. Manifest ghi inventory nghiên cứu, chứa cả đường dẫn loại khỏi Git; không phải danh sách file public bắt buộc. Bản train mới không khớp checksum benchmark cũ: đánh giá bằng scripts/evaluate.py, không sửa manifest để gọi là tái tạo cũ.

Để tái tạo riêng baseline Skill nếu không phục hồi: baseline là mean(correct) theo skill chỉ trên train; script historical DKT-only không sinh baseline/BKT. Dashboard so sánh ba mô hình chỉ mở khi có đủ output được căn chỉnh. Lệnh stage DKT/BKT phía README không tự sinh baseline Skill cũ.

Pipeline integration chọn nguồn bằng `--sources`: `skill`, `non-skill`, `assistments` (mặc định: Skill+Non-Skill, không Full), `full`, `daotao`, `all`. Chỉ `full`/`all` mới cần Full CSV. daotao chỉ cần hai export nội bộ; Skill/Non-Skill cần thêm events.csv membership từ preprocessing cùng raw. Xem [hướng dẫn integration](../data_integration/README.md) để chạy validation cơ bản hoặc `--benchmark --benchmark-root PRIVATE_ARCHIVE` khi có bản lưu gốc nguyên vẹn. Khóa HMAC riêng được tạo khi cần, không đưa lên Git. Không chạy integration nếu chỉ cần xem báo cáo tổng hợp.

Các tài liệu aggregate giữ trong Git; raw, normalized, learner-level figures, histories, splits và predictions trao đổi qua kênh riêng có quyền truy cập. Không dùng git add -f cho chúng.
