import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
import concurrent.futures 
from datetime import datetime
import os

# --- [1. 기본 설정] ---
st.set_page_config(page_title="나의 탐조 도감", layout="wide", page_icon="🦅")

# CSS: 깔끔한 목록 디자인
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            
            /* 목록 텍스트 정렬 */
            .bird-item {
                padding: 10px 5px;
                border-bottom: 1px solid #f0f0f0;
                font-size: 1.05rem;
                font-weight: 500;
            }
            
            /* 삭제 버튼 전용 스타일 */
            .stButton > button[kind="secondary"] {
                color: #ff4b4b !important;
                border-color: #ffcccc !important;
                width: 100%;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정(SHEET_URL, API_KEY)이 필요합니다.")
    st.stop()

# --- [2. 데이터 관리 함수] ---
@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    if not os.path.exists(file_path): return {}
    for enc in ['utf-8-sig', 'cp949', 'euc-kr']:
        try:
            df = pd.read_csv(file_path, skiprows=2, encoding=enc)
            bird_data = df.iloc[:, [4]].dropna() 
            bird_data.columns = ['name']
            return {name.strip(): i + 1 for i, name in enumerate(bird_data['name'].tolist())}
        except: continue
    return {}

BIRD_MAP = load_bird_map()
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty: return pd.DataFrame(columns=['No', 'bird_name', 'date'])
        if 'bird_name' in df.columns:
            df['real_no'] = df['bird_name'].apply(lambda x: BIRD_MAP.get(str(x).strip(), 9999))
            df = df.sort_values(by='real_no', ascending=True)
        return df
    except: return pd.DataFrame(columns=['No', 'bird_name', 'date'])

def save_data(bird_name):
    try:
        bird_name = bird_name.strip()
        df = get_data()
        if bird_name in df['bird_name'].values: return "이미 등록됨"
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name, 9999)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

def delete_data(bird_name):
    try:
        df = get_data()
        df = df[df['bird_name'] != bird_name]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e: return str(e)

# --- [3. AI 분석 함수] ---
def analyze_bird_image(image, user_doubt=None):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = f"사용자 의견: {user_doubt}. " if user_doubt else ""
        prompt += "사진 속 새의 한국어 이름(국명)을 찾고 짧은 이유를 쓰세요. 형식: 이름 | 이유"
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except: return "에러 | 분석 중 오류가 발생했습니다."

# --- [4. 메인 화면 구성] ---
st.title("📸 나의 탐조 도감")

df = get_data()
st.info(f"🌱 현재 총 **{len(df)}종**의 새를 기록했습니다.")

# 탭 구성: 삭제 버튼은 '기록 관리' 탭으로 분리
tab1, tab2, tab3 = st.tabs(["✍️ 직접 입력", "📸 AI 분석", "🛠️ 기록 관리"])

# --- 탭 1: 직접 입력 ---
with tab1:
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            res = save_data(name)
            if res is True: st.toast(f"✅ {name} 등록 완료!"); st.session_state.input_bird = ""
            else: st.warning(f"이미 등록된 새입니다: {name}")
    st.text_input("발견한 새 이름을 입력하세요", key="input_bird", on_change=add_manual)

# --- 탭 2: AI 사진 분석 ---
with tab2:
    uploaded_files = st.file_uploader("새 사진 업로드", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    if 'ai_results' not in st.session_state: st.session_state.ai_results = {}
    if 'dismissed_files' not in st.session_state: st.session_state.dismissed_files = set()

    if uploaded_files:
        active_files = [f for f in uploaded_files if f.name not in st.session_state.dismissed_files]
        for file in active_files:
            if file.name not in st.session_state.ai_results:
                with st.spinner(f"{file.name} 분석 중..."):
                    st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file))
            
            raw = st.session_state.ai_results[file.name]
            # 안전한 파싱 (ValueError 방지)
            parts = raw.split("|")
            bird_name = parts[0].strip()
            reason = parts[1].strip() if len(parts) > 1 else "분석이 완료되었습니다."
            
            with st.container(border=True):
                c_top1, c_top2 = st.columns([0.9, 0.1])
                if c_top2.button("❌", key=f"cls_{file.name}"):
                    st.session_state.dismissed_files.add(file.name); st.rerun()
                
                c1, c2 = st.columns([1, 2])
                c1.image(file, use_container_width=True)
                c2.markdown(f"### {bird_name}")
                c2.caption(reason)
                if c2.button("➕ 등록하기", key=f"reg_{file.name}"):
                    if save_data(bird_name) is True: st.toast(f"✅ {bird_name} 등록 완료!"); st.rerun()

# --- 탭 3: 기록 관리 (삭제 전용) ---
with tab3:
    st.write("##### 🗑️ 등록된 기록 삭제")
    if not df.empty:
        for index, row in df.iterrows():
            bird = row['bird_name']
            c1, c2 = st.columns([0.7, 0.3])
            c1.write(f"**{bird}**")
            if c2.button("삭제", key=f"del_tab_{index}"):
                if delete_data(bird) is True: st.toast(f"🗑️ {bird} 삭제됨"); st.rerun()
    else:
        st.caption("기록이 없습니다.")

# --- [5. 하단 전체 기록 보기 (삭제 버튼 없음)] ---
st.divider()
with st.expander("📜 전체 기록 목록", expanded=True):
    if not df.empty:
        for index, row in df.iterrows():
            bird = row['bird_name']
            real_no = BIRD_MAP.get(bird, 9999)
            display_no = "??" if real_no == 9999 else real_no
            
            # 메인 목록은 텍스트만 깔끔하게 표시
            st.markdown(f"<div class='bird-item'>{display_no}. {bird}</div>", unsafe_allow_html=True)
    else:
        st.caption("아직 기록된 새가 없습니다.")
