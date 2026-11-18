# Audit chuẩn hóa repository

Ngày 17/11/2026. Bản staging nằm trong workspace, project gốc không bị xóa/di chuyển/sửa. Quét metadata toàn cây, bao gồm env/cache và nested Git của nguồn; không đọc secret. Cột dung lượng tính theo byte file trên đĩa, không phải kích thước clone Git.

| Nhóm gốc | Số file | Bytes | Quyết định | Lý do / thay thế |
|---|---:|---:|---|---|
| results_non_skill_pre.log | 1 | 169 | LOẠI | Log tạm, không cần chạy repo. |
| .local_data_integration | 1 | 32 | LOẠI NHẠY CẢM | Chỉ đếm metadata file, không đọc nội dung khóa; không sao chép. |
| code | 14886 | 600679768 | GIỮ SUBSET | 19 runtime Python pyBKT + dkt.py, MIT licenses. Loại clone .git, C++/Eigen, notebook/data và Starter demo không dùng. |
| data | 5 | 288751673 | LOẠI KHỎI GIT | Toàn bộ raw ASSIST/daotao; hướng dẫn khôi phục ở docs/ARTIFACT_SETUP.md. |
| data_integration | 40 | 503291627 | GIỮ SOURCE/SCHEMA | Giữ preprocess/validate + schema/mapping. Loại normalized và báo cáo chứa đường dẫn cá nhân; viết báo cáo daotao tổng hợp riêng. |
| docs | 15 | 285398 | THAY BẰNG TÀI LIỆU CỘNG TÁC | Tài liệu lịch sử giữ trong project gốc; docs mới hướng dẫn setup, trạng thái, kết quả, chia việc. |
| experiments | 33866 | 1321795572 | GIỮ RUN CHÍNH | Giữ preprocessing hai cohort, DKT loop, corrected BKT stages. Loại dkt_smoke 2015, Phase 2B lỗi context, Full audit, env và logs. |
| kt_demo | 37021 | 1235660850 | GIỮ SOURCE/TEST | Giữ ba trang, core, validate, tests/server check; loại venv, logs và kết quả cá nhân hóa. Thêm thông báo artifact thiếu. |
| presentation | 6 | 133428 | GIỮ TỔNG HỢP | Giữ RESULTS_COMPARISON.csv và ARTIFACT_MANIFEST.csv; kết quả Markdown chuyển sang docs. Không giữ script build cũ phụ thuộc project đầy đủ. |
| research_audit | 5 | 127107 | TÓM TẮT | Không copy nguyên audit/tree có liên kết nhiều artifact riêng; kết luận và giới hạn ở docs/EXPERIMENT_RESULTS.md. |
| results | 507 | 449770580 | LOẠI KHỎI GIT | Tất cả checkpoint, per-learner predictions/histories/splits, outputs kể cả run trùng/chưa xong; metric tổng hợp giữ riêng. |
| survey | 174 | 26266400 | LOẠI | Reference clones, paper và dữ liệu legacy không thuộc runtime và chưa duyệt quyền tái phân phối. |

## Phân loại run và dữ liệu

Active: assist2009_phase2a → assist2009_phase2c corrected, assist2009_non_skill → assist2009_non_skill_training. Skill baseline kế thừa phase2b_run3, chỉ phục hồi prediction riêng khi demo. Phase 2B cũ có BKT thiếu context; không đưa combined main đó vào đường chạy hỗ trợ. Phase2B/run3 trùng snapshot theo audit trước; full/pilot và smoke 2015 không phải benchmark chính.
Biểu đồ theo learner không copy vì có thể tái nhận dạng. ROC/training curves được dashboard tính/vẽ khi phục hồi dữ liệu riêng; bảng metric và cấu hình/seed được giữ. Không copy PNG tùy tiện vì chưa xác minh nội dung từng ảnh.
Nguyên tắc PII: loại raw, normalized, test theo learner và ID mappings khỏi Git. Không coi giả danh hóa là đủ điều kiện public. Các tên tác giả/email trong phần giấy phép bên thứ ba là attribution, không phải học viên.

## Điều chỉnh source trong bản staging

Giữ đường dẫn experiments/code/kt_demo/data_integration để ROOT tương đối tiếp tục đúng. Không viết lại DKT. scripts/train_dkt.py là CLI mỏng tái sử dụng run_dkt và dkt_predict; single-seed output riêng. run_robustness import resource có fallback Windows và combined main lịch sử bị vô hiệu hóa. Các BKT subprocess dùng sys.executable/os.pathsep thay interpreter env cũ. Runtime BKT import được trên Windows; orchestration có resource vẫn chỉ hỗ trợ Ubuntu.
Namespace pykt tối thiểu thay registry import nhiều model; dkt.py giữ nguyên bytes. Dashboard có hướng dẫn thiếu artifact. SOURCE_PROVENANCE.json ghi hash trước/copy và thay đổi staging; các file nguồn đã sao chép được kiểm tra vẫn nguyên vẹn.

## Phạm vi công bố

Không có .env.example vì các lệnh hỗ trợ không cần API credential. requirements.txt dùng khoảng phiên bản; requirements-tested.txt ghi dependency trực tiếp đã chạy. Không tự gán license cho code nhóm; LICENSE_POLICY.md nêu việc cần tác giả quyết định. MIT vendor đã kiểm tra và giữ notice.
Repo local khởi tạo nhánh main, không remote/commit/push. Xem docs/VALIDATION.md và RELEASE_REVIEW.json cho checks và inventory public thực tế. Patterns không chứng minh tuyệt đối không có secret; danh sách candidate cần review trước push.
