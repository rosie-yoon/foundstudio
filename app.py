import streamlit as st
import google.generativeai as genai
import json
import time
import os
import pandas as pd
from datetime import datetime

# ==================== API 키 설정 ====================
# 1순위: Streamlit Cloud Secrets (배포 환경)
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", None)
except Exception:
    API_KEY = None

# 2순위: 로컬 .env 파일 (개발 환경)
if not API_KEY:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        API_KEY = os.getenv('GEMINI_API_KEY')
    except ImportError:
        API_KEY = None

# ❌ 이런 줄이 있으면 반드시 삭제!
# if not API_KEY:
#     API_KEY = "AIzaSy..."  <- 하드코딩 금지

if not API_KEY or not API_KEY.strip():
    st.error("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
    st.stop()


# ==================== 파일 저장소 설정 ====================
HISTORY_FILE = "lyrics_history.csv"


def save_to_history(genre, style, songs_data):
    """생성된 곡들을 CSV 파일에 저장"""
    new_records = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    for song in songs_data:
        new_records.append({
            "session_id": session_id,
            "timestamp": timestamp,
            "genre": genre,
            "style": style,
            "title": song['title'],
            "theme_ko": song['theme'],
            "lyrics": song['lyrics']
        })

    df_new = pd.DataFrame(new_records)

    # 기존 파일이 있으면 합치기
    if os.path.exists(HISTORY_FILE):
        try:
            df_old = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
            df_combined = pd.concat([df_new, df_old], ignore_index=True)
        except:
            df_combined = df_new
    else:
        df_combined = df_new

    # 저장 (최신 1000곡만 유지하여 파일 크기 관리)
    df_combined = df_combined.head(1000)
    df_combined.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')

    return len(new_records)


def load_history():
    """저장된 히스토리 불러오기"""
    if os.path.exists(HISTORY_FILE):
        try:
            return pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
        except:
            return pd.DataFrame()
    return pd.DataFrame()


def get_recent_titles(limit=50):
    """최근 생성된 제목들 가져오기 (중복 방지용)"""
    df = load_history()
    if not df.empty:
        return df.head(limit)['title'].tolist()
    return []


# ==================== 페이지 설정 ====================
st.set_page_config(
    page_title="Found Studio",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 다크모드 CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }

    .song-card {
        background: linear-gradient(135deg, #1E1E1E 0%, #2D2D2D 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        border-left: 4px solid #FF4B4B;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }

    .history-card {
        background-color: #262730;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #444;
    }

    .style-tag {
        background-color: #FF4B4B;
        color: white;
        padding: 4px 12px;
        border-radius: 15px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 10px;
    }

    .stButton>button {
        background-color: #FF4B4B;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: bold;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        background-color: #FF6B6B;
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# ==================== 장르 및 프롬프트 시스템 ====================
GENRE_PROMPTS = {
    "Urban R&B": {
        "description": "JAEHYUN 'J' 앨범 스타일의 모던 R&B",
        "styles": {
            "Smoke Style": {
                "description": "도시적이고 로맨틱한 R&B - 늦은 밤, 자신감, 그루비함",
                "system_prompt": """You are a professional R&B songwriter helping create songs for a YouTube-based music project using Suno AI.

CRITICAL REQUIREMENTS:
1. Song titles MUST be in natural and fluent English only
2. All lyrics MUST be in natural and fluent English only
3. Theme descriptions MUST be in Korean only (for user interface)

STYLE: "Smoke Style" - Urban Romantic R&B
Mood: Late night, City atmosphere, Confident but soft romance, Flirting energy, Smooth groove
Themes: late night drives, city lights, playful romance, magnetic attraction, confident intimacy
Tone: smooth, cool, groovy, stylish, urban

SONG STRUCTURE (MANDATORY):
Verse 1 -> Pre-Chorus -> Chorus -> Verse 2 -> Pre-Chorus -> Chorus -> Bridge -> Final Chorus

WRITING STYLE: Natural, conversational, emotionally believable, simple but memorable
BANNED WORDS: neon, velvet, echoes

OUTPUT FORMAT: Clean title and complete lyrics structure."""
            },

            "Dandelion Style": {
                "description": "따뜻하고 감성적인 R&B - 고백, 포근함, 순수한 사랑",
                "system_prompt": """You are a professional R&B songwriter helping create songs for a YouTube-based music project using Suno AI.

CRITICAL REQUIREMENTS:
1. Song titles MUST be in natural and fluent English only
2. All lyrics MUST be in natural and fluent English only
3. Theme descriptions MUST be in Korean only (for user interface)

STYLE: "Dandelion Style" - Warm Romantic R&B
Mood: Soft love, Confession, Warm emotional connection, Pure romance, Gentle affection
Themes: first love, deep emotional connection, comfort in love, slow relationship growth, quiet moments together
Tone: warm, sincere, romantic, gentle, emotional

SONG STRUCTURE (MANDATORY):
Verse 1 -> Pre-Chorus -> Chorus -> Verse 2 -> Pre-Chorus -> Chorus -> Bridge -> Final Chorus

WRITING STYLE: Natural, conversational, emotionally believable, simple but memorable
BANNED WORDS: neon, velvet, echoes

OUTPUT FORMAT: Clean title and complete lyrics structure."""
            }
        }
    }
}


# ==================== 세션 상태 초기화 ====================
def init_session_state():
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 1
    if 'selected_genre' not in st.session_state:
        st.session_state.selected_genre = None
    if 'selected_style' not in st.session_state:
        st.session_state.selected_style = None
    if 'num_songs' not in st.session_state:
        st.session_state.num_songs = 3
    if 'setlist' not in st.session_state:
        st.session_state.setlist = []
    if 'generated_lyrics' not in st.session_state:
        st.session_state.generated_lyrics = []
    if 'generation_count' not in st.session_state:
        st.session_state.generation_count = 0


init_session_state()

# ==================== 메인 UI ====================
st.title("🎵 AI 작사 스튜디오 Pro")
st.markdown("**Gemini AI 기반 프로페셔널 Urban R&B 작사 도구 + 이력 관리**")

# API 키 확인
if API_KEY and API_KEY.strip():
    try:
        genai.configure(api_key=API_KEY.strip())
    except Exception as e:
        st.error(f"❌ API 키 오류: {e}")
        st.stop()
else:
    st.error("❌ API 키가 설정되지 않았습니다.")
    st.stop()

# ==================== 탭 구성 ====================
tab1, tab2 = st.tabs(["✍️ 작사하기", "📚 이력 보기"])

# ==================== TAB 1: 작사하기 ====================
with tab1:
    # 사이드바: 진행 상태 및 통계
    with st.sidebar:
        st.header("📊 진행 상황")
        steps = [
            "1️⃣ 장르 선택",
            "2️⃣ 스타일 선택",
            "3️⃣ 곡 수 설정",
            "4️⃣ 셋리스트 생성",
            "5️⃣ 가사 생성",
            "6️⃣ 결과 확인"
        ]

        for i, step in enumerate(steps, 1):
            if i < st.session_state.current_step:
                st.markdown(f"✅ {step}")
            elif i == st.session_state.current_step:
                st.markdown(f"▶️ **{step}**")
            else:
                st.markdown(f"⭕ {step}")

        st.divider()

        # 통계 정보
        st.header("📈 통계")
        total_history = len(load_history())
        st.metric("전체 생성 곡수", total_history)
        st.metric("이번 세션", st.session_state.generation_count)

        # 최근 이력 미리보기
        if total_history > 0:
            st.header("🕒 최근 생성")
            recent_df = load_history().head(3)
            for _, row in recent_df.iterrows():
                st.markdown(f"🎵 **{row['title']}**")
                st.caption(f"{row['timestamp']} | {row['style']}")

        st.divider()

        # 리셋 버튼
        if st.button("🔄 처음부터 다시 시작", type="secondary"):
            for key in ['current_step', 'selected_genre', 'selected_style', 'setlist', 'generated_lyrics']:
                if key in st.session_state:
                    del st.session_state[key]
            init_session_state()
            st.rerun()

    # STEP 1: 장르 선택
    if st.session_state.current_step == 1:
        st.header("1️⃣ 장르를 선택하세요")

        for genre_name, genre_info in GENRE_PROMPTS.items():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"""
                <div class="song-card">
                    <div style="color: #FF4B4B; font-size: 22px; font-weight: bold; margin-bottom: 8px;">{genre_name}</div>
                    <p>{genre_info['description']}</p>
                    <p><strong>사용 가능한 스타일:</strong> {len(genre_info['styles'])}개</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                if st.button(f"선택하기", key=f"genre_{genre_name}"):
                    st.session_state.selected_genre = genre_name
                    st.session_state.current_step = 2
                    st.rerun()

    # STEP 2: 스타일 선택
    elif st.session_state.current_step == 2:
        st.header(f"2️⃣ 스타일을 선택하세요 - {st.session_state.selected_genre}")

        genre_data = GENRE_PROMPTS[st.session_state.selected_genre]

        for style_name, style_info in genre_data['styles'].items():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"""
                <div class="song-card">
                    <div style="color: #FF4B4B; font-size: 22px; font-weight: bold; margin-bottom: 8px;">{style_name}</div>
                    <p>{style_info['description']}</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                if st.button(f"선택하기", key=f"style_{style_name}"):
                    st.session_state.selected_style = style_name
                    st.session_state.current_step = 3
                    st.rerun()

    # STEP 3: 곡 수 설정
    elif st.session_state.current_step == 3:
        st.header("3️⃣ 생성할 곡 수를 입력하세요")

        st.markdown(f"**선택됨:** {st.session_state.selected_genre} - {st.session_state.selected_style}")

        num_songs = st.number_input(
            "몇 곡을 생성하시겠습니까?",
            min_value=1,
            max_value=25,
            value=3,
            help="한 번에 3~5곡 정도 생성하는 것을 추천합니다."
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("⬅️ 스타일 다시 선택"):
                st.session_state.current_step = 2
                st.rerun()

        with col2:
            if st.button("➡️ 셋리스트 만들기", type="primary"):
                st.session_state.num_songs = num_songs
                st.session_state.current_step = 4
                st.rerun()

    # STEP 4: 셋리스트 생성
    elif st.session_state.current_step == 4:
        st.header("4️⃣ 셋리스트(곡 컨셉) 생성")

        st.info(f"{st.session_state.selected_style} 스타일로 {st.session_state.num_songs}곡의 컨셉을 만듭니다.")

        # 중복 방지를 위한 최근 제목 확인
        recent_titles = get_recent_titles(50)
        if recent_titles:
            with st.expander("📋 최근 생성된 제목들 (중복 방지 참고용)"):
                st.write("AI가 다양한 제목을 생성할 수 있도록 최근 제목들을 참고합니다:")
                st.write(", ".join(recent_titles[:20]) + ("..." if len(recent_titles) > 20 else ""))

        # 자동 생성
        if st.button("🎲 AI 자동 생성 (제목: 영어 / 컨셉: 한글)", type="primary"):
            with st.spinner("AI가 곡 아이디어를 구상하고 있습니다..."):
                try:
                    model = genai.GenerativeModel('models/gemini-2.5-flash')

                    style_info = GENRE_PROMPTS[st.session_state.selected_genre]['styles'][
                        st.session_state.selected_style]

                    # 중복 방지를 위한 프롬프트 보강
                    avoid_titles_text = ""
                    if recent_titles:
                        avoid_titles_text = f"\n\nIMPORTANT: Avoid creating titles too similar to these recent ones: {', '.join(recent_titles[:15])}\nCreate fresh, unique titles that feel different from the above list."

                    concept_prompt = f"""
Based on the {st.session_state.selected_style} style of {st.session_state.selected_genre}, generate {st.session_state.num_songs} unique song concepts.

Style Description: {style_info['description']}

{avoid_titles_text}

For each song, provide:
1. A catchy, memorable English title
2. A detailed theme/concept description in Korean (한글로 상세한 주제/컨셉 설명)

Output as JSON:
{{
  "songs": [
    {{"title": "English Song Title", "theme": "한글로 된 상세한 컨셉 설명"}},
    ...
  ]
}}
"""

                    response = model.generate_content(concept_prompt)

                    # JSON 파싱
                    text = response.text.strip()
                    if text.startswith("```json"):
                        text = text[7:-3]
                    elif text.startswith("```"):
                        text = text[3:-3]

                    data = json.loads(text)
                    st.session_state.setlist = data['songs']
                    st.success("✅ 컨셉 생성 완료!")

                except Exception as e:
                    st.error(f"컨셉 생성 중 오류 발생: {str(e)}")

        # 셋리스트가 준비되면 다음 단계로
        if st.session_state.setlist:
            st.subheader("📋 확정된 셋리스트 (제목: 영어 / 컨셉: 한글)")

            # 데이터 편집기로 수정 가능
            edited_setlist = st.data_editor(
                st.session_state.setlist,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "title": "곡 제목 (English Title)",
                    "theme": "주제 및 컨셉 (한글 설명)"
                },
                num_rows="dynamic"
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("⬅️ 다시 생성하기"):
                    st.session_state.setlist = []
                    st.rerun()

            with col2:
                if st.button("✅ 이대로 가사 생성하기", type="primary"):
                    st.session_state.setlist = edited_setlist
                    st.session_state.current_step = 5
                    st.rerun()

    # STEP 5: 가사 생성
    elif st.session_state.current_step == 5:
        st.header("5️⃣ 가사 생성 중...")

        st.markdown(f"**총 {len(st.session_state.setlist)}곡 생성을 시작합니다.**")
        st.markdown(f"**스타일:** {st.session_state.selected_genre} - {st.session_state.selected_style}")

        # 진행률 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        generated_songs = []

        model = genai.GenerativeModel('models/gemini-2.5-flash')
        style_info = GENRE_PROMPTS[st.session_state.selected_genre]['styles'][st.session_state.selected_style]

        for idx, song in enumerate(st.session_state.setlist):
            status_text.text(f"작사 중: {song['title']} ({idx + 1}/{len(st.session_state.setlist)})")

            lyrics_prompt = f"""
{style_info['system_prompt']}

SPECIFIC SONG REQUEST:
Title: {song['title']}
Theme/Concept: {song['theme']}

Write complete English lyrics for this song following all the guidelines above.

Output format:
Title: {song['title']}

[Verse 1]
...

[Pre-Chorus]  
...

[Chorus]
...

[Verse 2]
...

[Pre-Chorus]
...

[Chorus]
...

[Bridge]
...

[Final Chorus]
...
"""

            try:
                response = model.generate_content(lyrics_prompt)
                lyrics = response.text.strip()

                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "style": st.session_state.selected_style,
                    "lyrics": lyrics
                })

            except Exception as e:
                st.error(f"{song['title']} 생성 중 오류: {str(e)}")
                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "style": st.session_state.selected_style,
                    "lyrics": f"가사 생성 오류: {str(e)}"
                })

            progress_bar.progress((idx + 1) / len(st.session_state.setlist))
            time.sleep(1)  # API 안정성을 위한 대기

        # 결과 저장 및 이력에 추가
        st.session_state.generated_lyrics = generated_songs

        # 자동 저장
        try:
            saved_count = save_to_history(
                st.session_state.selected_genre,
                st.session_state.selected_style,
                generated_songs
            )
            st.session_state.generation_count += saved_count
            st.toast(f"✅ {saved_count}곡이 이력에 자동 저장되었습니다!", icon="💾")
        except Exception as e:
            st.warning(f"⚠️ 이력 저장 중 오류: {e}")

        status_text.text("✅ 모든 작사가 완료되었습니다!")
        st.session_state.current_step = 6
        time.sleep(1)
        st.rerun()

    # STEP 6: 결과 표시 및 복사
    elif st.session_state.current_step == 6:
        st.header("6️⃣ 생성 완료! (자동 저장됨)")

        if not st.session_state.generated_lyrics:
            st.error("생성된 가사가 없습니다. 다시 시도해주세요.")
        else:
            st.success(f"🎉 총 {len(st.session_state.generated_lyrics)}곡의 가사가 완성되어 이력에 저장되었습니다!")

            # 전체 다운로드 및 작업 버튼
            col1, col2, col3 = st.columns([1, 1, 1])

            with col1:
                # 전체 가사 텍스트 생성
                all_lyrics_text = "\n\n" + "=" * 80 + "\n\n".join([
                    f"제목: {song['title']}\n컨셉: {song['theme']}\n\n{song['lyrics']}"
                    for song in st.session_state.generated_lyrics
                ])

                st.download_button(
                    "💾 전체 가사 다운로드",
                    data=all_lyrics_text,
                    file_name=f"{st.session_state.selected_genre}_{st.session_state.selected_style}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain"
                )

            with col2:
                if st.button("📋 전체 텍스트 보기"):
                    st.code(all_lyrics_text, language="text")

            with col3:
                if st.button("🔄 추가 생성하기"):
                    st.session_state.current_step = 4
                    st.session_state.setlist = []
                    st.rerun()

            st.divider()

            st.info("💡 각 곡을 클릭하여 펼치고, Suno에 복사하세요.")

            # 각 곡을 아코디언 방식으로 표시
            for idx, song in enumerate(st.session_state.generated_lyrics, 1):
                with st.expander(f"🎵 {idx}. {song['title']}", expanded=(idx == 1)):

                    # 메타 정보
                    col_info, col_style = st.columns([2, 1])
                    with col_info:
                        st.markdown(f"**컨셉/주제:** {song['theme']}")
                    with col_style:
                        st.markdown(f'<div class="style-tag">{song["style"]}</div>', unsafe_allow_html=True)

                    st.divider()

                    # 복사 버튼들
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if st.button("📋 제목만 복사", key=f"copy_title_{idx}"):
                            st.code(song['title'], language="text")

                    with col2:
                        if st.button("📋 가사만 복사", key=f"copy_lyrics_{idx}"):
                            st.code(song['lyrics'], language="text")

                    with col3:
                        combined_text = f"Title: {song['title']}\n\n{song['lyrics']}"
                        if st.button("📋 전체 복사 (제목+가사)", key=f"copy_all_{idx}"):
                            st.code(combined_text, language="text")

                    # 가사 표시
                    st.subheader("가사 내용 (Lyrics)")
                    st.text(song['lyrics'])

# ==================== TAB 2: 이력 보기 ====================
with tab2:
    st.header("📚 생성 이력 보기")
    st.info("🌅 아침에 생성하고 🌆 저녁에 확인하는 워크플로우를 위한 이력 관리")

    df_history = load_history()

    if df_history.empty:
        st.warning("아직 저장된 이력이 없습니다. 가사를 생성하면 여기에 자동으로 저장됩니다.")
    else:
        # 필터링 옵션
        col1, col2, col3 = st.columns(3)

        with col1:
            # 날짜 필터 (안전한 접근)
            if 'timestamp' in df_history.columns:
                unique_dates = df_history['timestamp'].astype(str).str[:10].unique()
                selected_date = st.selectbox("📅 날짜 선택", ["전체"] + sorted(unique_dates, reverse=True))
            else:
                selected_date = "전체"

        with col2:
            # 스타일 필터 (안전한 접근)
            if 'style' in df_history.columns:
                unique_styles = df_history['style'].unique()
                selected_style = st.selectbox("🎭 스타일 필터", ["전체"] + list(unique_styles))
            else:
                selected_style = "전체"

        with col3:
            # 검색
            search_term = st.text_input("🔍 제목 검색", placeholder="제목으로 검색...")

        # 필터 적용 (안전한 방식)
        filtered_df = df_history.copy()

        if selected_date != "전체" and 'timestamp' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['timestamp'].astype(str).str.startswith(selected_date)]

        if selected_style != "전체" and 'style' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['style'] == selected_style]

        if search_term and 'title' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['title'].astype(str).str.contains(search_term, case=False, na=False)]

        # 결과 표시
        st.divider()

        if filtered_df.empty:
            st.warning("필터 조건에 맞는 결과가 없습니다.")
        else:
            st.success(f"📊 총 {len(filtered_df)}곡이 검색되었습니다.")

            # 세션별 그룹화 (session_id 없으면 timestamp 사용)
            if 'session_id' not in filtered_df.columns:
                filtered_df['session_id'] = filtered_df['timestamp']

            sessions = filtered_df.groupby('session_id')

            # 최신순 정렬
            sorted_sessions = sorted(sessions, key=lambda x: x[1]['timestamp'].max(), reverse=True)

            for session_id, session_df in sorted_sessions:
                session_info = session_df.iloc[0]
                session_count = len(session_df)
                timestamp_str = str(session_info['timestamp'])
                genre_str = str(session_info.get('genre', 'Unknown'))
                style_str = str(session_info.get('style', 'Unknown'))

                with st.expander(
                        f"📁 {timestamp_str} | {genre_str} - {style_str} | {session_count}곡",
                        expanded=False
                ):
                    for idx, (_, song) in enumerate(session_df.iterrows(), 1):
                        # 안전한 데이터 접근 (핵심 수정 부분)
                        title = str(song.get('title', 'Untitled'))
                        theme_content = song.get('theme_ko', song.get('theme', '컨셉 정보 없음'))
                        lyrics_content = str(song.get('lyrics', ''))

                        st.markdown(f"### 🎵 {idx}. {title}")
                        st.markdown(f"**컨셉:** {theme_content}")

                        # 복사 버튼 (고유 키 생성)
                        col_a, col_b, col_c = st.columns(3)
                        unique_key = f"{session_id}_{idx}_{hash(str(song.name))}"

                        with col_a:
                            if st.button("📋 제목 복사", key=f"h_title_{unique_key}"):
                                st.code(title, language="text")

                        with col_b:
                            if st.button("📋 가사 복사", key=f"h_lyrics_{unique_key}"):
                                st.code(lyrics_content, language="text")

                        with col_c:
                            combined = f"Title: {title}\n\n{lyrics_content}"
                            if st.button("📋 전체 복사", key=f"h_all_{unique_key}"):
                                st.code(combined, language="text")

                        # 가사 표시
                        with st.expander("가사 내용 보기", expanded=False):
                            st.text(lyrics_content)

                        st.divider()

# ==================== 푸터 ====================
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    🎵 Found Studio
</div>
""", unsafe_allow_html=True)
