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

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            /* 닫기 버튼 스타일 조정 */
            div[data-testid="stButton"] > button {
                border-radius: 8px;
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

# --- [2. 족보(data.csv) 로드] ---
@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    if not os.path.exists(file_path):
        return {}
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, skiprows=2, encoding=enc)
            bird_data = df.iloc[:, [4]].dropna() 
            bird_data.columns = ['name']
            bird_data['name'] = bird_data['name'].str.strip()
            bird_list = bird_data['name'].tolist()
            return {name: i + 1 for i, name in enumerate(bird_list)}
        except:
            continue
    return {}

BIRD_MAP = load_bird_map()

# --- [3. 구글 시트 연결 및 관리] ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty:
            return pd.DataFrame(columns=['No', 'bird_name', 'date'])
        
        if BIRD_MAP and 'bird_name' in df.columns:
            df['real_no'] = df['bird_name'].apply(lambda x: BIRD_MAP.get(str(x).strip(), 9999))
            df = df.sort_values(by='real_no', ascending=True)
            return df
        else:
            return df
    except:
        return pd.DataFrame(columns=['No', 'bird_name', 'date'])

def save_data(bird_name):
    try:
        bird_name = bird_name.strip()
        df = get_data()
        
        if 'bird_name' in df.columns and bird_name in df['bird_name'].values:
            return "이미 등록된 새입니다."

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name, 9999)
        
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e:
        return str(e)

# ⭐️ [추가된 기능] 데이터 삭제 함수
def delete_data(bird_name):
    try:
        df = get_data()
        # 해당 이름이 아닌 것만 남김 (필터링) -> 즉, 삭제
        df = df[df['bird_name'] != bird_name]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e:
        return str(e)

# --- [4. AI 분석 함수] ---
def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = "사진 속 새의 '한국어 국명'을 단어 하나로 답하시오. 새가 아니면 '새 아님'."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except:
        return "Error"

# --- [5. 메인 화면] ---
st.title("🦅 탐조 도감")

if not BIRD_MAP:
    st.error("⚠️ 'data.csv' 파일을 찾을 수 없습니다!")

df = get_data()
count = len(df)

# 통계 박스
st.markdown(f"""
    <div style="padding: 15px; border-radius: 12px; background-color: #e8f5e9; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <span style="font-size: 1.0rem; color: #2e7d32; font-weight: bold;">🌱 총 발견한 새</span><br>
        <span style="font-size: 2.2rem; font-weight: 800; color: #1b5e20; line-height: 1.2;">{count}</span>
        <span style="font-size: 1.2rem; font-weight: 600; color: #333;"> 마리</span>
    </div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["✍️ 직접 입력", "📸 AI 분석"])

# ------------------------------------------------
# 탭 1: 직접 입력
# ------------------------------------------------
with tab1:
    st.write("##### 📝 발견한 새 이름을 기록하세요")
    
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            res = save_data(name)
            if res is True:
                st.toast(f"✅ {name} 저장 완료!")
                st.session_state.input_bird = ""
            elif res == "이미 등록된 새입니다.":
                st.warning("이미 도감에 있는 새입니다.")
            else:
                st.error(f"저장 실패: {res}")

    st.text_input("새 이름 입력", key="input_bird", on_change=add_manual, placeholder="예: 참새")

# ------------------------------------------------
# 탭 2: AI 사진 분석
# ------------------------------------------------
with tab2:
    st.write("##### 📸 사진으로 새 이름 찾기")
    uploaded_files = st.file_uploader("", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    # 세션 상태 초기화
    if 'ai_results' not in st.session_state:
        st.session_state.ai_results = {}
    if 'last_saved_bird' not in st.session_state:
        st.session_state.last_saved_bird = None
    
    # ⭐️ 닫기 버튼 누른 파일들을 기억하는 장소
    if 'dismissed_files' not in st.session_state:
        st.session_state.dismissed_files = set()

    if uploaded_files:
        # 닫기 버튼 누른 건 목록에서 제외하고 처리
        active_files = [f for f in uploaded_files if f.name not in st.session_state.dismissed_files]
        
        # 새로운 파일 분석
        new_files = [f for f in active_files if f.name not in st.session_state.ai_results]
        
        if new_files:
            st.write(f"⚡️ **{len(new_files)}장** 분석 중...")
            images = [Image.open(f) for f in new_files]
            
            with st.spinner("AI가 분석 중..."):
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    new_results = list(executor.map(analyze_bird_image, images))
            
            for f, res in zip(new_files, new_results):
                st.session_state.ai_results[f.name] = res

        # 결과 보여주기 Loop
        if not active_files and uploaded_files:
            st.info("모든 사진을 닫았습니다. 다시 분석하려면 파일을 다시 올려주세요.")

        for file in active_files:
            result = st.session_state.ai_results.get(file.name, "Error")
            
            with st.container(border=True):
                # ⭐️ 상단: 닫기 버튼 (X) 배치 (오른쪽 끝)
                top_col1, top_col2 = st.columns([0.9, 0.1])
                with top_col2:
                    # X 버튼 누르면 dismissed 목록에 추가하고 새로고침
                    if st.button("❌", key=f"close_{file.name}", help="이 결과 닫기"):
                        st.session_state.dismissed_files.add(file.name)
                        st.rerun()

                c1, c2 = st.columns([1, 2])
                with c1: st.image(file, use_container_width=True)
                with c2:
                    if result == "새 아님" or "Error" in result:
                        st.error("새를 못 찾았어요.")
                    else:
                        bird_no = BIRD_MAP.get(result, "??")
                        st.markdown(f"### 👉 **{result}**")
                        st.caption(f"도감 번호: {bird_no}번")
                        
                        is_saved = result in df['bird_name'].values if 'bird_name' in df.columns else False
                        
                        if is_saved:
                            if st.session_state.last_saved_bird == result:
                                st.success("🎉 방금 등록되었습니다!")
                            else:
                                st.info("✅ 도감에 보관 중입니다")
                        else:
                            if st.button(f"➕ 저장하기", key=f"btn_{file.name}"):
                                res = save_data(result)
                                if res is True:
                                    st.session_state.last_saved_bird = result
                                    st.toast(f"🎉 {result} 저장 완료!")
                                    st.rerun()
                                else:
                                    st.error(f"저장 실패: {res}")

# --- [6. 하단: 전체 기록 보기] ---
st.divider()
with st.expander("📜 전체 기록 보기 (도감 번호순)", expanded=True):
    if not df.empty and 'bird_name' in df.columns:
        for index, row in df.iterrows():
            bird = row['bird_name']
            real_no = BIRD_MAP.get(bird, 9999)
            display_no = "??" if real_no == 9999 else real_no
            
            # ⭐️ 목록 옆에 삭제 버튼 추가 (레이아웃 나누기)
            col_txt, col_btn = st.columns([0.85, 0.15])
            
            with col_txt:
                st.markdown(f"**{display_no}. {bird}**")
            
            with col_btn:
                # 삭제 버튼 누르면 즉시 삭제
                if st.button("삭제", key=f"del_{index}_{bird}"):
                    res = delete_data(bird)
                    if res is True:
                        st.toast(f"🗑️ {bird} 삭제 완료!")
                        st.rerun()
                    else:
                        st.error("삭제 실패")
            
            st.divider() # 구분선 추가
            
    else:
        st.caption("아직 기록된 새가 없습니다.")
