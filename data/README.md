# Chuẩn bị dataset riêng

Git chỉ theo dõi README này. ASSISTments cần tải riêng từ nguồn được phép hoặc nhận bản lưu hợp lệ của nhóm; daotao.ai là dữ liệu nội bộ, không đưa raw/định danh lên Git dù repository private.

| Nguồn | Đường dẫn tính từ root repository |
|---|---|
| ASSIST Skill Builder | data/assistment_2009/skill_builder_data_corrected_collapsed.csv |
| ASSIST Non-Skill Builder | data/assistment_2009/non_skill_builder_data_new.csv |
| ASSIST Full, chỉ khi chọn rõ | data/assistment_2009/full_dataset.csv |
| Activity nội bộ | data/daotao_ai/Activity Log at 134621 6112026.csv |
| Grades nội bộ | data/daotao_ai/Visual Grades Report at 134113 6112026.csv |

Kiểm tra hash bản benchmark theo [ARTIFACT_SETUP](../docs/ARTIFACT_SETUP.md). Không đổi config checksum để làm một dataset khác trông như snapshot cũ.

| Bước | Cần chuẩn bị |
|---|---|
| Smoke / integration smoke | Chỉ code và dependency tương ứng; test tự tạo fixture hư cấu |
| Preprocessing Skill hoặc Non-Skill | CSV thật tương ứng; không cần checkpoint |
| Training DKT | Histories ba split + skill_mapping từ preprocessing; không cần checkpoint cũ |
| Evaluate | Prediction CSV của run cần đánh giá |
| Integration daotao | Hai CSV nội bộ; không cần ASSIST hoặc checkpoint |
| Integration Skill/Non-Skill | Raw tương ứng + results/<cohort>/events.csv từ preprocessing cùng raw |
| Integration Full | Full CSV, luôn đóng KT eligibility gate; không cần events membership |
| Dashboard dữ liệu thật | Histories test, predictions Baseline/BKT/DKT, training history đúng bộ artifact |
| Kiểm chứng checkpoint | Checkpoint và toàn bộ artifact liên quan theo ARTIFACT_SETUP |
| Validation benchmark mở rộng | Bản lưu benchmark gốc nguyên vẹn gồm source/metrics/checksum, tùy chọn --benchmark-root |

Không dùng `git add -f` cho dataset, khóa HMAC hoặc output theo learner. Đặt dữ liệu bằng đường dẫn tương đối trên Windows/Ubuntu; với integration có thể dùng --input-root trỏ tới thư mục riêng chứa data/ và results/.
