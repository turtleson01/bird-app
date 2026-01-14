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

# CSS: 여백 줄이기 및 버튼 디자인 조정
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            
            /* 목록의 버튼과 텍스트 높이 맞추기 */
            div[data-testid="stHorizontalBlock"] {
                align-items: center;
            }
            /* 삭제 버튼 빨갛게 */
            button[kind="secondary"] {
                border-color: #ffcccc;
                color: #ff4b4b;
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

# --- [3. 구글 시트 관리] ---
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

def delete_data(bird_name):
    try:
        df = get_data()
        df = df[df['bird_name'] != bird_name]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e:
        return str(e)

# --- [4. AI 분석 함수 (업그레이드됨)] ---
def analyze_bird_image(image, user_doubt=None):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        if user_doubt:
            # 사용자가 반론을 제기했을 때의 프롬프트
            prompt = f"""
            사용자는 이 사진이 '{user_doubt}'일 것이라고 생각합니다.
            당신의 이전 판단과 사용자의 의견을 비교해서 다시 분석하세요.
            
            출력 형식:
            새이름 | 판단 이유 (한 문장으로 간략하게)
            
            예시 1: 말똥가리 | 꼬리 깃의 패턴과 날개 모양이 말똥가리의 특징과 일치합니다.
            예시 2: 흰꼬리수리 | 사용자의 의견도 일리 있지만, 부리의 노란색이 더 선명하여 흰꼬리수리가 맞습니다.
            """
        else:
            # 기본 분석 프롬프트
            prompt = """
            사진 속 새의 '한국어 국명'을 정확히 식별하고, 그 이유를 짧게 설명하세요.
            새가 아니면 '새 아님'이라고 하세요.
            
            출력 형식:
            새이름 | 판단 이유 (한 문장으로 간략하게)
            
            예시: 직박구리 | 뺨의 갈색 얼룩과 회색 몸통이 직박구리의 전형적인 특징입니다.
            """
            
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except:
        return "Error | 분석 중 오류 발생"

# --- [5. 메인 화면] ---
st.title("🦅 탐조 도감")

if not BIRD_MAP:
    st.error("⚠️ 'data.csv' 파일 없음")

df = get_data()
count = len(df)

# 통계 박스
st.markdown(f"""
    <div style="padding: 15px; border-radius: 12px; background-color: #e8f5e9; margin-bottom: 20px;">
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
    st.write("##### 📝 발견한 새 이름 기록")
    
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            res = save_data(name)
            if res is True:
                st.toast(f"✅ {name} 저장 완료!")
                st.session_state.input_bird = ""
            elif res == "이미 등록된 새입니다.":
                st.warning("이미 도감에 있습니다.")
            else:
                st.error(f"저장 실패: {res}")

    st.text_input("새 이름 입력", key="input_bird", on_change=add_manual, placeholder="예: 참새")

# ------------------------------------------------
# 탭 2: AI 사진 분석
# ------------------------------------------------
with tab2:
    st.write("##### 📸 사진으로 새 이름 찾기")
    uploaded_files = st.file_uploader("", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    if 'ai_results' not in st.session_state:
        st.session_state.ai_results = {} # {파일명: "이름 | 이유"}
    if 'dismissed_files' not in st.session_state:
        st.session_state.dismissed_files = set()

    if uploaded_files:
        active_files = [f for f in uploaded_files if f.name not in st.session_state.dismissed_files]
        new_files = [f for f in active_files if f.name not in st.session_state.ai_results]
        
        if new_files:
            st.write(f"⚡️ **{len(new_files)}장** 분석 중...")
            images = [Image.open(f) for f in new_files]
            
            with st.spinner("AI가 분석 중..."):
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # 람다 함수로 이미지 인자만 전달
                    new_results = list(executor.map(lambda img: analyze_bird_image(img), images))
            
            for f, res in zip(new_files, new_results):
                st.session_state.ai_results[f.name] = res

        if not active_files and uploaded_files:
            st.info("모든 사진을 닫았습니다.")

        for file in active_files:
            raw_result = st.session_state.ai_results.get(file.name, "Error | 오류")
            
            # 결과 파싱 ("이름 | 이유" 분리)
            if "|" in raw_result:
                bird_name, reason = raw_result.split("|", 1)
                bird_name = bird_name.strip()
                reason = reason.strip()
            else:
                bird_name = raw_result
                reason = "이유를 불러오지 못했습니다."

            with st.container(border=True):
                # 상단: 닫기 버튼
                top_col1, top_col2 = st.columns([0.95, 0.05])
                with top_col2:
                    if st.button("❌", key=f"close_{file.name}"):
                        st.session_state.dismissed_files.add(file.name)
                        st.rerun()

                c1, c2 = st.columns([1, 2])
                with c1: st.image(file, use_container_width=True)
                with c2:
                    if "새 아님" in bird_name or "Error" in bird_name:
                        st.error("새를 찾지 못했습니다.")
                    else:
                        bird_no = BIRD_MAP.get(bird_name, "??")
                        st.markdown(f"### 👉 **{bird_name}**")
                        st.caption(f"No.{bird_no} | 💡 {reason}")
                        
                        # 저장 상태 확인
                        is_saved = bird_name in df['bird_name'].values if 'bird_name' in df.columns else False
                        
                        if is_saved:
                            st.info("✅ 도감에 보관 중")
                        else:
                            if st.button(f"➕ 저장하기", key=f"btn_{file.name}"):
                                res = save_data(bird_name)
                                if res is True:
                                    st.toast(f"🎉 {bird_name} 저장 완료!")
                                    st.rerun()
                                else:
                                    st.error(f"실패: {res}")
                        
                        # --- 💬 AI와 토론하기 (반론 제기) ---
                        with st.expander("🤔 다른 새 같은가요? (재분석 요청)"):
                            def retry_analysis(f_name, img_file):
                                user_input = st.session_state[f"doubt_{f_name}"]
                                if user_input:
                                    with st.spinner(f"AI가 '{user_input}' 의견을 검토 중..."):
                                        img = Image.open(img_file)
                                        # 유저 의견을 넣어서 재분석
                                        new_res = analyze_bird_image(img, user_doubt=user_input)
                                        st.session_state.ai_results[f_name] = new_res
                                        st.rerun() # 결과 갱신

                            st.text_input("어떤 새라고 생각하시나요?", key=f"doubt_{file.name}")
                            st.button("AI에게 다시 물어보기", key=f"ask_{file.name}", 
                                      on_click=retry_analysis, args=(file.name, file))

# --- [6. 하단: 전체 기록 보기] ---
st.divider()
with st.expander("📜 전체 기록 보기", expanded=True): # 제목 수정됨
    if not df.empty and 'bird_name' in df.columns:
        for index, row in df.iterrows():
            bird = row['bird_name']
            real_no = BIRD_MAP.get(bird, 9999)
            display_no = "??" if real_no == 9999 else real_no
            
            # ⭐️ 목록 디자인 압축 (여백 최소화)
            col_txt, col_btn = st.columns([0.8, 0.2]) # 버튼 공간 확보
            
            with col_txt:
                # 수직 중앙 정렬 느낌을 위해 마크다운 조정
                st.markdown(f"<div style='padding-top: 5px;'><b>{display_no}. {bird}</b></div>", unsafe_allow_html=True)
            
            with col_btn:
                # 버튼을 오른쪽 끝으로 밀기 위한 빈 공간 대신 비율 조정 사용
                if st.button("삭제", key=f"del_{index}_{bird}"):
                    res = delete_data(bird)
                    if res is True:
                        st.toast(f"🗑️ {bird} 삭제됨")
                        st.rerun()
            
            # 구분선 대신 아주 얇은 여백으로 대체 (Divider 삭제)
            st.markdown("<hr style='margin: 5px 0; border: none; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)
            
    else:
        st.caption("아직 기록된 새가 없습니다.")
