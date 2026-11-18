# Làm việc nhóm hai thành viên

`main` giữ code chạy được; mỗi nhiệm vụ dùng nhánh `feature/<ten>` hoặc `fix/<ten>`. Thành viên A phụ trách pipeline/model/evaluation, B phụ trách dashboard/data contracts; đổi vai review cho nhau. Chỉ merge sau review và smoke PASS.

```bash
git switch -c feature/task-name
# sửa code, kiểm thử
git status --short
git diff --check
git add <file-code-cu-the>
git diff --cached --stat
python scripts/release_check.py
git commit -m "Describe concrete change"
```

Sau khi chủ repo tự tạo GitHub repository và xác nhận danh sách public, cấu hình remote đúng URL. Nhiệm vụ chuẩn hóa không tự tạo remote/commit/push. Nhóm nên bật branch protection và PR review nếu gói GitHub hỗ trợ.

PR ghi vấn đề, cách thay đổi hành vi, lệnh kiểm thử và dữ liệu cần có. Model PR ghi seed, split, config, nguồn metric; tách metric smoke khỏi research. Không đổi label/mapping để làm đẹp số. Review schema trước khi thay input/output pipeline.

Không commit data/, results/, .env, key, danh sách learner, raw daotao hoặc checkpoint. Mỗi máy có virtual environment và secret riêng; dùng kênh dữ liệu được kiểm soát để trao đổi. Khi cần bug report, dùng fixture hư cấu hoặc thống kê không định danh, không dán raw payload.

Nâng dependency: tạo nhánh, chạy smoke và checkpoint reproduction bằng artifact riêng, cập nhật requirements-tested.txt cùng evidence. Chọn giấy phép cho code nhóm chỉ sau khi hai tác giả và đơn vị liên quan đồng ý; không gỡ MIT notices của vendor.
