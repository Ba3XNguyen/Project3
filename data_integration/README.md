# Chuẩn hóa schema và đánh giá khả năng tích hợp

Module đang phát triển: đã xây dựng canonical schema, ánh xạ trường và adapter riêng từng nguồn. ASSISTments và daotao.ai **chưa gộp để huấn luyện chung**. daotao.ai thiếu correct theo từng attempt và question-to-skill đã xác minh; **chưa train DKT trên daotao.ai**. Output giữ các bảng riêng, không tạo nhãn hoặc tương tác KT từ snapshot điểm.

## Chọn nguồn

```bash
python data_integration/preprocess.py --sources daotao --output data_integration/normalized_daotao
python data_integration/validate_outputs.py --output data_integration/normalized_daotao
```

Hai lệnh trên chỉ cần hai CSV daotao và khóa HMAC riêng do preprocessing tạo nếu chưa có. Các chế độ:

| --sources | CSV cần có | Dependency bổ sung |
|---|---|---|
| skill | Skill Builder | results/assist2009_phase2a/events.csv |
| non-skill | Non-Skill Builder | results/assist2009_non_skill/events.csv |
| assistments (mặc định) | Skill + Non-Skill | Cả hai events.csv ở trên; không yêu cầu Full |
| full | Full | Không cần membership; KT gate luôn bằng 0 |
| daotao | Activity + Grades | Không cần ASSIST/benchmark |
| all | Cả 5 CSV | Hai events.csv membership |

Có thể chọn nhiều nguồn: `--sources skill daotao`. Thứ tự xử lý được chuẩn hóa, không trộn bảng. Cần chạy preprocessing trong experiments/ tương ứng trước khi integration ASSIST: events.csv phải được tạo từ chính raw đang dùng. Adapter kiểm tra source_record, khóa event, skill, correct, original, split và eligibility; không tự fit lại split/mapping. Sai membership phải báo lỗi, không bỏ qua để chạy tiếp.

`--input-root` mặc định là root repo; thư mục được chỉ định phải chứa data/ và results/ theo layout. `--key-file` mặc định `.local_data_integration/pseudonym.key`; nếu đổi đường dẫn phải cung cấp cùng khóa cho validator. Không ghi nội dung khóa vào manifest. `--output` phải là thư mục chưa tồn tại; dùng `data_integration/normalized_<run>` để Git tự bỏ qua. Không đặt key bên trong output. CSV/JSON output dùng UTF-8 trên Windows và Ubuntu.

## Hai mức validation

**Cơ bản (mặc định):** chỉ cần các raw/membership đúng nguồn đã chọn, output và khóa HMAC của run. Kiểm tra checksum nguồn/output/source adapter; schema canonical, nhãn 0/1, gate daotao/Full, identity, bảo toàn dòng/nhãn và thứ tự/prefix hành vi. Validator tái chạy adapter vào thư mục tạm rồi so toàn bộ bảng canonical, điểm thành phần và thống kê để phát hiện dữ liệu sai dù checksum output bị cập nhật. Việc replay dùng cùng adapter bổ sung cho các invariant độc lập; không phải chứng minh ngữ nghĩa nguồn bên ngoài. Không inference hoặc training.

```bash
python data_integration/validate_outputs.py --output data_integration/normalized_daotao
```

**Benchmark mở rộng:** thêm kiểm tra tất cả file trong manifest benchmark gốc và metric summary. Cần bản lưu riêng nguyên vẹn; repo này có điều chỉnh source nên không thể mặc nhiên coi là bản lưu gốc. Thay PRIVATE_ARCHIVE bằng thư mục thực tế:

```bash
python data_integration/validate_outputs.py --output data_integration/normalized_daotao --benchmark --benchmark-root PRIVATE_ARCHIVE
```

Thiếu/sai một artifact phải FAIL. Không dùng cờ này để bỏ kiểm tra cơ bản. Kết quả được ghi tại `<output>/VALIDATION_REPORT.json`, bên trong output riêng bị Git bỏ qua. Header-only daotao bị từ chối rõ ràng; file có event nhưng không có submission hoặc không có điểm số vẫn xử lý được. Timestamp trùng giữ rank theo source_record để ổn định kỹ thuật, chưa chứng minh thứ tự nghiệp vụ.

Kiểm thử không cần dữ liệu riêng: `python tests/integration_smoke.py`. Fixture hoàn toàn hư cấu, kiểm tra nguồn độc lập, thiếu/sai membership, sửa raw/output và benchmark opt-in. Không dùng metric/count fixture làm kết quả nghiên cứu.
