# --- 탭 2: AI 분석 (UI 고도화 및 파란색 버튼 적용) ---
with tab2:
    st.subheader("사진으로 이름 찾기")
    uploaded_files = st.file_uploader("새 사진을 업로드하세요", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if 'ai_results' not in st.session_state: st.session_state.ai_results = {}
    if 'dismissed_files' not in st.session_state: st.session_state.dismissed_files = set()

    if uploaded_files:
        active_files = [f for f in uploaded_files if f.name not in st.session_state.dismissed_files]
        for file in active_files:
            if file.name not in st.session_state.ai_results:
                with st.spinner(f"{file.name} 분석 중..."):
                    # 기본 분석 실행
                    st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file))
            
            raw = st.session_state.ai_results[file.name]
            # 에러 방지 분할
            parts = raw.split("|")
            bird_name = parts[0].strip()
            reason = parts[1].strip() if len(parts) > 1 else "분석 결과를 가져왔습니다."
            
            with st.container(border=True):
                # UI 레이아웃: 사진 옆에 이름과 이유를 큼직하게 배치
                c1, c2 = st.columns([1, 1.5])
                
                with c1:
                    st.image(file, use_container_width=True)
                
                with c2:
                    st.markdown(f"### 🏷️ 이름: **{bird_name}**")
                    st.markdown(f"**🔍 판단 이유**")
                    st.write(reason)
                    
                    # 🔵 파란색 [도감에 추가] 버튼 (st.button의 type="primary"는 기본적으로 파란색 계열임)
                    if st.button(f"➕ {bird_name} 등록하기", key=f"reg_{file.name}", type="primary", use_container_width=True):
                        res = save_data(bird_name)
                        if res is True: 
                            st.toast(f"✅ {bird_name} 등록 완료!")
                            st.rerun()
                        else:
                            st.error(res)

                    st.divider()
                    
                    # 💬 사용자의 반론 제기 (재분석 기능)
                    st.write("🤔 **판단이 틀린 것 같나요?**")
                    user_opinion = st.text_input("의견을 적어주세요 (예: 말똥가리 아니야?)", key=f"doubt_input_{file.name}")
                    if st.button("AI에게 다시 확인 요청", key=f"ask_{file.name}"):
                        if user_opinion:
                            with st.spinner("사용자 의견을 바탕으로 재분석 중..."):
                                # 사용자 의견을 담아 다시 분석
                                st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file), user_opinion)
                                st.rerun()
                
                # 우측 상단 닫기 버튼을 대신할 수 있는 하단 닫기
                if st.button("이 사진 분석 닫기", key=f"cls_{file.name}"):
                    st.session_state.dismissed_files.add(file.name)
                    st.rerun()
