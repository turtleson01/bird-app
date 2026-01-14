import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image

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
        df = pd.read_csv("data.csv", skiprows=2, encoding='utf-8-sig')
        bird_data = df.iloc[:, [4, 14]].dropna()
        bird_data.columns = ['name', 'family_kor']
        bird_list = bird_data['name'].str.strip().tolist()
        bird_order_map = {name: i for i, name in enumerate(bird_list)}
        families = bird_data['family_kor'].str.strip().unique()
        family_group = {f: bird_data[bird_data['family_kor'] == f]['name'].str.strip().tolist() for f in families}
        return bird_list, bird_order_map, family_group
    except:
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

# --- 메인 화면 ---
st.set_page_config(page_title="AI 조류 도감", layout="wide", page_icon="🐦")
birds, bird_order_map, family_group = load_bird_data()

if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

if not st.session_state.user_name:
    st.title("🐦 AI 조류 도감")
    with st.form("login_form"):
        input_name = st.text_input("닉네임 (예: 민석)")
        if st.form_submit_button("시작하기"):
            st.session_state.user_name = input_name
            st.rerun()
    st.stop()

with st.sidebar:
    st.success(f"{st.session_state.user_name}님 로그인 중")
    if st.button("로그아웃"):
        st.session_state.user_name = ""
        st.rerun()

st.title("📸 AI 조류 도감")
my_birds = get_user_data(st.session_state.user_name)
found_count = len(my_birds)
st.info(f"현재 {found_count}종 발견!")

st.divider()

# --- AI 사진 기능 ---
uploaded_file = st.file_uploader("새 사진 업로드", type=["jpg", "png"])
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, width=300)
    
    if st.button("이 새 이름이 뭐야?"):
        with st.spinner("AI 분석 중..."):
            try:
                genai.configure(api_key=API_KEY)
                
                # [중요] 모델 이름을 여기서 바꿀 수 있게 변수로 뺐습니다.
                # 우선 가장 최신 모델로 시도
                model = genai.GenerativeModel('gemini-1.5-flash') 
                
                prompt = "이 새의 한국어 국명만 정확히 알려줘. 설명 없이 이름만."
                response = model.generate_content([prompt, image])
                st.success(f"결과: {response.text}")
                
                # (등록 로직 생략 - 에러 확인이 우선)
                
            except Exception as e:
                st.error(f"AI 에러: {e}")

st.divider()

# ==========================================
# 🛠️ [긴급 진단] 문제 해결용 버튼 (여기를 봐주세요!)
# ==========================================
with st.expander("🛠️ 시스템 진단 (에러가 계속 나면 눌러보세요)", expanded=True):
    if st.button("내 API로 쓸 수 있는 모델 목록 확인하기"):
        try:
            genai.configure(api_key=API_KEY)
            st.write(f"설치된 AI 도구 버전: {genai.__version__}")
            st.write("---")
            st.write("📋 사용 가능한 모델 목록:")
            
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    st.write(f"- `{m.name}`")
                    available_models.append(m.name)
            
            if not available_models:
                st.error("사용 가능한 모델이 하나도 없습니다! API Key 권한 문제일 수 있습니다.")
                
        except Exception as e:
            st.error(f"목록 불러오기 실패: {e}")
