# Báo cáo kiểm kê dữ liệu daotao.ai và thông tin còn thiếu cho Knowledge Tracing

Ngày: 16/11/2026 — Đồ án 3, EduBrain LMS.

**Kết luận:** Đã thu được log gửi đáp án và snapshot điểm có thật, nhưng chưa có cặp skill–correct theo từng lần trả lời. Hiện có **0 tương tác KT đủ điều kiện xác minh**, nên chưa train DKT trên daotao.ai. Benchmark BKT/DKT trên ASSISTments vẫn là kết quả của nguồn riêng.

**Dữ liệu đã thu nhận.** Đã đọc trực tiếp `Activity Log at 134621 6112026.csv` và `Visual Grades Report at 134113 6112026.csv` trong `data/daotao_ai/`, không chỉ kế thừa báo cáo trước.

| Nguồn | Nội dung kiểm chứng được | Giới hạn |
|---|---|---|
| Activity: 136 record × 5 cột | 4 tài khoản; 131 lượt gửi của 2 learner (52 và 79 lượt), 30 input ID; 5 sự kiện đăng ký/hủy đăng ký/tạo báo cáo | Có mã lựa chọn choice_0…3, chưa có nội dung đáp án, nhãn chấm hoặc skill |
| Thời gian activity | 136/136 parse được, từ 28/07 đến 06/11/2026; không trùng learner-time | Phải sort trước khi tạo chuỗi; timezone và độ đầy đủ log chưa xác minh |
| Grades: 82 record × 42 cột | 82 tài khoản, 8 có điểm tổng số; 193/2788 ô thành phần có số (6,92%) | 74 tổng điểm và 2595 ô thành phần là Chưa làm; thiếu attempt ID và thời điểm chấm |

Grades có điểm thành phần thật ở Dropdown, Câu 1…30 và Code Runner; Blank Common Problem/Text Input chưa có số. Điểm thành phần gồm 1 (189 ô), 0 (2), 5 (1), 10 (1), do đó không thể coi mọi điểm là nhị phân. Tổng thành phần khớp điểm tổng trên cả 8 hàng có số; điểm tối đa 42 là ở mức tổng. Không suy correct từ điểm tổng, điểm 1 hoặc Chưa làm.

**Khả năng liên kết.** Join username trim exact cho 3 tài khoản chung và đủ 131/131 lượt gửi đáp án. Đây chỉ là join tài khoản. Grades không có input ID, attempt ID hoặc graded_at để nối với từng lần gửi; 30 input không tự tương ứng 30 cột Câu 1…30. Số liên kết attempt → kết quả chấm và question → skill đã xác minh đều bằng 0.

**Đối chiếu trường cần thiết:**

| Trường | ASSISTments trong project | daotao.ai hiện có | Trạng thái |
|---|---|---|---|
| Learner ID | user_id; group/split theo learner | Tên đăng nhập ở hai file; ID chỉ ở Grades | AVAILABLE |
| Question/Input ID | problem_id; không đi vào embedding DKT skill-only | 30 input DOM ID; Grades chỉ nhãn Câu 1…30 | PARTIAL |
| Skill ID | skill_id → skill_idx fit trên train | Không có skill hoặc mapping question-to-skill | MISSING |
| Correct (0/1) | correct nhị phân theo event | Không có nhãn chấm từng submission | MISSING |
| Interaction order | order_id số; sort trong learner | Có thể sort Thời gian; không trùng learner-time trong export | PARTIAL |
| Timestamp | Không bắt buộc; pipeline dùng order_id | 136/136 parse được dd/mm/yyyy HH:MM:SS | PARTIAL |
| Attempt ID | event_id dẫn xuất từ order_id; không phải số lần thử | Không có submission/attempt ID trong hai CSV | MISSING |
| Score | DKT dùng correct; không cần score riêng | 8 tổng điểm; 193 điểm thành phần snapshot | PARTIAL |

AVAILABLE: có và dùng được trong phạm vi đã kiểm tra. PARTIAL: có một phần hoặc cần ánh xạ/xác minh thêm. MISSING: không tìm thấy trong hai export. UNVERIFIED: có vấn đề về độ tin cậy/phạm vi chưa đủ bằng chứng để xác nhận.

**Điều kiện DKT.** Source thật dùng learner, skill_idx, correct nhị phân và thứ tự; learner phải có ít nhất 2 event để tạo target tiếp theo. Question ID/timestamp/score không bắt buộc làm tensor input, nhưng khóa question và attempt hoặc tương đương cần cho nối skill/nhãn từ nguồn daotao. Hiện có 0 learner với ≥2 tương tác KT hợp lệ. Hai chuỗi log dài 52/79 chỉ là chuỗi hành vi. Kể cả khôi phục toàn bộ nhãn, 2 learner chưa đủ ba tập không rỗng độc lập theo learner.

**Đề nghị thu thập tiếp:** (1) grade theo mỗi lần nộp, kèm learner–question–attempt key, correct hoặc score/max_score và chính sách chấm; (2) catalog input → question ổn định → cột điểm; (3) question-to-skill được chuyên môn duyệt; (4) submitted_at/graded_at, timezone và server order; (5) thêm learner cùng phạm vi export rõ ràng. Đề nghị quản trị kiểm tra nguồn chấm bài/log/cấu trúc nội dung của triển khai Open edX/daotao.ai; đây là nguồn đề xuất, chưa xác minh quyền truy cập hoặc API/database cụ thể.


Nguồn: audit riêng ngày 16/11/2026, chỉ công bố số tổng hợp; raw và bảng theo learner không nằm trong Git.
