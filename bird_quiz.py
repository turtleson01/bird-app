import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import os

# --- [1. 기본 설정] ---
st.set_page_config(page_title="탐조 도감 V2", layout="wide", page_icon="👾")

# --- [2. 레트로/픽셀 테마 CSS (둥근모 꼴 + NES 스타일)] ---
retro_style = """
<style>
/* 1. 폰트 불러오기 (둥근모) */
@import url('https://cdn.jsdelivr.net/gh/DungGeunMo/DungGeunMo/DungGeunMo.css');

/* 2. 전체 폰트 적용 */
html, body, [class*="css"] {
    font-family: 'DungGeunMo', sans-serif !important;
}

/* 3. 헤더/타이틀 스타일 */
h1, h2, h3 {
    color: #2c3e50;
    text-shadow: 2px 2px 0px #bdc3c7; /* 레트로 그림자 */
}

/* 4. 버튼 스타일 (각진 NES 스타일) */
div.stButton > button {
    border: 2px solid #000 !important;
    border-radius: 0px !important; /* 둥근 모서리 제거 */
    box-shadow: 4px 4px 0px 0px #000 !important; /* 거친 그림자 */
    background-color: #fff !important;
    color: #000 !important;
    font-weight: bold !important;
    transition: all 0.1s;
}
div.stButton > button:active {
    transform: translate(2px, 2px);
    box-shadow: 2px 2px 0px 0px #000 !important;
}
div.stButton > button:hover {
    background-color: #f1c40f !important; /* 호버 시 노란색 */
}

/* 5. 요약 박스 (레트로 보드판) */
.summary-box {
    border: 3px solid #2c3e50;
    background-color: #ecf0f1;
    padding: 20px;
    box-shadow: 6px 6px 0px #95a5a6;
    margin-bottom: 20px;
}
.summary-count { font-size: 2rem; color: #e67e22; }

/* 6. 도감 그리드 카드 (포켓몬 도감 스타일) */
.bird-card-collected {
    border: 2px solid #27ae60;
    background-color: #eafaf1;
    padding: 10px;
    text-align: center;
    box-shadow: 3px 3px 0px #2ecc71;
    height: 100%;
    margin-bottom: 10px;
}
.bird-card-missing {
    border: 2px solid #95a5a6;
    background-color: #dfe6e9;
    padding: 10px;
    text-align: center;
    box-shadow: 3px 3px 0px #b2bec3;
    color: #7f8c8d;
    height: 100%;
    opacity: 0.7;
    margin-bottom: 10px;
}
.pixel-icon { font-size: 2rem; }

/* 7. 배지 스타일 (알약 -> 각진 태그) */
.sidebar-badge {
    display: inline-block; padding: 4px 8px; 
    border: 2px solid #000; 
    font-size: 0.7rem; 
    box-shadow: 2px 2px 0px #000;
    margin: 3px; background: #fff;
}

/* 탭 스타일 */
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] { 
    border: 2px solid transparent; 
    border-radius: 0px;
    font-family: 'DungGeunMo';
}
.stTabs [aria-selected="true"] {
    border: 2px solid #000 !important;
    box-shadow: 3px 3px 0px #000;
    background-color: #fff;
}
</style>
"""
st.markdown(retro_style, unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [3. 데이터 로직] ---
# 배지 정보 (이름, 등급, 설명, 우선순위)
BADGE_INFO = {
    "🐣 탐조 입문": {"tier": "rare", "desc": "첫 번째 새 기록!", "rank": 1},
    "🌱 새싹 탐조가": {"tier": "rare", "desc": "5마리 발견", "rank": 1.5},
    "🥉 아마추어": {"tier": "rare", "desc": "20마리 수집", "rank": 2},
    "🥈 베테랑": {"tier": "epic", "desc": "50마리 수집", "rank": 3},
    "🥇 마스터": {"tier": "unique", "desc": "100마리 수집", "rank": 4},
    "💎 전설": {"tier": "legendary", "desc": "300마리 수집", "rank": 5},
    "🌈 다채로운 시선": {"tier": "unique", "desc": "15개 과 기록", "rank": 4},
    "🦆 호수의 지배자": {"tier": "epic", "desc": "오리과 10마리", "rank": 3},
    "🦅 하늘의 제왕": {"tier": "unique", "desc": "맹금류 5마리", "rank": 4},
    "🦉 밤의 추적자": {"tier": "unique", "desc": "올빼미과 발견", "rank": 4},
    "🍀 럭키 탐조가": {"tier": "unique", "desc": "멸종위기종 발견", "rank": 4},
}

TIER_STYLE = {
    "rare":      {"color": "#000", "bg": "#81ecec"},
    "epic":      {"color": "#000", "bg": "#a29bfe"},
    "unique":    {"color": "#000", "bg": "#ffeaa7"},
    "legendary": {"color": "#fff", "bg": "#00b894"},
}

RARE_BIRDS = { "황새": "class1", "수리부엉이": "class2", "원앙": "natural" } # (간소화)
RARE_LABEL = { "class1": "👑 1급", "class2": "⭐ 2급", "natural": "🌿 천연" }

@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    if not os.path.exists(file_path): return {}, {}, 0, {}
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, skiprows=2, header=None, encoding=enc)
            if df.shape[1] < 15: continue
            bird_data = df.iloc[:, [4, 14]].copy()
            bird_data.columns = ['name', 'family']
            bird_data = bird_data.dropna()
            bird_data['name'] = bird_data['name'].astype(str).str.strip()
            bird_data['family'] = bird_data['family'].astype(str).str.strip()
            
            # 필터링
            filter_keywords = ['대표국명', '국명', 'Name', 'Family', '과']
            bird_data = bird_data[~bird_data['family'].isin(filter_keywords)]
            
            name_to_family = dict(zip(bird_data['name'], bird_data['family']))
            
            # 과별 리스트 생성
            family_groups = {}
            for _, row in bird_data.iterrows():
                fam = row['family']
                name = row['name']
                if fam not in family_groups: family_groups[fam] = []
                family_groups[fam].append(name)
                
            return name_to_family, family_groups, len(bird_data)
        except Exception as e: continue
    return {}, {}, 0

BIRD_FAMILY_MAP, FAMILY_GROUPS, TOTAL_SPECIES_COUNT = load_bird_map()
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty: return pd.DataFrame(columns=['No', 'bird_name', 'sex', 'date'])
        return df
    except: return pd.DataFrame(columns=['No', 'bird_name', 'sex', 'date'])

def save_data(bird_name, sex, current_df):
    bird_name = bird_name.strip()
    if bird_name not in BIRD_FAMILY_MAP: return f"⚠️ 도감에 없는 새입니다."
    if not current_df.empty and bird_name in current_df['bird_name'].values: return "이미 등록된 새입니다."
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_row = pd.DataFrame({'No': [999], 'bird_name': [bird_name], 'sex': [sex], 'date': [now]})
        updated_df = pd.concat([current_df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

def delete_birds(bird_names_to_delete, current_df):
    try:
        df = current_df[~current_df['bird_name'].isin(bird_names_to_delete)]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except: return False

def calculate_badges(df):
    badges = []
    count = len(df)
    if count >= 1: badges.append("🐣 탐조 입문")
    if count >= 5: badges.append("🌱 새싹 탐조가")
    if count >= 20: badges.append("🥉 아마추어")
    if count >= 50: badges.append("🥈 베테랑")
    if count >= 100: badges.append("🥇 마스터")
    if count >= 300: badges.append("💎 전설")
    
    if not df.empty:
        df['family'] = df['bird_name'].map(BIRD_FAMILY_MAP)
        fam_counts = df['family'].value_counts()
        if df['family'].nunique() >= 15: badges.append("🌈 다채로운 시선")
        if fam_counts.get('오리과', 0) >= 10: badges.append("🦆 호수의 지배자")
        raptor = fam_counts.get('수리과', 0) + fam_counts.get('매과', 0)
        if raptor >= 5: badges.append("🦅 하늘의 제왕")
        if fam_counts.get('올빼미과', 0) >= 1: badges.append("🦉 밤의 추적자")
    
    # 레어 체크 (간소화)
    for name in df['bird_name']:
        if name in RARE_BIRDS: 
            badges.append("🍀 럭키 탐조가")
            break
    return list(set(badges)) # 중복제거

def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(["이 새의 한국어 종명만 정확히 알려줘. 설명 없이 이름만.", image])
        return response.text.strip()
    except: return "분석 실패"

# --- [4. 메인 화면] ---
st.title("👾 탐조 도감 V2")

df = get_data()
current_badges = calculate_badges(df)
collected_set = set(df['bird_name'].values)

# 배지 알림
if 'my_badges' not in st.session_state: st.session_state['my_badges'] = current_badges
new_badges = [b for b in current_badges if b not in st.session_state['my_badges']]
if new_badges:
    st.balloons()
    for nb in new_badges: st.toast(f"🏆 배지 획득! [{nb}]", icon="🎉")
    st.session_state['my_badges'] = current_badges

# 사이드바 (레트로 스타일)
with st.sidebar:
    st.header("🏆 획득 배지")
    if current_badges:
        html = '<div class="sidebar-badge-container">'
        for b in current_badges:
            tier = BADGE_INFO.get(b, {}).get('tier', 'rare')
            st_col = TIER_STYLE.get(tier, TIER_STYLE['rare'])
            html += f'<span class="sidebar-badge" style="background:{st_col["bg"]}; color:{st_col["color"]};">{b}</span>'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
    else: st.caption("아직 획득한 배지가 없습니다.")
    
    st.divider()
    st.header("📊 현재 스코어")
    st.metric("총 발견 수", f"{len(df)} 마리")

# 메인 요약 (레트로 박스)
progress = min((len(df) / TOTAL_SPECIES_COUNT) * 100, 100) if TOTAL_SPECIES_COUNT else 0
st.markdown(f"""
<div class="summary-box">
    <h3>🌱 도감 완성도</h3>
    <span class="summary-count">{len(df)}</span> / {TOTAL_SPECIES_COUNT} 종
    <div style="background:#bdc3c7; height:20px; width:100%; border:2px solid #000; margin-top:10px;">
        <div style="background:#2ecc71; height:100%; width:{progress}%;"></div>
    </div>
</div>
""", unsafe_allow_html=True)

# 탭 메뉴 (3개)
tab1, tab2, tab3 = st.tabs(["✍️ 종 추가", "▦ 도감 (Grid)", "🏆 배지 목록"])

# [Tab 1] 종 추가
with tab1:
    st.subheader("새로운 발견 기록")
    method = st.radio("입력 방식", ["📝 직접 입력", "📸 AI 분석"], horizontal=True)
    
    if method == "📝 직접 입력":
        with st.form("manual_add"):
            name = st.text_input("새 이름 (예: 참새)")
            sex = st.radio("성별", ["미구분", "수컷", "암컷"], horizontal=True)
            if st.form_submit_button("도감에 등록 (PRESS START)"):
                res = save_data(name, sex, df)
                if res is True: st.success("저장 완료!"); st.rerun()
                else: st.error(res)
    else:
        up_file = st.file_uploader("사진 업로드", type=["jpg","png"])
        if up_file:
            st.image(up_file, width=200)
            if st.button("AI 분석 시작"):
                with st.spinner("분석 중..."):
                    res = analyze_bird_image(Image.open(up_file))
                    st.success(f"결과: {res}")
                    # 여기서 바로 저장 버튼을 띄우거나 세션에 저장하여 처리 가능

# [Tab 2] 도감 그리드 (핵심 기능!)
with tab2:
    st.subheader("▦ 나의 도감")
    
    # 필터 (과별 보기) - 성능 최적화
    all_families = sorted(FAMILY_GROUPS.keys())
    selected_fam = st.selectbox("보고 싶은 '과(Family)'를 선택하세요", ["전체 보기"] + all_families)
    
    target_birds = []
    if selected_fam == "전체 보기":
        # 전체 보기는 너무 많으므로 수집한 것만 우선 보여주거나, 앞쪽 일부만 보여줌
        st.caption("전체 보기는 수집한 새 위주로 표시됩니다.")
        # 수집한 새 + 아직 못 모은 새 일부
        collected_list = df['bird_name'].tolist()
        target_birds = collected_list # 일단 수집한 것만
    else:
        target_birds = FAMILY_GROUPS[selected_fam]
    
    # 그리드 그리기 (3열)
    cols = st.columns(3)
    for i, bird in enumerate(target_birds):
        is_collected = bird in collected_set
        col = cols[i % 3]
        
        with col:
            if is_collected:
                # 수집된 상태 (컬러풀 + 테두리)
                st.markdown(f"""
                <div class="bird-card-collected">
                    <div class="pixel-icon">🐦</div>
                    <div style="font-weight:bold;">{bird}</div>
                    <div style="font-size:0.8rem; color:green;">GET!</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # 미수집 상태 (회색 + 물음표)
                st.markdown(f"""
                <div class="bird-card-missing">
                    <div class="pixel-icon">🥚</div>
                    <div style="font-weight:bold;">???</div>
                    <div style="font-size:0.8rem;">{bird}</div>
                </div>
                """, unsafe_allow_html=True)
                
    # 삭제 관리 (맨 아래 숨김)
    with st.expander("🛠️ 데이터 관리 (삭제)"):
        to_del = st.multiselect("삭제할 새", df['bird_name'].tolist())
        if st.button("삭제 실행"):
            delete_birds(to_del, df)
            st.rerun()

# [Tab 3] 배지 목록
with tab3:
    st.subheader("🏆 도전 과제")
    sorted_badges = sorted(BADGE_INFO.keys(), key=lambda x: BADGE_INFO[x]['rank'])
    
    for b in sorted_badges:
        earned = b in current_badges
        info = BADGE_INFO[b]
        icon = "✅" if earned else "🔒"
        style_color = "#2c3e50" if earned else "#95a5a6"
        
        st.markdown(f"""
        <div style="border:2px solid {style_color}; padding:10px; margin-bottom:10px; background:#fff; box-shadow: 4px 4px 0px {style_color}; color:{style_color};">
            <h4 style="margin:0;">{icon} {b}</h4>
            <p style="margin:0; font-size:0.9rem;">{info['desc']}</p>
        </div>
        """, unsafe_allow_html=True)
