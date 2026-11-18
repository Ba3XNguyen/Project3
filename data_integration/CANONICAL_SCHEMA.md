# Canonical event schema v1

Schema dùng chung là hợp đồng biểu diễn; không tự bảo đảm hai nguồn có cùng nhãn, kỹ năng hoặc đơn vị quan sát. CSV UTF-8, dấu phẩy, header, ô rỗng = chưa biết/không có; số 0 là giá trị quan sát hợp lệ. Không thay missing bằng 0, không gán thời gian từ tên file, không coi “Chưa làm” là sai. Không gộp nguồn huấn luyện.

| Trường | Kiểu / ý nghĩa | ASSIST2009 Skill & Non-Skill | ASSIST2009 Full | daotao.ai |
|---|---|---|---|---|
| source | string, nguồn và variant | quan sát provenance file | variant riêng | daotao_ai; event_kind phân biệt log/snapshot |
| learner_id | string giả danh | suy ra HMAC từ user_id | cùng namespace ASSIST cho kiểm tra overlap | suy ra HMAC từ Tên đăng nhập, nhất quán hai export |
| course_id | string nullable | chưa có; school/class/sequence không thay cho course | chưa có | quan sát course-v1 trong URL của 131 submission; 5 sự kiện còn lại thiếu; grades không có |
| assessment_id | string nullable | cần mapping assignment_id → assessment, để trống | như trái | cần block/assessment metadata; sequential trong URL chưa chứng minh là assessment |
| question_id | string nullable | problem_id có namespace variant | như trái | input DOM ID quan sát ở 131 log; chưa xác minh cấp component/block; grades chỉ có nhãn cột nên để trống |
| skill_id | string nullable, một skill đã có semantics | chỉ skill_id số đơn, namespace variant; multi giữ raw_skill_ids | list_skill_ids chỉ giữ raw_skill_ids, canonical skill để trống vì semantics chưa xác minh | chưa có; cần question→skill do chuyên môn duyệt |
| correct | integer 0/1 nullable | chỉ nhãn 0/1 có sẵn, không tái định nghĩa | giữ đúng binary đã cung cấp, fractional để raw_correct, không làm tròn | thiếu ở từng attempt; không suy từ choice, snapshot hay điểm tổng |
| interaction_order | integer nullable, thứ tự trong learner | order_id quan sát làm khóa thứ tự (không phải rank liên tục) | như trái | suy ra rank theo timestamp cục bộ của từng learner; snapshot trống |
| timestamp | ISO8601 nullable | không có | không có | parse Thời gian dd/mm/yyyy HH:MM:SS; giữ naive vì timezone export chưa xác minh |
| selected_answer | string nullable, lựa chọn đã gửi | để trống; answer_text/answer_id chưa chứng minh là lựa chọn an toàn để demo | không có | choice_0..3 trích nguyên văn từ payload đã khớp regex; không phải answer key |
| response_time_ms | số không âm nullable | quan sát ms_first_response; missing/số âm để trống | ms_first_response_time | chưa có; chênh timestamp không phải response time |
| attempt_count | số không âm nullable, theo định nghĩa nguồn | quan sát attempt_count; không dùng làm feature ở chính event cần dự đoán | có | chưa có; observed_prior_same_input_submissions là số lần thấy trong export, không phải tổng attempts thật |
| hint_count | số không âm nullable | quan sát hint_count | chưa có | chưa có; không gán 0 |
| max_score | số không âm nullable | chưa có | chưa có | Điểm tối đa=42 chỉ ở aggregate snapshot; max từng câu chưa có |
| obtained_score | số không âm nullable | chưa có; không sao chép correct sang điểm | chưa có | Điểm tổng ở aggregate; số ở ô thành phần giữ ở component snapshot, không gán vào event |

Các trạng thái từng nguồn/trường nằm trong [FEATURE_MAPPING.csv](FEATURE_MAPPING.csv): `observed` (trực tiếp), `derived` (biến đổi xác định), `mapping_required` (cần đối chiếu ngoài), `unavailable` (không có). Cột `raw_evidence` chỉ tên trường và phép biến đổi, không chứa thông tin cá nhân.

Mở rộng provenance: `event_id`, `source_record` (số bản ghi CSV, không phải dòng vật lý do quoted multiline), `event_kind`, `question_id_basis`, `timestamp_timezone_status`, `raw_skill_ids`, `raw_correct`, `original`, `observed_assignment_id`, `split`, `common_target`, `kt_eligible`, `exclusion_reason`. `component_label` chỉ xuất trong bảng snapshot điểm có tên cột quan sát; không biến “Câu 1” thành question_id. Link raw qua source_record là dữ liệu riêng nội bộ, không kèm bảng danh tính.

`learner_id = <domain>:learner:<96-bit HMAC-SHA256>` dùng secret key ngoài thư mục xuất. Hai domain là assist2009 và daotao_ai. Cùng user_id ASSIST có cùng pseudonym giữa các variant để nhận diện overlap; không hàm ý cùng người giữa nền tảng. Skill/question namespace theo variant ASSIST là lựa chọn bảo thủ, tránh khẳng định hai catalog tương đương. daotao dùng `daotao_ai:input:<observed input id>`; hậu tố `_2_1` được giữ nguyên, không suy thành mã câu hỏi toàn cục. Không có skill giả thay thế question.

ASSIST xuất toàn bộ raw rows để kiểm kê, giữ nguyên thứ tự CSV; muốn chuỗi phải sort learner + **numeric** interaction_order. `kt_eligible=1` chỉ ở Skill/Non-Skill có khóa hợp lệ, correct binary, skill số đơn, original=1 và khớp membership lịch sử. Các cột split/common_target kế thừa events.csv; không chia lại tập. Đây không phải toàn bộ raw đều dùng train. Full luôn `kt_eligible=0` cho đến khi xác minh skill và overlap; số bản ghi thỏa bộ lọc số học không phải benchmark được duyệt.

daotao xuất activity có rank theo từng learner và thời gian; 131 submission là subset của 136 activity, không cộng hai bảng làm 267 event. Snapshot tổng và điểm thành phần có `event_kind` riêng, thiếu timestamp/attempt/question link nên không dùng như chuỗi tương tác. Giữ 82 aggregate snapshot (kể cả chưa làm) và 193 điểm thành phần có số; không tạo hàng tương tác cho 2595 ô “Chưa làm”. Không join snapshot với activity ngoài thống kê giao tập tài khoản.

KT cần learner, skill, correct, khóa thứ tự tin cậy và ít nhất hai interaction cùng learner; question_id hữu ích nhưng không bắt buộc cho DKT skill-only hiện tại. Timestamp thực không bắt buộc với ASSIST vì đã có order_id. Cần timestamp + attempt ID có semantics rõ khi nối nhãn daotao. Mọi điều kiện availability cần xét trước thời điểm dự đoán; cột chứa metadata hoặc nhãn không tự động là predictor.

Pseudonymization không đồng nghĩa anonymization: thời gian/chuỗi vẫn có thể tái nhận diện khi kết hợp nguồn ngoài. Các export loại tên, email, username gốc, IP và URL HTML; key và raw phải giữ riêng. Không gửi key, raw hoặc manifest có thông tin riêng cho demo công khai.
