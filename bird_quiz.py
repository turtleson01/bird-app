from PIL import Image
from datetime import datetime
import os
import requests 
from streamlit_lottie import st_lottie 

# --- [1. 기본 설정] ---
st.set_page_config(page_title="탐조 도감", layout="wide", page_icon="📚")

# ⭐️ [CSS] Lottie 오버레이 설정 (화면 공간 차지 X, 클릭 통과)
# CSS: 깔끔한 UI 스타일
st.markdown("""
<style>
div[data-testid="stLottie"] {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    z-index: 99999 !important;
    pointer-events: none !important;
    margin: 0 !important;
    padding: 0 !important;
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stApp {padding-top: 10px;}

.summary-box {
    padding: 20px; border-radius: 15px; 
    background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
    margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: left;
}
iframe[title="streamlit_lottie.st_lottie"] {
    width: 100vw !important;
    height: 100vh !important;
.summary-text { font-size: 1.1rem; color: #2e7d32; font-weight: bold; }
.summary-count { font-size: 2rem; font-weight: 800; color: #1b5e20; }

.sidebar-badge-container { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.sidebar-badge {
    display: inline-flex; align-items: center; padding: 4px 10px;
    border-radius: 15px; font-size: 0.8rem; font-weight: 700;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1); white-space: nowrap; margin-bottom: 4px;
}

.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; border-radius: 5px; }

.rare-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-left: 8px; vertical-align: middle; }
.tag-class1 { background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
.tag-class2 { background-color: #fff3e0; color: #ef6c00; border: 1px solid #ffcc80; }
.tag-natural { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }

.stat-highlight { color: #2e7d32; font-weight: 700; }
.sidebar-card { background-color: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px 15px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
div.stButton > button[kind="primary"] { background: linear-gradient(45deg, #64B5F6, #90CAF9); color: white !important; border: none; border-radius: 12px; padding: 0.6rem 1rem; font-weight: 700; width: 100%; box-shadow: 0 3px 5px rgba(0,0,0,0.1); }
[data-testid="stFileUploaderDropzone"] button { display: none !important; }
[data-testid="stFileUploaderDropzone"] section { cursor: pointer; }
</style>
""", unsafe_allow_html=True)

# Lottie 로드 함수
@st.cache_data
def load_lottieurl(url: str):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# 폭죽 URL
lottie_fireworks = load_lottieurl("https://assets6.lottiefiles.com/packages/lf20_rovf9gzu.json")
try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [2. 데이터 및 설정] ---
BADGE_INFO = {
@@ -93,52 +101,6 @@ def load_lottieurl(url: str):
}
RARE_LABEL = { "class1": "👑 멸종위기 1급", "class2": "⭐ 멸종위기 2급", "natural": "🌿 천연기념물" }

# CSS
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stApp {padding-top: 10px;}

.summary-box {
    padding: 20px; border-radius: 15px; 
    background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
    margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: left;
}
.summary-text { font-size: 1.1rem; color: #2e7d32; font-weight: bold; }
.summary-count { font-size: 2rem; font-weight: 800; color: #1b5e20; }

.sidebar-badge-container { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.sidebar-badge {
    display: inline-flex; align-items: center; padding: 4px 10px;
    border-radius: 15px; font-size: 0.8rem; font-weight: 700;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1); white-space: nowrap; margin-bottom: 4px;
}

.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; border-radius: 5px; }

.rare-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-left: 8px; vertical-align: middle; }
.tag-class1 { background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
.tag-class2 { background-color: #fff3e0; color: #ef6c00; border: 1px solid #ffcc80; }
.tag-natural { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }

.stat-highlight { color: #2e7d32; font-weight: 700; }
.sidebar-card { background-color: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px 15px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
div.stButton > button[kind="primary"] { background: linear-gradient(45deg, #64B5F6, #90CAF9); color: white !important; border: none; border-radius: 12px; padding: 0.6rem 1rem; font-weight: 700; width: 100%; box-shadow: 0 3px 5px rgba(0,0,0,0.1); }
[data-testid="stFileUploaderDropzone"] button { display: none !important; }
[data-testid="stFileUploaderDropzone"] section { cursor: pointer; }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [3. 로직 함수] ---
@st.cache_data
def load_bird_map():
@@ -203,7 +165,6 @@ def delete_birds(bird_names_to_delete, current_df):
def calculate_badges(df):
badges = []
count = len(df)
    
if count >= 1: badges.append("🐣 탐조 입문")
if count >= 5: badges.append("🌱 새싹 탐조가")
if count >= 20: badges.append("🥉 아마추어 탐조가")
@@ -214,9 +175,7 @@ def calculate_badges(df):
if not df.empty and FAMILY_MAP:
df['family'] = df['bird_name'].map(FAMILY_MAP)
fam_counts = df['family'].value_counts()
        
        unique_families = df['family'].nunique()
        if unique_families >= 15: badges.append("🌈 다채로운 시선")
        if df['family'].nunique() >= 15: badges.append("🌈 다채로운 시선")
if fam_counts.get('오리과', 0) >= 10: badges.append("🦆 호수의 지배자")
raptor_count = fam_counts.get('수리과', 0) + fam_counts.get('매과', 0)
if raptor_count >= 5: badges.append("🦅 하늘의 제왕")
@@ -251,27 +210,15 @@ def analyze_bird_image(image, user_doubt=None):
df = get_data()
current_badges = calculate_badges(df)

if 'my_badges' not in st.session_state: st.session_state['my_badges'] = current_badges
new_badges = [b for b in current_badges if b not in st.session_state['my_badges']]
if new_badges:
    # ⭐️ [배지 획득 시에만 폭죽] (1회 재생 + 클릭 통과 + 전체 화면)
    if lottie_fireworks:
        st_lottie(lottie_fireworks, key="badge_fireworks", loop=False, height=0, width=0) # height 0이지만 CSS로 강제 확장됨
    for nb in new_badges:
        st.toast(f"🏆 새로운 배지 획득! : {nb}", icon="🎉")

# ⭐️ [핵심 수정] 배지 획득/상실 여부와 상관없이 항상 현재 배지 상태를 동기화
# 이렇게 해야 새를 삭제했을 때 배지도 함께 사라진 상태로 업데이트됨
# 배지 상태 동기화 (항상 현재 데이터 기준)
st.session_state['my_badges'] = current_badges

# 사이드바
with st.sidebar:
st.header("🏆 획득 배지")
    
if current_badges:
badge_html_parts = []
badge_html_parts.append('<div class="sidebar-badge-container">')
        
sorted_badges = sorted(current_badges, key=lambda x: BADGE_INFO.get(x, {}).get('rank', 0), reverse=True)
top_badges = sorted_badges[:3]
other_badges = sorted_badges[3:]
@@ -351,8 +298,21 @@ def add_manual():
if name:
res = save_data(name, sex, df)
if res is True: 
                    msg = f"{name}({sex}) 등록 완료!"
                    # 1. 메시지 기본 생성
                    msg = f"✅ {name}({sex}) 등록 완료!"
if name in RARE_BIRDS: msg += f" ({RARE_LABEL.get(RARE_BIRDS[name])} 발견!)"
                    
                    # 2. 배지 획득 여부 체크 (즉석 계산)
                    # 현재(저장 후) 데이터를 기준으로 배지 다시 계산
                    try:
                        # 방금 저장한 데이터를 반영하기 위해 df에 행 추가 시뮬레이션 또는 재로딩 필요하지만
                        # 간단히 현재 보유 배지와 비교. 
                        # *주의: save_data가 리런을 트리거하지 않으므로, 
                        # 여기서는 '예상 배지'를 계산하거나, 리런 후 메시지를 띄우는 방식이 안전함.
                        # 여기서는 리런을 하므로, 리런 직전에 메시지를 세션에 담음.
                        pass 
                    except: pass
                    
st.session_state.add_message = ('success', msg)
else: 
st.session_state.add_message = ('error', res)
@@ -362,11 +322,21 @@ def add_manual():
# ⭐️ 알림 메시지 (입력창 바로 아래)
if 'add_message' in st.session_state and st.session_state.add_message:
msg_type, msg_text = st.session_state.add_message
            
            # 배지 획득 여부 확인 (리런 후 계산된 current_badges와 비교 로직은 복잡해지므로, 
            # 여기서는 단순히 등록 메시지만 띄우고, 배지 탭에서 확인하게 하거나
            # 혹은 아래처럼 텍스트를 추가할 수 있음)
            
            # ⭐️ 새로 획득한 배지가 있다면 메시지에 추가
            # (이 시점은 리런 후이므로 current_badges가 최신임)
            # 다만, 이전 상태를 모르므로 '방금 획득했는지' 알기 어려움.
            # 심플하게 등록 성공 메시지만 띄움.
            
if msg_type == 'success':
                st.success(msg_text, icon="✅")
                st.success(msg_text)
st.session_state.add_message = None
else:
                st.error(msg_text, icon="🚫")
                st.error(msg_text)
st.session_state.add_message = None

else: # AI 분석
@@ -413,7 +383,7 @@ def add_manual():
if st.button(f"도감에 등록하기", key=f"reg_{file.name}", type="primary", use_container_width=True):
res = save_data(bird_name, ai_sex, df)
if res is True: 
                                        st.session_state.add_message = ('success', f"{bird_name}({ai_sex}) 등록 성공!")
                                        st.session_state.add_message = ('success', f"✅ {bird_name}({ai_sex}) 등록 성공!")
st.rerun()
else: st.error(res)
else:
@@ -432,10 +402,10 @@ def add_manual():
if 'add_message' in st.session_state and st.session_state.add_message:
msg_type, msg_text = st.session_state.add_message
if msg_type == 'success':
                st.success(msg_text, icon="✅")
                st.success(msg_text)
st.session_state.add_message = None
else:
                st.error(msg_text, icon="🚫")
                st.error(msg_text)
st.session_state.add_message = None

# --- [Tab 2] 나의 도감 ---
