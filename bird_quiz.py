import streamlit as st
import google.generativeai as genai
from PIL import Image
import concurrent.futures 

# --- [1. 설정 & 디자인] ---
st.set_page_config(page_title="나만의 탐조 도감", layout="wide", page_icon="🦅")

# 진짜 앱처럼 보이게 하는 CSS
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# API 키 확인
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("설정(Secrets)에 GOOGLE_API_KEY가 없습니다.")
    st.stop()

# --- [2. 임시 저장소 (세션)] ---
# 구글 시트 대신, 앱이 켜져있는 동안만 기억하는 메모리입니다.
if 'collected_birds' not in st.session_state:
    st.session_state.collected_birds = []

# --- [3. AI 분석 함수 (2.5 Flash)] ---
def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = "사진 속 새의 '한국어 국명'을 단어 하나로 답하시오. 새가 아니면 '새 아님'."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except:
        return "Error"

# --- [4. 메인 화면] ---
st.title("🦅 나만의 탐조 도감")

# 📊 통계 박스 (디자인 복구)
count = len(st.session_state.collected_birds)
st.markdown(f"""
    <div style="padding: 15px; border-radius: 12px; background-color: #e8f5e9; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <span style="font-size: 1.0rem; color: #2e7d32; font-weight: bold;">🌱 현재 채집한 새</span><br>
        <span style="font-size: 2.2rem; font-weight: 800; color: #1b5e20; line-height: 1.2;">{count}</span>
        <span style="font-size: 1.2rem; font-weight: 600; color: #333;"> 마리</span>
    </div>
""", unsafe_allow_html=True)

# 탭으로 기능 분리 (깔끔하게)
tab1, tab2 = st.tabs(["✍️ 직접 입력", "📸 AI 분석"])

# ------------------------------------------------
# 탭 1: 직접 입력 기능 (복구됨!)
# ------------------------------------------------
with tab1:
    st.write("##### 발견한 새 이름을 직접 기록하세요")
    
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            if name not in st.session_state.collected_birds:
                st.session_state.collected_birds.append(name)
                st.toast(f"✅ {name} 추가 완료!")
            else:
                st.warning("이미 목록에 있는 새입니다.")
        st.session_state.input_bird = "" # 입력창 비우기

    st.text_input("새 이름 입력", key="input_bird", on_change=add_manual, placeholder="예: 참새, 까치")
    st.caption("엔터를 치면 바로 추가됩니다.")

# ------------------------------------------------
# 탭 2: AI 사진 분석
# ------------------------------------------------
with tab2:
    st.write("##### 사진을 올리면 AI가 이름을 찾아줍니다")
    uploaded_files = st.file_uploader("", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    if uploaded_files:
        st.write(f"⚡️ **{len(uploaded_files)}장** 분석 중...")
        
        images = [Image.open(file) for file in uploaded_files]
        results = []

        with st.spinner("AI가 눈을 부릅뜨고 찾는 중..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(analyze_bird_image, images))

        for file, result in zip(uploaded_files, results):
            with st.container(border=True):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(file, use_container_width=True)
                with c2:
                    if result == "새 아님" or "Error" in result:
                        st.error("새를 못 찾았어요.")
                    else:
                        st.markdown(f"### 👉 **{result}**")
                        
                        # 도감 추가 버튼
                        if result not in st.session_state.collected_birds:
                            if st.button(f"➕ 도감에 넣기", key=f"btn_{file.name}"):
                                st.session_state.collected_birds.append(result)
                                st.toast(f"🎉 {result} 획득!")
                                st.rerun()
                        else:
                            st.info("✅ 이미 도감에 있습니다.")

# --- [5. 하단: 내 도감 리스트] ---
st.divider()
with st.expander("📜 나의 도감 목록 보기", expanded=True):
    if st.session_state.collected_birds:
        # 예쁜 뱃지 스타일로 보여주기
        st.markdown(" ".join([f"`{bird}`" for bird in st.session_state.collected_birds]), unsafe_allow_html=True)
    else:
        st.write("아직 발견한 새가 없습니다. 밖으로 나가보세요! 🔭")
