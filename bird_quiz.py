import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
import concurrent.futures 
from datetime import datetime
import os

# --- [1. 기본 설정] ---
st.set_page_config(page_title="탐조 도감", layout="wide", page_icon="🦅")

# CSS: UI 깔끔하게 정리
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            
            /* 목록 아이템 스타일 */
            .bird-item {
                font-size: 1.05rem;
                padding: 8px 0;
                font-weight: 500;
            }
            hr { margin: 0.4rem 0 !important; }
            
            /* 탭 폰트 크기 조정 */
            button[data-baseweb="tab"] {
                font-size: 1rem !important;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [2. 데이터 및 족보 관리 함수] ---
@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    if not os.path.exists(file_path): return {}
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, skiprows=2, encoding=enc)
            bird_data = df.iloc[:, [4]].dropna() 
            bird_data.columns = ['name']
            bird_list = bird_data['name'].str.strip().tolist()
            return {name: i + 1 for i, name in enumerate(bird_list)}
        except: continue
    return {}

BIRD_MAP = load_bird_map()
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty: return pd.DataFrame(columns=['No', 'bird_name', 'date'])
        if BIRD_MAP and 'bird_name' in df.columns:
            df['real_no'] = df['bird_name'].apply(lambda x: BIRD_MAP.get(str(x).strip(), 9999))
            df = df.sort_values(by='real_no', ascending=True)
        return df
    except: return pd.DataFrame(columns=['No', 'bird_name', 'date'])

def save_data(bird_name):
    try:
        bird_name = bird_name.strip()
        df = get_data()
        if bird_name in df['bird_name'].values: return "이미 등록된 새입니다."
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name, 9999)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

def delete_birds(bird_names_to_delete):
    try:
        df = get_data()
        df = df[~df['bird_name'].isin(bird_names_to_delete)]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e: return str(e)

# --- [3. AI 분석 함수] ---
def analyze_bird_image(image, user_doubt=None):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = f"사용자 의심: {user_doubt}. " if user_doubt else ""
        prompt += "사진 속 새의 '한국어 국명'을 식별하고 그 이유를 짧게 설명하세요. 출력: 새이름 | 이유"
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except: return "Error | 분석 오류"

# --- [4. 메인 화면 구성] ---
st.title("🦅 탐조 도감")

df = get_data()

# 상단 요약 정보
st.markdown(f"""
    <div style="padding: 15px; border-radius: 12px; background-color: #e8f5e9; margin-bottom: 20px;">
        <span style="font-size: 1.0rem; color: #2e7d32; font-weight: bold;">🌱 총 발견한 새: {len(df)} 마리</span>
    </div>
""", unsafe_allow_html=True)

# 탭 구성: 직접 입력 - AI 분석 - 기록 관리
tab1, tab2, tab3 = st.tabs(["✍️ 직접 입력", "📸 AI 분석", "🛠️ 기록 관리"])

# --- 탭 1: 직접 입력 ---
with tab1:
    st.subheader("새 이름 직접 기록")
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            res = save_data(name)
            if res is True: 
                st.toast(f"✅ {name} 등록 완료!")
                st.session_state.input_bird = ""
            else: st.error(res)
    st.text_input("발견한 새 이름을 입력하세요", key="input_bird", on_change=add_manual, placeholder="예: 참새")

# --- 탭 2: AI 분석 ---
with tab2:
    st.subheader("사진으로 이름 찾기")
    uploaded_files = st.file_uploader("새 사진을 업로드하세요", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if 'ai_results' not in st.session_state: st.session_state.ai_results = {}
    if 'dismissed_files' not in st.session_state: st.session_state.dismissed_files = set()

    if uploaded_files:
        active_files = [f for f in uploaded_files if f.name not in st.session_state.dismissed_files]
        for file in active_files:
            if file.name not in st.session_state.ai_results:
                with st.spinner(f"{file.name} 분석 중..."):
                    st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file))
            
            raw = st.session_state.ai_results[file.name]
            bird_name, reason = raw.split("|") if "|" in raw else (raw, "분석 완료")
            
            with st.container(border=True):
                c_top1, c_top2 = st.columns([0.9, 0.1])
                if c_top2.button("❌", key=f"cls_{file.name}"):
                    st.session_state.dismissed_files.add(file.name); st.rerun()
                
                c1, c2 = st
