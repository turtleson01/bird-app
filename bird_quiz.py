import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import os

# --- [1. 기본 설정] ---
st.set_page_config(page_title="나의 탐조 도감", layout="wide", page_icon="🦅")

# CSS: 디자인 업그레이드 (버튼 촌스러운 느낌 제거)
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            
            /* 요약 박스 디자인 */
            .summary-box {
                padding: 20px; 
                border-radius: 15px; 
                background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
                border-left: 6px solid #2e7d32;
                margin-bottom: 25px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }
            .summary-text { font-size: 1.1rem; color: #2e7d32; font-weight: bold; }
            .summary-count { font-size: 2rem; font-weight: 800; color: #1b5e20; }
            
            /* 목록 아이템 디자인 */
            .bird-item { 
                font-size: 1.1rem; 
                padding: 12px 5px; 
                font-weight: 500; 
                color: #333;
            }
            hr { margin: 0 !important; border-top: 1px solid #eee !important; }

            /* ⭐️ [NEW] 세련된 등록 버튼 디자인 */
            div.stButton > button[kind="primary"] {
                background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%); /* 모던한 딥블루 그라데이션 */
                color: white !important;
                border: none;
                border-radius: 12px;
                padding: 0.6rem 1rem;
                font-weight: 600;
                transition: all 0.3s ease;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                width: 100%;
            }
            div.stButton > button[kind="primary"]:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0,0,0,0.2);
            }
            div.stButton > button[kind="primary"]:active {
                transform: translateY(0);
            }

            /* 삭제 버튼 (빨간색 계열 유지하되 깔끔하게) */
            div.stButton > button[kind="secondary"] {
                background-color: white;
                color: #ff4b4b;
                border: 1px solid #ffcccc;
                border-radius: 8px;
                transition: 0.2s;
            }
            div.stButton > button[kind="secondary"]:hover {
                background-color: #fff5f5;
                border-color: #ff0000;
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
    bird_name = bird_name.strip()
    
    if bird_name not in BIRD_MAP:
        return f"⚠️ '{bird_name}'은(는) 족보(data.csv)에 없는 이름입니다."

    try:
        df = get_data()
        if bird_name in df['bird_name'].values: 
            return "이미 등록된 새입니다."
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: 
        return str(e)

def delete_birds(bird_names_to_delete):
    try:
        df = get_data()
        df = df[~df['bird_name'].isin(bird_names_to_delete)]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e: return str(e)

# --- [3. AI 분석 함수 (프롬프트 강화)] ---
def analyze_bird_image(image, user_doubt=None):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        # ⭐️ 프롬프트 대폭 수정: 새가 없으면 명확하게 '새 아님'이라고 뱉도록 지시
        system_instruction = """
        당신은 조류 전문가입니다. 사진을 분석하여 다음 규칙을 엄격히 따르세요:
        1. 사진에 '새'가 명확히 있다면: 한국어 국명(종명) | 식별 근거(1문장)
        2. 사진에 새가 없거나, 화면 캡처, 에러 메시지, 사람, 풍경 등이라면: 새 아님 | 새를 찾을 수 없습니다. (또는 사진에 대한 간단한 설명)
        3. 형식을 반드시 지키세요 (구분자는 수직선 | 사용). '새이름' 같은 모호한 단어 쓰지 마세요.
        """
        
        prompt = f"{system_instruction}"
        if user_doubt:
            prompt += f"\n사용자 의심/반론: '{user_doubt}'. 이를 참고하여 다시 신중하게 판단하세요."
            
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except: return "Error | 분석 오류"

# --- [4. 메인 화면 구성] ---
st.title("🦅 나의 탐조 도감")

df = get_data()

st.markdown(f"""
    <div class="summary-box">
        <span class="summary-text">🌱 현재까지 모은 도감</span><br>
        <span class="summary-count">{len(df)}</span>
        <span class="summary-text"> 마리</span>
    </div>
""", unsafe_allow_html=True)

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
            else:
                st.error(res)
    
    st.text_input("새 이름을 입력하세요", 
                  key="input_bird", 
                  on_change=add_manual, 
                  placeholder="예: 참새, 맷도요 등")

# --- 탭 2: AI 분석 ---
with tab2:
    st.subheader("사진으로 이름 찾기")
    uploaded_files = st.file_uploader("새 사진 업로드", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if 'ai_results' not in st.session_state: st.session_state.ai_results = {}
    if 'dismissed_files' not in st.session_state: st.session_state.dismissed_files = set()

    if uploaded_files:
        active_files = [f for f in uploaded_files if f.name not in st.session_state.dismissed_files]
        for file in active_files:
            if file.name not in st.session_state.ai_results:
                with st.spinner(f"🔍 {file.name} 분석 중..."):
                    st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file))
            
            raw = st.session_state.ai_results[file.name]
            
            # 파싱 로직
            if "|" in raw:
                parts = raw.split("|", 1)
                bird_name = parts[0].strip()
                reason = parts[1].strip()
            else:
                bird_name = raw.strip()
                reason = "결과 상세 내용을 불러오지 못했습니다."
            
            # ⭐️ '새 아님', 'Error' 등이 나오면 등록 불가 처리
            is_valid_bird = True
            if bird_name in ["새 아님", "Error", "판독 불가"] or "오류" in bird_name:
                is_valid_bird = False

            with st.container(border=True):
                # 닫기 버튼
                top_c1, top_c2 = st.columns([0.9, 0.1])
                if top_c2.button("✕", key=f"cls_{file.name}"):
                    st.session_state.dismissed_files.add(file.name); st.rerun()

                c1, c2 = st.columns([1, 1.5])
                with c1:
                    st.image(file, use_container_width=True)
                
                with c2:
                    if is_valid_bird:
                        st.markdown(f"### 🏷️ 이름: **{bird_name}**")
                        st.markdown(f"**🔍 판단 이유**")
                        st.info(reason) # 이유를 깔끔한 박스에
                        
                        # ⭐️ [등록하기] 버튼: 새가 맞을 때만 표시 + 세련된 디자인(primary)
                        if st.button(f"➕ 도감에 등록하기", key=f"reg_{file.name}", type="primary", use_container_width=True):
                            res = save_data(bird_name)
                            if res is True: 
                                st.balloons() # 성공 시 풍선 효과
                                st.toast(f"🎉 {bird_name} 등록 성공!")
                                st.rerun()
                            else:
                                st.error(res)
                    else:
                        # 새가 아닐 때
                        st.warning(f"⚠️ **{bird_name}**")
                        st.write(reason)
                        # 등록 버튼 아예 안 보여줌

                    st.divider()
                    
                    # 재분석 요청
                    st.caption("결과가 이상한가요?")
                    c_ask1, c_ask2 = st.columns([0.7, 0.3])
                    user_opinion = c_ask1.text_input("의견 (예: 이거 말똥가리 아냐?)", key=f"doubt_{file.name}", label_visibility="collapsed", placeholder="의견 입력...")
                    if c_ask2.button("재분석", key=f"ask_{file.name}", use_container_width=True):
                        if user_opinion:
                            with st.spinner("AI가 다시 생각하는 중..."):
                                st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file), user_opinion)
                                st.rerun()

# --- 탭 3: 기록 관리 (삭제) ---
with tab3:
    st.subheader("데이터 관리")
    if not df.empty:
        to_delete = st.multiselect("삭제할 기록 선택", options=df['bird_name'].tolist())
        if to_delete:
            if st.button(f"🗑️ 선택한 {len(to_delete)}개 삭제하기", type="primary"):
                if delete_birds(to_delete) is True:
                    st.success("삭제되었습니다.")
                    st.rerun()
    else:
        st.info("아직 등록된 기록이 없습니다.")

# --- [5. 하단: 나의 탐조 목록] ---
st.divider()
st.subheader("📜 나의 탐조 목록")
if not df.empty:
    for index, row in df.iterrows():
        bird = row['bird_name']
        real_no = BIRD_MAP.get(bird, 9999)
        display_no = "??" if real_no == 9999 else real_no
        
        # 디자인: 번호와 이름을 깔끔하게
        st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid #eee;">
            <span style="font-size:1.1rem; font-weight:600; color:#555;">No.{display_no}</span>
            <span style="font-size:1.2rem; font-weight:bold; color:#333;">{bird}</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.caption("기록이 없습니다.")
