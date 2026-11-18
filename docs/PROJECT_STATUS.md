# Trạng thái project

Ngày chuẩn hóa repo: 17/11/2026.

- Đã có benchmark ASSIST2009 Skill/Non-Skill: baseline tần suất, corrected BKT và DKT-LSTM ba seed. Metric tổng hợp ở EXPERIMENT_RESULTS.md.
- Checkpoint demo từng được kiểm chứng toàn bộ test ngày 12/11/2026 trên Windows: 32.563/46.464 target, max ΔP=0 ở hai run được chọn. Đây là kiểm chứng lịch sử trong project riêng, không phải benchmark chạy lại khi đóng gói.
- Dashboard ba trang Performance/Replay/Skill Analysis; không gọi P(correct) là mastery thực tế.
- Audit daotao ngày 16/11: 131 submission, 2 learner, chưa có skill/correct theo attempt, 0 event KT đủ điều kiện.
- Repo staging giữ source, config và thống kê tổng hợp; không mang theo dữ liệu học viên hoặc checkpoint. Kết quả kiểm thử bản staging được ghi riêng trong VALIDATION.md.

Chưa hoàn thành: tiếp cận nguồn grade theo attempt của daotao, question/skill crosswalk, thêm learner, pilot miền đích, đánh giá can thiệp học tập. Không gọi repo là LMS tích hợp production.
