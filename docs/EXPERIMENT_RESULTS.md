# Kết quả chính cho Đồ án 3

Ngày lập: 11/11/2026. Chỉ sử dụng metric đã lưu; không huấn luyện hoặc inference lại. Mục tiêu là dự đoán `correct` ở tương tác kế tiếp, không phải đo trực tiếp mastery hay tác động cải thiện học tập.

| Benchmark | Phương pháp | Test AUC ↑ | Accuracy@0.5 ↑ | Log Loss ↓ | Brier ↓ |
|---|---|---:|---:|---:|---:|
| Skill Builder — Phase 2C corrected | Skill-frequency | 0.621382 | 0.688389 | 0.604302 | 0.208043 |
| Skill Builder — Phase 2C corrected | BKT | 0.723331 | 0.726530 | 0.552692 | 0.185613 |
| Skill Builder — Phase 2C corrected | DKT-LSTM, seed 42 | **0.736992** | **0.736879** | **0.542593** | **0.180871** |
| Non-Skill Builder — Main Training | Skill-frequency | 0.638549 | 0.657262 | 0.620658 | 0.215698 |
| Non-Skill Builder — Main Training | BKT | 0.711812 | 0.686833 | 0.583006 | 0.199674 |
| Non-Skill Builder — Main Training | DKT-LSTM, seed 43 | **0.759875** | **0.716921** | **0.550587** | **0.185828** |

[CSV đầy đủ](../presentation/RESULTS_COMPARISON.csv) giữ độ chính xác số gốc, validation AUC và đường dẫn evidence. Không có F1 đã lưu nên không tự bổ sung. Skill baseline lấy từ `results/assist2009_phase2b_run3/metrics.json`: cùng cohort Phase 2A, cùng split và target, baseline train-only không đổi. Việc kế thừa baseline không đưa BKT Phase 2B có lỗi context vào bảng chính. Script đối chiếu ID và nhãn của cả ba prediction test trước khi xuất bảng.

Skill: 214425 event, 4003 người học, 101 skill train; train/val/test targets 147803/30056/32563. Non-Skill: 317264 event, 7834 người học, 169 skill train; targets 218154/44812/46464. Cả hai lọc original=1, single-skill, nhãn nhị phân, chia 70/15/15 theo người học seed 42; event đầu làm context. Thứ tự dùng order_id, không có timestamp thật.

Baseline là tần suất đúng theo skill chỉ từ train; BKT không forgetting, EM maxiter=100, tol=.005, 1 fit/skill, dự đoán trước cập nhật trên đầy đủ lịch sử cùng skill. DKT dùng embedding/LSTM hidden 200, dropout .1, Adam .001, batch một người, full history, tối đa 20 epoch/patience 5, ba seed 42/43/44. Chọn checkpoint theo validation (ngưỡng tăng .001), chọn seed theo validation AUC: Skill 42 (epoch 4), Non-Skill 43 (epoch 3).

DKT tốt nhất trong từng cohort theo các metric lưu. Bootstrap cặp theo người học (500 mẫu, seed 42) của DKT–BKT: Skill mean ΔAUC 0.013717, CI95% [0.007548, 0.019835]; Non-Skill 0.047933, [0.042945, 0.053249]. Đây là mean bootstrap, không phải hiệu chính xác hai AUC điểm. Nguồn: `results/assist2009_phase2c/paired_bootstrap.json`, `results/assist2009_non_skill_training/paired_bootstrap.json`.

Giới hạn cần nói với giảng viên: chỉ một split; BKT còn 3/101 và 7/169 skill chạm maxiter và chỉ một khởi tạo; test được tính trong quá trình chạy dù điều kiện chọn dùng validation; Skill test đã xem ở Phase 2B. Không gọi đây là đánh giá holdout mới hoàn toàn. AUC hai cohort không chứng minh nguồn nào tốt hơn; không có thí nghiệm chuyển miền. Nhãn là `correct` được cung cấp, chưa đồng nhất với “đúng ngay lần đầu”.

Nguồn: presentation/RESULTS_COMPARISON.csv và ARTIFACT_MANIFEST.csv. Báo cáo gốc research_audit và presentation được giữ trong kho nghiên cứu riêng. Các metric là lịch sử; chưa chạy benchmark lại trong repo staging.
