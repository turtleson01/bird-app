import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
import concurrent.futures # 병렬 처리를 위한 도구

# --- [설정] ---
try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("Secrets 설정 오류: API Key나 시트 주소가 없습니다.")
    st.stop()

# --- 데이터 로드 ---
@st.cache_data
def load_bird_data():
    try:
        try:
            df = pd.read_csv("data.csv", skiprows=2, encoding='utf-8-sig')
        except:
            df = pd.read_csv("data.csv", skiprows=2, encoding='cp949')

        bird_data = df.iloc[:, [4, 14]].dropna()
        bird_data.columns = ['name', 'family_kor']
        
        bird_list = bird_data['name'].astype(str).str.strip().tolist()
        bird_order_map = {name: i for i, name in enumerate(bird_list)}
        families = bird_data['family_kor'].astype(str).str.strip().unique()
        family_group = {f: bird_data[bird_data['family_kor'] == f]['name'].str.strip().tolist() for f in families}
        
        return bird_list, bird_order_map, family_group
    except Exception as e:
        return [], {}, {}

conn = st.connection("gsheets", type=GSheetsConnection)

def get_user_data(user_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not df.empty and 'user_name' in df.columns:
            return df[df['user_name'] == user_name]['bird_name'].tolist()
        return []
    except:
        return []

def add_bird_to_sheet(user_name, bird_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        new_row = pd.DataFrame({'user_name': [user_name], 'bird_name': [bird_name]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except:
        return False

# ⭐️ AI 분석 함수 (Flash 모델로 변경하여 속도/안정성 확보)
def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        
        # [변경] 1.5 Pro 대신 'gemini-1.5-flash' 사용
        # 이유: 404 에러 방지 + 속도가 훨씬 빠름 + 조류 식별에 충분한 성능
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        prompt = """
        당신은 한국의 야생 조류 전문가입니다.
        사진 속의 새를 식별하여 '한국어 국명'을 단어 하나로 답하세요.
        한국 도심/공원에서 흔한 새(직박구리, 참새, 까치 등)일 확률을 우선 고려하세요.
        만약 새가 아니라면 '새 아님'이라고 하세요.
        """
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

# --- 메인 화면 시작 ---
st.set_page_config(page_title="AI 조류 도감", layout="wide", page_icon="🐦")
birds, bird_order_map, family_group = load_bird_data()

# 임시 저장소
if 'local_updates' not in st.session_state:
    st.session_state.local_updates = []

# 로그인 화면
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

with st.sidebar:
    st.header("👤 사용자 설정")
    with st.form("login_sidebar"):
        input_name = st.text_input("닉네임", value=st.session_state.user_name)
        if st.form_submit_button("로그인"):
            st.session_state.user_name = input_name
            st.session_state.local_updates = [] 
            st.rerun()
    
    if st.session_state.user_name:
        st.success(f"✅ {st.session_state.user_name}님 기록 중")

if not st.session_state.user_name:
    st.info("👈 닉네임을 먼저 입력해주세요.")
    st.stop()

st.title("📸 AI 조류 도감")

# 통계 계산
db_birds = get_user_data(st.session_state.user_name)
my_birds = list(set(db_birds + st.session_state.local_updates))
found_count = len(my_birds)

st.markdown(f"""
    <div style="padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;">
        <span style="font-size: 1.1rem; color: #555;">{st.session_state.user_name}님의 도감</span><br>
        <span style="font-size: 2.0rem; font-weight: 800; color: #007BFF; line-height: 1;">{found_count}</span>
        <span style="font-size: 1.2rem; font-weight: 600; color: #333;"> 종 발견</span>
    </div>
""", unsafe_allow_html=True)

# 1. 직접 기록하기
st.subheader("✍️ 직접 기록하기")

def handle_input():
    val = st.session_state.bird_input.strip()
    if val in birds:
        if val not in my_birds:
            add_bird_to_sheet(st.session_state.user_name, val)
            st.session_state.local_updates.append(val)
            st.toast(f"✅ {val} 저장 완료!")
        else:
            st.warning(f"'{val}'는 이미 있어요.")
    elif val:
        st.error(f"'{val}'... 목록에 없어요.")
    st.session_state.bird_input = ""

st.text_input("새 이름을 입력하세요", key="bird_input", on_change=handle_input)

st.divider()

# ==========================================
# 2. [병렬 처리 모드] 멘트 수정 + 속도 개선
# ==========================================
st.subheader("🤖 AI에게 물어보기")

uploaded_files = st.file_uploader("사진을 여러 장 선택해도 됩니다", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"📂 총 **{len(uploaded_files)}장**의 사진을 분석합니다.")
    
    images = [Image.open(file) for file in uploaded_files]
    results = []

    # ⭐️ [멘트 수정] 아주 심플하게!
    with st.spinner("분석 중..."):
        # 병렬 처리 (여러 장 동시 분석)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # 순서 보장을 위해 map 사용
            results = list(executor.map(analyze_bird_image, images))

    # 결과 출력
    for i, (file, ai_result) in enumerate(zip(uploaded_files, results)):
        with st.container(border=True):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(file, use_container_width=True)
            
            with col2:
                # 결과 헤더
                st.subheader(f"👉 {ai_result}")
                
                # 에러 처리
                if "Error" in ai_result:
                    st.error(f"오류: {ai_result}")
                elif ai_result == "새 아님":
                    st.error("새를 찾을 수 없습니다.")
                else:
                    if ai_result in birds:
                        if ai_result in my_birds:
                            st.info("👋 이미 도감에 등록된 친구입니다.")
                        else:
                            st.success("🎉 새로운 종 추가! (등록해주세요)")
                            
                            unique_key = f"btn_{i}_{file.name}"
                            if st.button(f"➕ '{ai_result}' 도감에 넣기", key=unique_key):
                                add_bird_to_sheet(st.session_state.user_name, ai_result)
                                st.session_state.local_updates.append(ai_result)
                                st.toast(f"{ai_result} 저장 완료!")
                                st.rerun()
                    else:
                        st.error(f"⚠️ '{ai_result}'은(는) 도감 목록에 없는 새입니다. (등록 불가)")

st.divider()

with st.expander("📜 전체 기록 보기"):
    st.write(f"총 {len(my_birds)}마리 발견")
    st.write(my_birds)
