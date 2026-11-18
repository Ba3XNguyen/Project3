# Kiểm thử bản repository staging

## Bổ sung sau rà soát integration — 17/11/2026

- `python tests/integration_smoke.py`: PASS 7 test methods; một test bao gồm 6 lựa chọn nguồn (skill/non-skill/assistments/full/daotao/all). Có thêm kiểm tra validator không tạo khóa khi thiếu key. Dữ liệu hoàn toàn hư cấu, không train model trong integration test.
- Ca âm: thiếu hoặc sai membership, thay raw, thay điểm output và sửa cả checksum đều bị từ chối. `--benchmark` khi thiếu archive riêng báo lỗi, validation mặc định vẫn chạy với nguồn đã chọn.
- Ca biên: daotao không có submission/không có điểm số vẫn hợp lệ; không sinh nhãn correct. Skill/Non-Skill cần events.csv từ cùng raw; Full không tự được đưa vào chế độ mặc định.
- Schema/nội dung/consistency tách khỏi archive benchmark; `--benchmark-root` chỉ tới snapshot gốc nếu muốn kiểm tra mở rộng. Validation cơ bản không đòi checkpoint hoặc metric benchmark.
- Test dùng đường dẫn có dấu cách trên Windows; UTF-8 được chỉ định khi đọc/ghi tiếng Việt. Ubuntu chưa chạy trực tiếp trong phiên này.
- `python tests/smoke.py` và release check được chạy lại sau thay đổi. Xem RELEASE_REVIEW.json và kết quả báo cáo cuối; không commit/push hoặc train benchmark lớn.

Các lần chạy sandbox gặp lỗi quyền đọc/dọn thư mục tạm Windows; chạy lại ngoài sandbox đã giải quyết. Lỗi encoding phát hiện trong lần test đầu đã được sửa; không bỏ kiểm tra để đạt PASS.

Ngày 17/11/2026. Thực thi trên Windows 11, Python 3.13.1, CPU; tái sử dụng virtual environment đã có của project gốc để chạy source staging. Không cài môi trường mới từ requirements trên Ubuntu, chưa kiểm chứng clean install trên máy khác. Dependency trực tiếp thực tế: requirements-tested.txt.

| Lệnh / kiểm tra | Kết quả thực tế |
|---|---|
| python scripts/check_setup.py | PASS import numpy/pandas/sklearn/torch/streamlit/plotly, vendored DKT và pyBKT; báo artifact riêng còn thiếu đúng dự kiến |
| python tests/smoke.py | PASS, exit 0; fixture hư cấu 20 learner × 4 event |
| prepare.py --config <fixture-config> --output <new-prepared> (do smoke gọi) | PASS preprocessing 80 dòng an toàn, split/mapping/eligibility |
| scripts/train_dkt.py --data <fixture-prepared> --output <new-run> --max-epochs 1 --patience 1 | PASS thực sự train 1 epoch, lưu/nạp checkpoint và xuất predictions |
| scripts/evaluate.py <fixture-prediction-test.csv> | PASS thực sự tính metric từ CSV của smoke; không coi là research metric |
| Streamlit AppTest hai dataset ở trạng thái clean clone | PASS không exception, hiện thông báo thiếu artifact và đường dẫn hướng dẫn |
| python kt_demo/check_server.py (smoke gọi) | PASS server thật, health và root HTTP 200; server dừng sau kiểm tra |
| python scripts/release_check.py | PASS pattern/size/path scan, 8 ignore probes, không gitlink/nested Git trong code |
| Đối chiếu 45 file source đã sao chép với bản gốc | PASS source gốc nguyên hash; staging modifications được ghi trong SOURCE_PROVENANCE.json |
| Rà danh tính thật trong tài liệu public | PASS không có literal email/tên/IP/username chữ từ CSV daotao; không xuất danh sách định danh |
| git diff --cached --check -- . ':(exclude)code/**' | PASS; whitespace có sẵn trong vendor được giữ để không sửa source bên thứ ba |

Lần smoke đầu hoàn thành checks nhưng framework có lỗi quyền dọn TEMP khi thoát sandbox. Đã chạy lại ngoài sandbox với output mới: exit 0, không lỗi cleanup; chỉ còn cảnh báo ScriptRunContext thông thường của AppTest.

Giới hạn: chưa chạy benchmark lớn, chưa chạy full preprocessing raw trong repo mới, chưa kiểm thử Ubuntu/clean dependency installation, chưa review bố cục bằng trình duyệt. Dashboard dữ liệu thật cần bộ artifact riêng như ARTIFACT_SETUP.md; trạng thái thiếu artifact đã được kiểm thử. Full-history DKT loop giữ nguyên; không công bố AUC fixture làm kết quả đồ án. BKT runtime import PASS; BKT training stages Linux chưa chạy lại.

Repo có thể commit và đưa lên GitHub private để hai thành viên cộng tác sau review danh sách file. Chưa tạo remote, commit hoặc push. Public release còn cần chủ sở hữu quyết định license code nhóm và quyền công bố; MIT vendor đã giữ đầy đủ. Scan tự động không bảo đảm phát hiện mọi loại secret hoặc mọi vấn đề pháp lý.
