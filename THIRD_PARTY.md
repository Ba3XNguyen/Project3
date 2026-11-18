# Third-party source provenance

| Runtime | Upstream | Commit kiểm tra cục bộ | Version metadata | License |
|---|---|---|---|---|
| pyBKT pure Python | https://github.com/CAHLR/pyBKT | 9bfeb31c09ea63c5962afc06b3935b5eefb4029e | setup.py: 1.5.0 | MIT, code/pyBKT/LICENSE |
| pyKT DKT | https://github.com/pykt-team/pykt-toolkit | ccbaf37b07e3e7ff7b2415475b2faacb967d54ea | setup.py: 0.0.38 | MIT, code/pykt-toolkit/LICENSE |

Repo mới không chứa .git của hai upstream. Giữ 19 file Python runtime source-py/pyBKT (không copy test, C++/Eigen, datasets, notebooks) và duy nhất pyKT models/dkt.py. Thêm hai __init__.py tối thiểu cho namespace pykt/models, tránh import registry mọi model cùng dependencies không dùng. DKT class và state_dict keys không bị thay đổi.

Snapshot nguồn có git status dirty. Đã so 19 file runtime pyBKT và dkt.py với HEAD sau chuẩn hóa CRLF→LF: không có khác biệt nội dung. Điều này không khẳng định toàn clone sạch hoặc mọi file khác là newline-only; những file ngoài runtime không được đưa vào repo. Ghi provenance source hash trong SOURCE_PROVENANCE.json.

DKT checkpoint benchmark dùng embedding/hidden=200, dropout=.1, 101 hoặc 169 skill. Không thay bằng package mới nhất. Bản training lịch sử dùng Python 3.12.3/torch 2.5.1+cpu; môi trường tái kiểm chứng demo cũ Windows Python 3.13.1/torch 2.15.0+cpu. Xem VALIDATION.md cho môi trường staging thực tế.
