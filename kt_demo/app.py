from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import roc_curve
from core import CONFIG, ROOT, paths, read_json, load_data, metrics

st.set_page_config(page_title='DKT · ASSISTments 2009',layout='wide')
st.title('Knowledge Tracing · DKT trên dữ liệu thực')
st.caption('P(correct) là xác suất trả lời đúng; không phải mức độ thành thạo thực tế. Không huấn luyện trong demo.')
name = st.sidebar.selectbox('Dataset',list(CONFIG))
page = st.sidebar.radio('Trang',['Model Performance','Student Replay','Skill Analysis'])

@st.cache_data
def get_data(name):
    return load_data(name)

try:
    events, predictions = get_data(name)
except Exception as exc:
    st.error('Thiếu hoặc không khớp artifact riêng của dataset đã chọn.')
    st.info('Xem docs/ARTIFACT_SETUP.md: đặt histories, prediction CSV và training history đúng thư mục results/. Không có dữ liệu thay thế.')
    st.code(str(exc))
    st.stop()

data, run, seed, _ = paths(name)
validation_path = ROOT/'kt_demo/validation_results.json'
if validation_path.exists():
    result = read_json(validation_path)['datasets'].get(name,{})
    st.sidebar.write('Kiểm chứng checkpoint: '+result.get('status','chưa chạy'))
    if result.get('status') == 'PASS':
        st.sidebar.caption(f"Lần kiểm chứng đã lưu: {result['inference_targets']:,} target; max Δ={result['max_probability_difference']:.3g}. Chạy validate.py để kiểm chứng lại artifact hiện tại.")
else:
    st.sidebar.warning('Chưa có kiểm chứng checkpoint. Chạy validate.py.')

if page == 'Model Performance':
    st.subheader('Test metrics tính lại từ CSV')
    st.dataframe(pd.DataFrame({k:metrics(v) for k,v in predictions.items()}).T.style.format('{:.6f}'))
    fig = go.Figure()
    for model,df in predictions.items():
        fpr,tpr,_ = roc_curve(df.label,df.probability)
        fig.add_trace(go.Scatter(x=fpr,y=tpr,name=model,mode='lines'))
    fig.add_trace(go.Scatter(x=[0,1],y=[0,1],name='Chance',mode='lines',line=dict(dash='dash')))
    fig.update_layout(xaxis_title='False positive rate',yaxis_title='True positive rate',title='ROC trên cùng tập target test')
    st.plotly_chart(fig,width='stretch')
    h = read_json(run/f'dkt_seed{seed}_history.json')
    history = pd.DataFrame(h['history'])
    left,right = st.columns(2)
    with left:
        st.write('Training loss · trung bình theo learner')
        st.line_chart(history.set_index('epoch')[['train_loss_mean_user']])
    with right:
        st.write('Validation AUC theo epoch')
        st.line_chart(history.set_index('epoch')[['auc']])
    st.caption(f"DKT seed {seed}, best epoch {h['best_epoch']}; Embedding 200 → LSTM 200 → sigmoid theo skill. Input: các cặp (skill, correct) trước target + skill target. Full history; reset state mỗi learner.")
    st.warning('Một split theo learner; test từng được tính trong các run cũ. Đây không phải holdout mới hoàn toàn. AUC giữa hai dataset không chứng minh chuyển miền hay cải thiện học tập.')
else:
    learners = events.groupby('learner').size().sort_values(ascending=False).index.tolist()
    learner = st.selectbox('Học viên test (giả danh hóa)',learners)
    student = events[events.learner == learner].sort_values('position')
    if len(student)<2:
        st.info('Học viên chỉ có context đầu, không có target để replay.')
        st.stop()
    pos = st.select_slider('Thời điểm tương tác được mở',options=student.position.tolist()[1:])
    past = student[student.position < pos]
    current = student[student.position == pos].iloc[0]
    cols = ['position','skill_id','correct']
    st.write('Lịch sử đã quan sát trước thời điểm chọn')
    st.dataframe(past[cols].rename(columns={'correct':'Kết quả đã quan sát'}),hide_index=True)
    if page == 'Student Replay':
        st.write(f"Target tại vị trí {pos} · skill {current.skill_id}")
        st.dataframe(pd.DataFrame([{'Mô hình':m,'P(correct) trước target':current[m],
                                     'Dự đoán @0.5':int(current[m]>=.5)} for m in predictions]),hide_index=True)
        st.write(f"Nhãn thực tế tại thời điểm đã chọn: **{int(current.correct)}**")
        st.caption('Tương tác đầu chỉ làm context. Không hiển thị nhãn ở các vị trí sau thời điểm đã chọn. So sánh mô hình đã join theo event ID và kiểm tra learner/nhãn.')
    else:
        observed = student[student.position <= pos]
        skill = st.selectbox('Kỹ năng trong phần lịch sử đã mở',sorted(observed.skill_id.unique(),key=str))
        selected = observed[(observed.skill_id == skill) & (observed.position > 0)]
        fig = go.Figure()
        for m in predictions:
            fig.add_trace(go.Scatter(x=selected.position,y=selected[m],mode='lines+markers',name=f'{m} P(correct) trước target'))
        fig.add_trace(go.Scatter(x=selected.position,y=selected.correct,mode='markers',name='Kết quả thực tế',marker=dict(symbol='x',size=13)))
        fig.update_layout(xaxis_title='Vị trí trong toàn lịch sử',yaxis_title='Xác suất / nhãn 0–1',yaxis_range=[-.05,1.05])
        st.plotly_chart(fig,width='stretch')
        st.dataframe(selected[['position','skill_id','DKT','BKT','Baseline','correct']],hide_index=True)
        st.caption('DKT sử dụng toàn bộ lịch sử đa kỹ năng trước target. P(correct) không phải mastery; nhãn 0/1 là kết quả quan sát. Event đầu không có next-step prediction.')
