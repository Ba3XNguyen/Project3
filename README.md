# EduBrain LMS — Knowledge Tracing

Project Đồ án 3: benchmark Baseline/BKT/DKT trên ASSISTments 2009–2010, dashboard replay và phân tích khả năng tích hợp daotao.ai. Kết quả nghiên cứu là lịch sử đã kiểm chứng; các smoke test chỉ xác nhận phần mềm chạy.

## Project Structure (Cấu trúc dự án)

```text
EduBrain-LMS-GitHub/
├── code/                 runtime/source subset pyBKT và DKT, kèm MIT licenses
├── experiments/          pipeline và cấu hình thực nghiệm
│   ├── assist2009_preparation/
│   ├── assist2009_non_skill/
│   ├── assist2009_robustness/
│   └── assist2009_non_skill_training/
├── scripts/              check_setup.py, train_dkt.py, evaluate.py, release_check.py
├── kt_demo/              dashboard Streamlit, đọc artifact và kiểm chứng checkpoint
├── data_integration/     canonical schema, ánh xạ trường, adapters và validation
├── docs/                 hướng dẫn, trạng thái và kết quả nghiên cứu
├── tests/                smoke.py và integration_smoke.py
├── data/                 README; người dùng tự chuẩn bị dataset, raw bị Git bỏ qua
├── results/              README; checkpoint/kết quả riêng bị Git bỏ qua
├── presentation/         metric tổng hợp và checksum manifest lịch sử
├── requirements.txt
└── README.md
```

Cây trên liệt kê thư mục thực tế được chia sẻ; không liệt kê Git metadata, cache và thư mục kiểm thử riêng. `scripts/` cung cấp các lệnh hỗ trợ training/evaluation/setup/release; preprocessing được gọi trực tiếp từ `experiments/` hoặc `data_integration/`.

`data_integration/` là pipeline **chuẩn hóa schema và đánh giá khả năng tích hợp**, đang phát triển cho tương lai. Đã có schema chung và bước đầu ánh xạ dữ liệu. **Chưa gộp ASSISTments với daotao.ai để huấn luyện DKT.** daotao.ai chưa đủ nhãn đúng/sai theo từng attempt và question-to-skill; **không được tuyên bố đã train DKT trên daotao.ai**. Xem [hướng dẫn integration](data_integration/README.md).

| Trạng thái | Phạm vi |
|---|---|
| Đã hoàn thành | Benchmark ASSIST lịch sử, adapter hai cohort, dashboard và kiểm chứng checkpoint; schema integration và kiểm kê nguồn |
| Đang phát triển | Integration theo nguồn, kiểm chứng ngữ nghĩa và thu thập grade/skill của daotao |
| Chưa triển khai | Train DKT trên daotao, train chung hai nguồn, đánh giá tác động cá nhân hóa/LMS production |

Workflow benchmark: **Dataset → Preprocessing → Training → Evaluation → Dashboard**. Integration là nhánh chuẩn hóa/kiểm kê riêng; output daotao hiện chưa đi vào Training.

## Quick Start

1. **Clone** repository private bằng URL nhóm đã tạo: `git clone https://github.com/OWNER/EduBrain-LMS.git`, sau đó `cd EduBrain-LMS`. OWNER là placeholder, chưa có repo được tạo trong nhiệm vụ này.
2. **Tạo venv** theo hướng dẫn Ubuntu/Windows bên dưới.
3. **Cài dependency:** `python -m pip install -r requirements.txt`; kiểm tra bằng `python scripts/check_setup.py`.
4. **Smoke test:** `python tests/smoke.py` và `python tests/integration_smoke.py`. Fixture hư cấu chỉ kiểm tra phần mềm, không phải benchmark nghiên cứu thật.
5. **Chuẩn bị dữ liệu riêng:** xem [data/README.md](data/README.md); chỉ cung cấp CSV của nguồn muốn chạy. Dataset/checkpoint không nằm trong Git.
6. **Preprocessing → train → evaluate:** dùng các lệnh bên dưới. Training thật chỉ chạy sau bước chuẩn bị; không cần chạy benchmark lớn để kiểm tra setup.
7. **Mở dashboard:** `python -m streamlit run kt_demo/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false`. Khi chưa khôi phục histories/predictions/training history riêng, dashboard chỉ báo thiếu artifact và hướng dẫn; không tạo dữ liệu thay thế.

## Cài đặt Ubuntu

Thay OWNER bằng tài khoản nhóm sau khi tự tạo repository. Không có remote được tạo tự động.

```bash
git clone https://github.com/OWNER/EduBrain-LMS.git
cd EduBrain-LMS
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/check_setup.py
```

Dùng Python 3.11–3.13. Có thể cần cài gói python3-venv của Ubuntu. Runtime DKT và pyBKT thuần Python đã có trong repo, không cần cài toàn bộ upstream hoặc C++ Eigen. Không thay implementation DKT.

Windows PowerShell: thay bước tạo/kích hoạt bằng `py -3.13 -m venv .venv` và `.\.venv\Scripts\Activate.ps1`; nếu policy không cho activate, dùng `.\.venv\Scripts\python.exe` thay `python`. DKT CLI, preprocessing và dashboard hỗ trợ đường dẫn tương đối trên hai OS. Các BKT orchestration lịch sử vẫn dùng module Linux `resource`: chạy chúng trên Ubuntu, không tuyên bố đã kiểm thử BKT benchmark trên Windows.

## Chuẩn bị dữ liệu, train và đánh giá

Đọc [ARTIFACT_SETUP](docs/ARTIFACT_SETUP.md) để lấy dữ liệu đúng quyền sử dụng và đặt đúng đường dẫn. Lệnh preprocessing không tải dữ liệu. Không dùng dữ liệu học viên trong commit.

```bash
python experiments/assist2009_preparation/prepare.py
python experiments/assist2009_non_skill/preprocess.py
python scripts/train_dkt.py --data results/assist2009_phase2a --output results/my_skill_run --seed 42
python scripts/evaluate.py results/my_skill_run/predictions_dkt_seed42_test.csv
```

Non-Skill: đổi `--data results/assist2009_non_skill`, seed 43 và một output mới. Wrapper tái dùng nguyên `run_dkt`, không yêu cầu phải train BKT trước. Đây là single-seed run mới; không tự thay metrics benchmark hoặc danh sách artifact dashboard. Source lịch sử dùng test trong mỗi epoch dù chọn checkpoint bằng validation; xem giới hạn trong docs/EXPERIMENT_RESULTS.md.

Để tái chạy đúng stage lịch sử trên Ubuntu sau preprocessing (thời gian dài; không thuộc smoke test):

```bash
python experiments/assist2009_robustness/bkt_isolated_stage.py
python experiments/assist2009_robustness/dkt_stage.py
python experiments/assist2009_non_skill_training/bkt_stage.py
python experiments/assist2009_non_skill_training/dkt_stage.py
```

Chỉ chạy với output mới/chưa có artifact cần giữ. Stage lịch sử có thể ghi đè output mặc định; đặt `ASSIST2009_PHASE2C_OUTPUT` và `ASSIST2009_NON_SKILL_TRAINING_OUTPUT` tới thư mục mới khi cần. Không gọi combined `run_robustness.py` main (đã vô hiệu hóa vì BKT main cũ thiếu context); corrected BKT nằm trong `bkt_one.py`.

## Dashboard

```bash
python -m streamlit run kt_demo/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Mở localhost:8501. Sau khi phục hồi bộ artifact benchmark riêng theo ARTIFACT_SETUP:

```bash
python kt_demo/validate.py
python kt_demo/test_dashboard.py
```

## Kiểm tra nhanh

```bash
python tests/smoke.py
python scripts/release_check.py
```

Smoke sinh 80 dòng hoàn toàn hư cấu trong thư mục con duy nhất dưới `.test_artifacts/`, train đúng 1 epoch và kiểm tra checkpoint/metrics/dashboard. Không đưa metrics fixture vào báo cáo nghiên cứu. Mỗi lần chạy tạo output mới. `requirements-tested.txt` ghi phiên bản trực tiếp đã dùng, còn `requirements.txt` là khoảng phiên bản hỗ trợ cần kiểm thử khi nâng cấp.

Xem [PROJECT_STATUS](docs/PROJECT_STATUS.md), [TEAM_WORKFLOW](docs/TEAM_WORKFLOW.md), [REPO_AUDIT](REPO_AUDIT.md) và [VALIDATION](docs/VALIDATION.md). Phần code nhóm chưa được gán giấy phép phát hành mới; xem LICENSE_POLICY.md. Không commit dữ liệu, secret, output theo learner. Repo chưa push và chưa tạo trên GitHub.
