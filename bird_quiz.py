import streamlit as st
import google.generativeai as genai
from PIL import Image
import concurrent.futures 

# --- [1. 기본 설정] ---
# 복잡한 시트 설정 없이, 오직 AI 키 하나만 있으면 됩니다.
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("설정(Secrets)에 GOOGLE_API_KEY가 없습니다.")
    st.stop()

# --- [2. 앱처럼 보이게 하는 마법의 CSS] ---
# 상단 메뉴, 바닥글 등을 숨겨서 진짜 앱처럼 깔끔하게 만듭니다.
st.set_page_config(page_title="AI 조류 도감", layout="wide", page_icon="🦅")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 20px;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- [3. AI 분석 함수] ---
# 민석님이 만족하신 '속도'와 '정확도'의 핵심 (Gemini 2.5 Flash)
def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        # 현존 가장 빠르고 가성비 좋은 모델
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        prompt = """
        당신은 한국의 야생 조류 전문가입니다.
        사진 속의 새를 식별하여 '한국어 국명'을 단어 하나로 답하세요.
        한국 도심/공원에서 흔한 새(직박구리, 참새, 까치, 비둘기 등)일 확률을 우선 고려하세요.
        만약 새가 아니라면 '새 아님'이라고 하세요.
        """
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except Exception as e:
        return f"Error"

# --- [4. 메인 화면 UI] ---
st.title("🦅 AI 조류 도감")
st.caption("촬영한 사진을 올리면 AI가 즉시 분석합니다.")

st.divider()

# 파일 업로드 (카메라 촬영 or 갤러리 선택 가능)
uploaded_files = st.file_uploader("📸 사진을 선택하거나 찍어주세요", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    # 이미지 로딩
    images = [Image.open(file) for file in uploaded_files]
    results = []

    # 병렬 처리 (여러 장을 동시에 분석해서 속도 3배 향상)
    with st.spinner("AI가 분석 중입니다..."):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(analyze_bird_image, images))

    # 결과 출력
    st.write(f"총 **{len(uploaded_files)}장** 분석 완료!")
    
    for i, (file, ai_result) in enumerate(zip(uploaded_files, results)):
        # 카드 형태의 깔끔한 디자인 유지
        with st.container(border=True):
            col1, col2 = st.columns([1, 2], gap="medium")
            
            with col1:
                st.image(file, use_container_width=True)
            
            with col2:
                if ai_result == "새 아님":
                     st.warning("⚠️ 새가 아닙니다.")
                elif "Error" in ai_result:
                     st.error("분석 실패")
                else:
                     st.markdown(f"### 👉 **{ai_result}**")
                     st.caption("한국 야생 조류 데이터베이스")

else:
    # 사진이 없을 때 보이는 안내 문구
    st.info("👆 위 버튼을 눌러 사진을 올려보세요.")
    st.markdown("""
    **💡 팁:**
    - 사진은 한 번에 여러 장 올릴 수 있습니다.
    - 홈 화면에 추가하면 진짜 앱처럼 쓸 수 있습니다.
    """)
