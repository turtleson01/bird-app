import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import os
import time

# --- [1. 기본 설정] ---
st.set_page_config(page_title="탐조 도감", layout="wide", page_icon="📚")

# CSS: 깔끔한 UI 스타일 + 사이드바 가독성 개선
st.markdown("""
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

div.stButton > button[kind="primary"] { background: linear-gradient(45deg, #64B5F6, #90CAF9); color: white !important; border: none; border-radius: 12px; padding: 0.6rem 1rem; font-weight: 700; width: 100%; box-shadow: 0 3px 5px rgba(0,0,0,0.1); }
[data-testid="stFileUploaderDropzone"] button { display: none !important; }
[data-testid="stFileUploaderDropzone"] section { cursor: pointer; }

/* 사이드바 Expander 스타일 개선 */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background-color: white !important;
    border-radius: 8px !important;
    border: 1px solid #e0e0e0 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    margin-bottom: 8px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #333 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.9rem !important;
    color: #555 !important;
}
</style>
""", unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [2. 데이터 및 설정] ---
ACHIEVEMENT_INFO = {
    "🐣 탐조 입문": {"tier": "rare", "desc": "첫 번째 새를 기록했습니다! 시작이 반입니다.", "rank": 1},
    "🌱 새싹 탐조가": {"tier": "rare", "desc": "5마리의 새를 만났습니다.", "rank": 1.5},
    "🥉 아마추어 탐조가": {"tier": "rare", "desc": "20마리 수집! 동네 새들은 다 꿰뚫고 계시군요.", "rank": 2},
    "🥈 베테랑 탐조가": {"tier": "epic", "desc": "50마리 수집! 어디 가서 '새 좀 안다'고 하셔도 됩니다.", "rank": 3},
    "🥇 마스터 탐조가": {"tier": "unique", "desc": "100마리 수집! 진정한 고수의 반열에 올랐습니다.", "rank": 4},
    "💎 전설의 탐조가": {"tier": "legendary", "desc": "300마리 수집! 당신은 살아있는 도감 그 자체입니다.", "rank": 5},
    
    "🌈 다채로운 시선": {"tier": "unique", "desc": "15개 이상의 서로 다른 '과(Family)'를 기록했습니다. 편식 없는 탐조!", "rank": 4},
    "🦆 호수의 지배자": {"tier": "epic", "desc": "오리과 10마리 이상 수집", "rank": 3},
    "🦅 하늘의 제왕": {"tier": "unique", "desc": "맹금류(수리과/매과) 5마리 이상 수집.", "rank": 4},
    "🦢 우아한 백로": {"tier": "epic", "desc": "백로/왜가리과 5마리 이상 수집", "rank": 3},
    "🌲 숲속의 드러머": {"tier": "epic", "desc": "딱따구리과 3마리 이상 수집", "rank": 3},
    "🦉 밤의 추적자": {"tier": "unique", "desc": "올빼미과(부엉이 등) 발견. 밤의 제왕을 만났습니다.", "rank": 4},
    "🧠 똑똑한 새": {"tier": "rare", "desc": "까마귀과(까치, 어치 등) 3마리 이상 수집", "rank": 2},
    "👔 넥타이 신사": {"tier": "rare", "desc": "박새과 3마리 이상 수집", "rank": 2},
    "🏖️ 갯벌의 나그네": {"tier": "epic", "desc": "도요/물떼새과 5마리 이상 수집", "rank": 3},
    "🍀 럭키 탐조가": {"tier": "unique", "desc": "멸종위기종 첫 발견! 엄청난 행운입니다.", "rank": 4},
    "🛡️ 자연의 수호자": {"tier": "legendary", "desc": "멸종위기종 5마리 이상 기록. 당신은 자연의 지킴이입니다.", "rank": 5},
}

TIER_STYLE = {
    "rare":      {"color": "#1E88E5", "bg": "#E3F2FD", "border": "#64B5F6", "label": "Rare", "icon": "🔹"},
    "epic":      {"color": "#8E24AA", "bg": "#F3E5F5", "border": "#BA68C8", "label": "Epic", "icon": "🔮"},
    "unique":    {"color": "#F57C00", "bg": "#FFF3E0", "border": "#FFB74D", "label": "Unique", "icon": "🌟"},
    "legendary": {"color": "#2E7D32", "bg": "#E8F5E9", "border": "#81C784", "label": "Legendary", "icon": "🌿"},
}

RARE_BIRDS = {
    "황새": "class1", "저어새": "class1", "노랑부리백로": "class1", "매": "class1", "흰꼬리수리": "class1",
    "참수리": "class1", "검독수리": "class1", "두루미": "class1", "넓적부리도요": "class1", "청다리도요사촌": "class1",
    "크낙새": "class1", "혹고니": "class1", "호사비오리": "class1", "먹황새": "class1",
    "개리": "class2", "큰기러기": "class2", "흑기러기": "class2", "고니": "class2", "큰고니": "class2",
    "가창오리": "class2", "붉은가슴흰죽지": "class2", "검은머리물떼새": "class2", "알락꼬리마도요": "class2",
    "뿔쇠오리": "class2", "흑비둘기": "class2", "섬개개비": "class2", "붉은배새매": "class2",
    "수리부엉이": "class2", "참매": "class2", "까막딱따구리": "class2", "팔색조": "class2",
    "솔개": "class2", "큰말똥가리": "class2", "독수리": "class2", "새호리기": "class2", "물수리": "class2",
    "잿빛개구리매": "class2", "긴점박이올빼미": "class2", "쇠부엉이": "class2", "올빼미": "class2",
    "조롱이": "class2", "털발말똥가리": "class2", "흰목물떼새": "class2", "뜸부기": "class2",
    "재두루미": "class2", "흑두루미": "class2", "검은머리갈매기": "class2", "무당새": "class2",
    "긴꼬리딱새": "class2", "삼광조": "class2", "양비둘기": "class2", "따오기": "class2", "붉은해오라기": "class2",
    "원앙": "natural", "황조롱이": "natural", "소쩍새": "natural", "솔부엉이": "natural",
    "큰소쩍새": "natural", "어치": "natural" 
}
RARE_LABEL = { "class1": "👑 멸종위기 1급", "class2": "⭐ 멸종위기 2급", "natural": "🌿 천연기념물" }

# --- [3. 로직 함수] ---
@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    if not os.path.exists(file_path): return {}, {}, 0, {}, {}
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
            filter_keywords = ['대표국명', '국명', 'Name', 'Family', '과']
            bird_data = bird_data[~bird_data['family'].isin(filter_keywords)]
            total_species_count = len(bird_data)
            bird_list = bird_data['name'].tolist()
            name_to_no = {name: i + 1 for i, name in enumerate(bird_list)}
            name_to_family = dict(zip(bird_data['name'], bird_data['family']))
            family_groups = {}
            for index, row in bird_data.iterrows():
                fam = row['family']
                nm = row['name']
                if fam not in family_groups: family_groups[fam] = []
                family_groups[fam].append(nm)
            family_total_counts = bird_data['family'].value_counts().to_dict()
            return name_to_no, name_to_family, total_species_count, family_total_counts, family_groups
        except Exception as e: continue
    return {}, {}, 0, {}, {}

BIRD_MAP, FAMILY_MAP, TOTAL_SPECIES_COUNT, FAMILY_TOTAL_COUNTS, FAMILY_GROUPS = load_bird_map()
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        expected_cols = ['No', 'bird_name', 'sex', 'date']
        if df.empty: return pd.DataFrame(columns=expected_cols)
        if 'sex' not in df.columns: df['sex'] = '미구분'
        if BIRD_MAP and 'bird_name' in df.columns:
            df['real_no'] = df['bird_name'].apply(lambda x: BIRD_MAP.get(str(x).strip(), 9999))
            df = df.sort_values(by='real_no', ascending=True)
        return df
    except: return pd.DataFrame(columns=['No', 'bird_name', 'sex', 'date'])

def save_data(bird_name, sex, current_df):
    bird_name = bird_name.strip()
    if bird_name not in BIRD_MAP: return f"⚠️ '{bird_name}'은(는) 목록에 없습니다."
    if not current_df.empty and bird_name in current_df['bird_name'].values: return "이미 등록된 새입니다."
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'sex': [sex], 'date': [now]})
        updated_df = pd.concat([current_df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

def delete_birds(bird_names_to_delete, current_df):
    try:
        df = current_df[~current_df['bird_name'].isin(bird_names_to_delete)]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e: return str(e)

def calculate_achievements(df):
    achievements = []
    count = len(df)
    
    if count >= 1: achievements.append("🐣 탐조 입문")
    if count >= 5: achievements.append("🌱 새싹 탐조가")
    if count >= 20: achievements.append("🥉 아마추어 탐조가")
    if count >= 50: achievements.append("🥈 베테랑 탐조가")
    if count >= 100: achievements.append("🥇 마스터 탐조가")
    if count >= 300: achievements.append("💎 전설의 탐조가")
    
    if not df.empty and FAMILY_MAP:
        df['family'] = df['bird_name'].map(FAMILY_MAP)
        fam_counts = df['family'].value_counts()
        
        if df['family'].nunique() >= 15: achievements.append("🌈 다채로운 시선")
        if fam_counts.get('오리과', 0) >= 10: achievements.append("🦆 호수의 지배자")
        if fam_counts.get('수리과', 0) + fam_counts.get('매과', 0) >= 5: achievements.append("🦅 하늘의 제왕")
        if fam_counts.get('백로과', 0) >= 5: achievements.append("🦢 우아한 백로")
        if fam_counts.get('딱다구리과', 0) >= 3: achievements.append("🌲 숲속의 드러머")
        if fam_counts.get('올빼미과', 0) >= 1: achievements.append("🦉 밤의 추적자")
        if fam_counts.get('까마귀과', 0) >= 3: achievements.append("🧠 똑똑한 새")
        if fam_counts.get('박새과', 0) >= 3: achievements.append("👔 넥타이 신사")
        if fam_counts.get('도요과', 0) >= 5: achievements.append("🏖️ 갯벌의 나그네")
    
    rare_count = 0
    for name in df['bird_name']:
        if name in RARE_BIRDS: rare_count += 1
    if rare_count >= 1: achievements.append("🍀 럭키 탐조가")
    if rare_count >= 5: achievements.append("🛡️ 자연의 수호자")
    
    return achievements

def analyze_bird_image(image, user_doubt=None):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        system_instruction = "당신은 조류 전문가입니다. 사진을 분석하여 '종명 | 판단근거' 형식으로 답하세요. 구체적인 종을 모르면 '새 아님'이라고 하세요."
        prompt = f"{system_instruction}"
        if user_doubt: prompt += f"\n사용자 반론: '{user_doubt}'. 재분석하세요."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except: return "Error | 분석 오류"

# --- [4. 메인 화면] ---
st.title("📚 탐조 도감")

df = get_data()
current_achievements = calculate_achievements(df)

if 'my_achievements' not in st.session_state:
    st.session_state['my_achievements'] = current_achievements

newly_earned = list(set(current_achievements) - set(st.session_state['my_achievements']))
st.session_state['my_achievements'] = current_achievements

# 사이드바
with st.sidebar:
    st.header("🏆 업적 현황")
    if current_achievements:
        badge_html_parts = []
        badge_html_parts.append('<div class="sidebar-badge-container">')
        sorted_badges = sorted(current_achievements, key=lambda x: ACHIEVEMENT_INFO.get(x, {}).get('rank', 0), reverse=True)
        top_badges = sorted_badges[:3]
        other_badges = sorted_badges[3:]
        
        for badge_name in top_badges:
            info = ACHIEVEMENT_INFO.get(badge_name, {"tier": "rare"})
            style = TIER_STYLE.get(info['tier'], TIER_STYLE['rare'])
            tag = f'<span class="sidebar-badge" style="background-color: {style["bg"]}; color: {style["color"]}; border: 1px solid {style["color"]}40;">{style["icon"]} {badge_name}</span>'
            badge_html_parts.append(tag)
        badge_html_parts.append('</div>')
        st.markdown("".join(badge_html_parts), unsafe_allow_html=True)
        
        if other_badges:
            with st.expander("🔽 보유 업적 전체 보기"):
                extra_html = '<div class="sidebar-badge-container">'
                for badge_name in other_badges:
                    info = ACHIEVEMENT_INFO.get(badge_name, {"tier": "rare"})
                    style = TIER_STYLE.get(info['tier'], TIER_STYLE['rare'])
                    extra_html += f'<span class="sidebar-badge" style="background-color: {style["bg"]}; color: {style["color"]}; border: 1px solid {style["color"]}40;">{style["icon"]} {badge_name}</span>'
                extra_html += '</div>'
                st.markdown(extra_html, unsafe_allow_html=True)
    else:
        st.caption("달성한 업적이 없습니다.")
    
    st.divider()
    
    st.header("📊 과별 수집 현황")
    if FAMILY_TOTAL_COUNTS:
        my_family_counts = {}
        my_collected_birds = {} 
        
        if not df.empty and FAMILY_MAP:
            df['family'] = df['bird_name'].map(FAMILY_MAP)
            my_family_counts = df['family'].value_counts().to_dict()
            for idx, row in df.iterrows():
                f = row['family']
                n = row['bird_name']
                if f not in my_collected_birds: my_collected_birds[f] = []
                my_collected_birds[f].append(n)

        sorted_families = sorted(FAMILY_TOTAL_COUNTS.keys())
        
        for family in sorted_families:
            total = FAMILY_TOTAL_COUNTS[family]
            count = my_family_counts.get(family, 0)
            
            with st.expander(f"{family} ({count}/{total})"):
                collected_list = my_collected_birds.get(family, [])
                if collected_list:
                    st.markdown(f"**✅ 획득 ({len(collected_list)})**")
                    st.caption(", ".join(collected_list))
                
                all_birds_in_family = FAMILY_GROUPS.get(family, [])
                missing_list = [b for b in all_birds_in_family if b not in collected_list]
                
                if missing_list:
                    st.markdown(f"**🔒 미획득 ({len(missing_list)})**")
                    st.caption(", ".join(missing_list))
                elif total > 0:
                    st.success("🎉 모든 종 수집 완료!")

# 메인 요약
total_collected = len(df)
total_species = TOTAL_SPECIES_COUNT if TOTAL_SPECIES_COUNT > 0 else 1
progress_percent = min((total_collected / total_species) * 100, 100)

st.markdown(f"""
    <div class="summary-box">
        <span class="summary-text">🌱 현재까지 모은 도감</span><br>
        <span class="summary-count">{total_collected}</span>
        <span class="summary-text"> 종 / 전체 {total_species}종</span>
    </div>
    <div class="progress-container">
        <div class="progress-bar" style="width: {progress_percent}%;"></div>
    </div>
""", unsafe_allow_html=True)

# 탭 메뉴
tab1, tab2, tab3 = st.tabs(["✍️ 종 추가", "📜 나의 도감", "🏆 업적 도감"])

# --- [Tab 1] 종 추가 ---
with tab1:
    st.subheader("✍️ 새로운 새 기록하기")
    input_method = st.radio("입력 방식 선택", ["📝 직접 이름 입력", "📸 AI 사진 분석"], horizontal=True)
    
    if input_method == "📝 직접 이름 입력":
        sex_selection = st.radio("성별", ["미구분", "수컷", "암컷"], horizontal=True, key="manual_sex")
        
        def add_manual():
            name = st.session_state.input_bird.strip()
            sex = st.session_state.manual_sex 
            st.session_state.input_bird = ""
            
            if name:
                res = save_data(name, sex, df)
                if res is True: 
                    msg = f"{name}({sex}) 등록 완료!"
                    if name in RARE_BIRDS: msg += f" ({RARE_LABEL.get(RARE_BIRDS[name])} 발견!)"
                    st.session_state.add_message = ('success', msg)
                else: 
                    st.session_state.add_message = ('error', res)
            
        st.text_input("새 이름을 입력하세요", key="input_bird", on_change=add_manual, placeholder="예: 참새")
        
        if 'add_message' in st.session_state and st.session_state.add_message:
            msg_type, msg_text = st.session_state.add_message
            placeholder = st.empty()
            
            if msg_type == 'success':
                placeholder.success(msg_text, icon="✅")
                badge_placeholder = st.empty()
                if newly_earned:
                    for b in newly_earned:
                        badge_placeholder.info(f"🏆 **업적 달성!** [{b}]", icon="🎉")
                
                time.sleep(3)
                placeholder.empty()
                badge_placeholder.empty()
                st.session_state.add_message = None
                
            else:
                placeholder.error(msg_text, icon="🚫")
                time.sleep(3)
                placeholder.empty()
                st.session_state.add_message = None
        
    else: # AI 분석
        uploaded_files = st.file_uploader("새 사진 업로드", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        if 'ai_results' not in st.session_state: st.session_state.ai_results = {}
        
        if uploaded_files:
            for file in uploaded_files:
                if file.name not in st.session_state.ai_results:
                    with st.spinner(f"🔍 {file.name} 분석 중..."):
                        st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file))
                
                raw = st.session_state.ai_results[file.name]
                if "|" in raw:
                    parts = raw.split("|", 1)
                    bird_name = parts[0].strip()
                    reason = parts[1].strip()
                else:
                    bird_name = raw.strip()
                    reason = "상세 이유를 가져오지 못했습니다."
                
                invalid_keywords = ["새이름", "종명", "이름", "새 이름", "모름", "알수없음"]
                if bird_name in invalid_keywords: bird_name = "판독 불가"
                is_valid_bird = True
                if bird_name in ["새 아님", "Error", "판독 불가"] or "오류" in bird_name: is_valid_bird = False

                with st.container(border=True):
                    c1, c2 = st.columns([1, 1.5])
                    with c1: st.image(file, use_container_width=True)
                    with c2:
                        if is_valid_bird:
                            display_name = bird_name
                            if bird_name in RARE_BIRDS:
                                rarity_code = RARE_BIRDS[bird_name]
                                tag_text = RARE_LABEL.get(rarity_code, "")
                                display_name += f" <span style='color:#e65100; font-size:0.9em;'>{tag_text}</span>"
                            st.markdown(f"### **{display_name}**", unsafe_allow_html=True)
                            st.markdown(f"**🔍 판단 이유**")
                            st.info(reason)
                            col_sex, col_btn = st.columns([1, 1])
                            with col_sex:
                                ai_sex = st.radio("성별", ["미구분", "수컷", "암컷"], horizontal=True, key=f"sex_{file.name}", label_visibility="collapsed")
                            with col_btn:
                                if st.button(f"도감에 등록하기", key=f"reg_{file.name}", type="primary", use_container_width=True):
                                    res = save_data(bird_name, ai_sex, df)
                                    if res is True: 
                                        st.session_state.add_message = ('success', f"✅ {bird_name}({ai_sex}) 등록 성공!")
                                        st.rerun()
                                    else: st.error(res)
                        else:
                            st.warning(f"⚠️ **{bird_name}**")
                            st.write(reason)
                        st.divider()
                        c_ask1, c_ask2 = st.columns([0.7, 0.3])
                        user_opinion = c_ask1.text_input("의견", key=f"doubt_{file.name}", placeholder="예: 말똥가리 아냐?", label_visibility="collapsed")
                        if c_ask2.button("재분석", key=f"ask_{file.name}", use_container_width=True):
                            if user_opinion:
                                with st.spinner("재분석 중..."):
                                    st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file), user_opinion)
                                    st.rerun()
        
        if 'add_message' in st.session_state and st.session_state.add_message:
            msg_type, msg_text = st.session_state.add_message
            placeholder = st.empty()
            
            if msg_type == 'success':
                placeholder.success(msg_text, icon="✅")
                badge_placeholder = st.empty()
                if newly_earned:
                    for b in newly_earned:
                        badge_placeholder.info(f"🏆 **업적 달성!** [{b}]", icon="🎉")
                
                time.sleep(3)
                placeholder.empty()
                badge_placeholder.empty()
                st.session_state.add_message = None
            else:
                placeholder.error(msg_text, icon="🚫")
                time.sleep(3)
                placeholder.empty()
                st.session_state.add_message = None

# --- [Tab 2] 나의 도감 (✨ 페이징 & 편집 모드 & UI 버그 수정) ---
with tab2:
    st.subheader("📜 나의 탐조 목록")
    
    edit_mode = st.toggle("🛠️ 목록 관리 (삭제 모드)", key="edit_mode")
    
    if not df.empty:
        if edit_mode:
            st.caption("삭제할 항목을 선택(체크)하고 아래 버튼을 누르세요.")
            df_to_edit = df.copy()
            df_to_edit['삭제'] = False 
            
            cols = ['삭제'] + [c for c in df_to_edit.columns if c != '삭제']
            df_to_edit = df_to_edit[cols]
            
            edited_df = st.data_editor(
                df_to_edit,
                hide_index=True,
                column_config={
                    "삭제": st.column_config.CheckboxColumn("삭제", help="체크하면 삭제됩니다.", default=False),
                    "bird_name": "새 이름", "sex": "성별", "date": "기록 일시", "No": "번호"
                },
                use_container_width=True
            )
            
            to_delete_list = edited_df[edited_df['삭제'] == True]['bird_name'].tolist()
            if to_delete_list:
                if st.button(f"선택한 {len(to_delete_list)}개 항목 영구 삭제", type="primary"):
                    res = delete_birds(to_delete_list, df)
                    if res is True:
                        st.success("삭제되었습니다.")
                        st.rerun()
                    else:
                        st.error(f"삭제 실패: {res}")
        else:
            items_per_page = 10
            total_items = len(df)
            total_pages = max(1, (total_items - 1) // items_per_page + 1)
            
            col_page1, col_page2 = st.columns([8, 2])
            with col_page2:
                page = st.number_input("페이지", min_value=1, max_value=total_pages, step=1, label_visibility="collapsed")
            
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_df = df.iloc[start_idx:end_idx]
            
            for index, row in page_df.iterrows():
                bird = row['bird_name']
                real_no = BIRD_MAP.get(bird, 9999)
                display_no = "??" if real_no == 9999 else real_no
                sex_info = row.get('sex', '미구분')
                sex_icon = ""
                if sex_info == '수컷': sex_icon = " <span style='color:blue; font-size:1rem;'>(♂)</span>"
                elif sex_info == '암컷': sex_icon = " <span style='color:red; font-size:1rem;'>(♀)</span>"
                rare_tag = ""
                if bird in RARE_BIRDS:
                    rarity_code = RARE_BIRDS[bird]
                    tag_class = f"tag-{rarity_code}"
                    tag_text = RARE_LABEL.get(rarity_code, "").replace("👑 ", "").replace("⭐ ", "").replace("🌿 ", "")
                    rare_tag = f"<span class='rare-tag {tag_class}'>{tag_text}</span>"
                
                record_date = row.get('date', '')
                
                # ⭐️ [UI Fix] HTML 태그 들여쓰기 제거
                st.markdown(f"""<div style="display:flex; align-items:center; justify-content:space-between; padding:10px 0; border-bottom:1px solid #eee;">
    <div style="display:flex; align-items:center; gap:12px;">
        <span style="font-size:1.1rem; font-weight:600; color:#555; min-width:30px;">{display_no}.</span>
        <span style="font-size:1.2rem; font-weight:bold; color:#333;">{bird}{sex_icon}</span>
        {rare_tag}
    </div>
    <div style="font-size:0.8rem; color:#999;">{record_date}</div>
</div>""", unsafe_allow_html=True)
            
            st.caption(f"총 {total_items}마리 중 {start_idx+1}~{min(end_idx, total_items)}번째 표시")

    else:
        st.info("아직 기록된 새가 없습니다. 첫 새를 등록해보세요!")

# --- [Tab 3] 업적 도감 ---
with tab3:
    st.subheader("🏆 업적 도감")
    st.caption("탐조 활동을 통해 얻을 수 있는 모든 업적과 조건입니다.")
    sorted_badges = sorted(ACHIEVEMENT_INFO.keys(), key=lambda x: ACHIEVEMENT_INFO[x]['rank'])
    
    for badge_name in sorted_badges:
        info = ACHIEVEMENT_INFO[badge_name]
        is_earned = badge_name in current_achievements
        style = TIER_STYLE.get(info['tier'], TIER_STYLE['rare'])
        
        parts = badge_name.split(" ", 1)
        icon_emoji = parts[0] if len(parts) > 0 else "🏅"
        clean_name = parts[1] if len(parts) > 1 else badge_name
        
        border_color = style.get('border', '#e0e0e0')
        bg_color = style['bg'] if is_earned else "#ffffff"
        opacity = "1.0" if is_earned else "0.6"
        grayscale = "0%" if is_earned else "100%"
        text_color = "#333333" if is_earned else "#999999"
        
        st.markdown(f"""
        <div style="
            border: 2px solid {border_color};
            background-color: {bg_color};
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            opacity: {opacity};
            filter: grayscale({grayscale});
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        ">
            <div style="font-size: 3rem; margin-right: 15px;">{icon_emoji}</div>
            <div>
                <div style="font-weight: bold; font-size: 1.1rem; color: {text_color};">
                    {clean_name} <span style="font-size: 0.8rem; color: {style['color']}; border: 1px solid {style['color']}; border-radius: 5px; padding: 2px 5px; margin-left: 5px;">{style['label']}</span>
                </div>
                <div style="font-size: 0.9rem; color: #666;">{info['desc']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
