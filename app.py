import streamlit as st
import google.generativeai as genai
import json
import time
import os
import pandas as pd
import requests
from datetime import datetime

# Suno API 설정
SUNO_API_URL = os.getenv('SUNO_API_URL', 'http://localhost:3000')


# ==================== 유틸리티 함수 ====================
def clean_lyrics_output(raw_lyrics):
    """AI가 생성한 가사에서 메타데이터를 제거하고 순수한 가사만 반환"""
    if not raw_lyrics:
        return ""

    lines = raw_lyrics.strip().split('\n')
    cleaned_lines = []
    lyrics_started = False

    for line in lines:
        stripped_line = line.strip()

        if not stripped_line:
            if lyrics_started:
                cleaned_lines.append(line)
            continue

        lower_line = stripped_line.lower()
        if any(lower_line.startswith(prefix) for prefix in [
            'title:', 'theme:', 'theme description:', 'concept:',
            'style:', 'mood:', 'genre:', 'description:', 'song:', 'track:'
        ]):
            continue

        if stripped_line.startswith('[') and any(tag in lower_line for tag in [
            'verse', 'chorus', 'pre-chorus', 'bridge', 'intro', 'outro', 'final', 'hook'
        ]):
            lyrics_started = True

        if lyrics_started:
            cleaned_lines.append(line)

    if not cleaned_lines:
        return raw_lyrics.strip()

    return '\n'.join(cleaned_lines).strip()


def generate_music_with_suno(title, lyrics, style):
    """Suno API를 통해 음악 생성"""
    try:
        health_check = requests.get(f"{SUNO_API_URL}/api/get_limit", timeout=5)
        if health_check.status_code != 200:
            return None, f"Suno API 서버 연결 실패: {health_check.status_code}"

        cleaned_lyrics = lyrics.strip()[:2500]
        cleaned_title = title.strip()[:80]
        fixed_tags = "R&B, Hiphop, Groovy Beat, indie, Urban Soul"

        payload = {
            "prompt": cleaned_lyrics,
            "tags": fixed_tags,
            "title": cleaned_title,
            "make_instrumental": False,
            "wait_audio": False,
            "mv": "chirp-v3-5"
        }

        response = requests.post(
            f"{SUNO_API_URL}/api/custom_generate",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            if result and len(result) > 0:
                ids = [item.get('id') for item in result if item.get('id')]
                if ids:
                    return ids, None
                else:
                    return None, "Suno에서 유효한 ID를 반환하지 않았습니다."
            else:
                return None, f"Suno 응답이 비어있습니다: {response.text}"
        else:
            error_detail = response.text[:200] if response.text else "응답 없음"
            return None, f"Suno API 오류 {response.status_code}: {error_detail}"

    except requests.exceptions.ConnectionError:
        return None, "❌ Suno API 서버 연결 실패"
    except requests.exceptions.Timeout:
        return None, "⏱️ Suno API 요청 시간 초과 (60초)"
    except Exception as e:
        return None, f"예상치 못한 오류: {str(e)}"


def check_suno_status(audio_ids):
    """Suno 음악 생성 상태 확인"""
    try:
        ids_str = ','.join(audio_ids)
        response = requests.get(
            f"{SUNO_API_URL}/api/get",
            params={'ids': ids_str},
            timeout=10
        )

        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"상태 확인 실패: {response.status_code}"

    except Exception as e:
        return None, f"상태 확인 오류: {str(e)}"


# ==================== API 키 설정 ====================
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", None)
except Exception:
    API_KEY = None

if not API_KEY:
    try:
        from dotenv import load_dotenv

        load_dotenv()
        API_KEY = os.getenv('GEMINI_API_KEY')
    except ImportError:
        API_KEY = None

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
            "theme": song.get('theme', ''),
            "theme_ko": song.get('theme', ''),
            "lyrics": song['lyrics']
        })

    df_new = pd.DataFrame(new_records)

    if os.path.exists(HISTORY_FILE):
        try:
            df_old = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
            df_combined = pd.concat([df_new, df_old], ignore_index=True)
        except:
            df_combined = df_new
    else:
        df_combined = df_new

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
    if not df.empty and 'title' in df.columns:
        return df.head(limit)['title'].tolist()
    return []


# ==================== 세션 상태 초기화 ====================
def init_session_state():
    defaults = {
        'current_step': 1,
        'selected_genre': None,
        'selected_style': None,
        'num_songs': 3,
        'setlist': [],
        'generated_lyrics': [],
        'generation_count': 0,
        'selected_song_index': 0,
        'selected_history_index': 0,
        'history_flat_list': []
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

# ==================== 페이지 설정 ====================
st.set_page_config(
    page_title="Found Studio",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== ✨ 개선된 CSS (독립 스크롤) ====================
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #E8EAED;
    }

    :root {
        --google-blue: #4285F4;
        --google-blue-hover: #5A9DF8;
        --google-blue-dark: #1A73E8;
    }

    .stButton>button {
        background-color: #2D2D2D !important;
        color: #E8EAED !important;
        border: 1px solid #444 !important;
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: 500;
        transition: all 0.2s ease;
        width: 100%;
        text-align: left;
    }

    .stButton>button:hover {
        background-color: #3A3A3A !important;
        border-color: var(--google-blue) !important;
        color: var(--google-blue) !important;
    }

    .stButton>button[kind="primary"] {
        background-color: var(--google-blue) !important;
        border-color: var(--google-blue) !important;
        color: white !important;
        font-weight: 600;
    }

    .stButton>button[kind="primary"]:hover {
        background-color: var(--google-blue-dark) !important;
    }

    /* ✅ 핵심: 독립 스크롤 영역 */
    .song-list-scroll {
        max-height: 70vh;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 8px;
        border-right: 2px solid #333;
    }

    .history-list-scroll {
        max-height: 70vh;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 8px;
        border-right: 2px solid #333;
    }

    .detail-scroll {
        max-height: 70vh;
        overflow-y: auto;
        overflow-x: hidden;
        padding-left: 20px;
    }

    /* 스크롤바 디자인 */
    .song-list-scroll::-webkit-scrollbar,
    .history-list-scroll::-webkit-scrollbar,
    .detail-scroll::-webkit-scrollbar {
        width: 8px;
    }

    .song-list-scroll::-webkit-scrollbar-track,
    .history-list-scroll::-webkit-scrollbar-track,
    .detail-scroll::-webkit-scrollbar-track {
        background: #1E1E1E;
        border-radius: 4px;
    }

    .song-list-scroll::-webkit-scrollbar-thumb,
    .history-list-scroll::-webkit-scrollbar-thumb,
    .detail-scroll::-webkit-scrollbar-thumb {
        background: var(--google-blue);
        border-radius: 4px;
    }

    .song-list-scroll::-webkit-scrollbar-thumb:hover,
    .history-list-scroll::-webkit-scrollbar-thumb:hover,
    .detail-scroll::-webkit-scrollbar-thumb:hover {
        background: var(--google-blue-hover);
    }

    .song-card {
        background-color: transparent;
        border: 1px solid #333;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        border-left: 4px solid var(--google-blue);
    }

    .style-tag {
        background-color: var(--google-blue);
        color: white;
        padding: 6px 14px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }

    h1 { color: var(--google-blue) !important; }
    h2, h3 { color: #E8EAED !important; }
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

CRITICAL OUTPUT REQUIREMENTS:
- DO NOT include "Title:" line in your response
- DO NOT include "Theme Description:" or any descriptive text
- START your response directly with [Verse 1] or [Intro]
- Output ONLY the lyrics structure with section tags

OUTPUT FORMAT: Pure lyrics only, starting with [Verse 1]."""
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

CRITICAL OUTPUT REQUIREMENTS:
- DO NOT include "Title:" line in your response
- DO NOT include "Theme Description:" or any descriptive text
- START your response directly with [Verse 1] or [Intro]
- Output ONLY the lyrics structure with section tags

OUTPUT FORMAT: Pure lyrics only, starting with [Verse 1]."""
            }
        }
    }
}

# ==================== 메인 UI ====================
st.title("Found Studio")
# ✅ 서브타이틀 제거됨

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

        st.header("📈 통계")
        total_history = len(load_history())
        st.metric("전체 생성 곡수", total_history)
        st.metric("이번 세션", st.session_state.generation_count)

        st.divider()

        if st.button("🔄 처음부터 다시 시작", type="secondary"):
            for key in ['current_step', 'selected_genre', 'selected_style', 'setlist', 'generated_lyrics',
                        'selected_song_index']:
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
                    <div style="color: var(--google-blue); font-size: 22px; font-weight: bold; margin-bottom: 8px;">{genre_name}</div>
                    <p>{genre_info['description']}</p>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("선택하기", key=f"genre_{genre_name}"):
                    st.session_state.selected_genre = genre_name
                    st.session_state.current_step = 2
                    st.rerun()

    # STEP 2: 스타일 선택
    elif st.session_state.current_step == 2:
        st.header("2️⃣ 스타일을 선택하세요")
        genre_data = GENRE_PROMPTS[st.session_state.selected_genre]
        for style_name, style_info in genre_data['styles'].items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                <div class="song-card">
                    <div style="color: var(--google-blue); font-size: 22px; font-weight: bold; margin-bottom: 8px;">{style_name}</div>
                    <p>{style_info['description']}</p>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("선택하기", key=f"style_{style_name}"):
                    st.session_state.selected_style = style_name
                    st.session_state.current_step = 3
                    st.rerun()

    # STEP 3: 곡 수 설정
    elif st.session_state.current_step == 3:
        st.header("3️⃣ 생성할 곡 수를 입력하세요")
        num_songs = st.number_input("몇 곡을 생성하시겠습니까?", min_value=1, max_value=25, value=3)
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
        recent_titles = get_recent_titles(50)

        if st.button("🎲 AI 자동 생성 (제목: 영어 / 컨셉: 한글)", type="primary"):
            with st.spinner("AI가 곡 아이디어를 구상하고 있습니다..."):
                try:
                    model = genai.GenerativeModel('models/gemini-2.5-flash')
                    style_info = GENRE_PROMPTS[st.session_state.selected_genre]['styles'][
                        st.session_state.selected_style]

                    avoid_titles_text = ""
                    if recent_titles:
                        avoid_titles_text = f"\n\nIMPORTANT: Avoid creating titles too similar to these recent ones: {', '.join(recent_titles[:15])}"

                    concept_prompt = f"""
Based on the {st.session_state.selected_style} style of {st.session_state.selected_genre}, generate {st.session_state.num_songs} unique song concepts.

Style Description: {style_info['description']}
{avoid_titles_text}

For each song, provide:
1. A catchy, memorable English title
2. A detailed theme/concept description in Korean

Output as JSON:
{{
  "songs": [
    {{"title": "English Song Title", "theme": "한글로 된 상세한 컨셉 설명"}},
    ...
  ]
}}
"""
                    response = model.generate_content(concept_prompt)
                    text = response.text.strip()
                    if text.startswith("```json"):
                        text = text[7:-3]
                    elif text.startswith("```"):
                        text = text[3:-3]

                    data = json.loads(text)
                    st.session_state.setlist = data['songs']
                    st.success("✅ 컨셉 생성 완료!")
                except Exception as e:
                    st.error(f"컨셉 생성 중 오류: {str(e)}")

        if st.session_state.setlist:
            st.subheader("📋 확정된 셋리스트")
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
Remember: Start directly with [Verse 1], do NOT include title or theme description in output.
"""

            try:
                response = model.generate_content(lyrics_prompt)
                clean_lyrics = clean_lyrics_output(response.text.strip())

                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "style": st.session_state.selected_style,
                    "lyrics": clean_lyrics
                })
            except Exception as e:
                st.error(f"{song['title']} 생성 중 오류: {str(e)}")

            progress_bar.progress((idx + 1) / len(st.session_state.setlist))
            time.sleep(1)

        st.session_state.generated_lyrics = generated_songs

        try:
            saved_count = save_to_history(st.session_state.selected_genre, st.session_state.selected_style,
                                          generated_songs)
            st.session_state.generation_count += saved_count
            st.toast(f"✅ {saved_count}곡이 이력에 자동 저장되었습니다!", icon="💾")
        except Exception as e:
            st.warning(f"⚠️ 이력 저장 중 오류: {e}")

        status_text.text("✅ 모든 작사가 완료되었습니다!")
        st.session_state.current_step = 6
        time.sleep(1)
        st.rerun()

    # ==================== ✅ STEP 6: 완벽한 스크롤 UI ====================
    elif st.session_state.current_step == 6:
        st.header("6️⃣ 생성 완료!")

        if not st.session_state.generated_lyrics:
            st.error("생성된 가사가 없습니다.")
        else:
            st.success(f"🎉 총 {len(st.session_state.generated_lyrics)}곡의 가사가 완성되었습니다!")

            # 상단 액션 버튼
            col1, col2, col3 = st.columns(3)
            with col1:
                all_text = "\n\n" + "=" * 80 + "\n\n".join([
                    f"제목: {s['title']}\n컨셉: {s['theme']}\n\n{s['lyrics']}"
                    for s in st.session_state.generated_lyrics
                ])
                st.download_button(
                    "💾 전체 가사 다운로드",
                    data=all_text,
                    file_name=f"Found_Studio_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain"
                )
            with col2:
                if st.button("📋 전체 텍스트 보기"):
                    st.code(all_text, language="text")
            with col3:
                if st.button("🔄 추가 생성하기"):
                    st.session_state.current_step = 4
                    st.session_state.setlist = []
                    st.rerun()

            st.divider()

            # 병렬 배치
            left_col, right_col = st.columns([3, 7], gap="large")

            # ✅ 좌측: 스크롤 가능한 곡 목록
            with left_col:
                st.subheader("곡 목록")

                st.markdown('<div class="song-list-scroll">', unsafe_allow_html=True)

                for idx, song in enumerate(st.session_state.generated_lyrics):
                    is_selected = (st.session_state.selected_song_index == idx)

                    if st.button(
                            song['title'],
                            key=f"song_btn_{idx}",
                            type="primary" if is_selected else "secondary",
                            use_container_width=True
                    ):
                        st.session_state.selected_song_index = idx
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

            # ✅ 우측: 스크롤 가능한 상세 정보
            with right_col:
                st.markdown('<div class="detail-scroll">', unsafe_allow_html=True)

                if 0 <= st.session_state.selected_song_index < len(st.session_state.generated_lyrics):
                    song = st.session_state.generated_lyrics[st.session_state.selected_song_index]
                    idx = st.session_state.selected_song_index

                    st.subheader(song['title'])

                    meta_col1, meta_col2 = st.columns([2, 1])
                    with meta_col1:
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        st.caption(f"📅 생성일시: {current_time}")
                    with meta_col2:
                        st.markdown(f'<div class="style-tag">{song["style"]}</div>', unsafe_allow_html=True)

                    st.markdown(f"**💡 컨셉:** {song['theme']}")
                    st.divider()

                    # ✅ 안내 박스 제거됨 - st.code()만 표시

                    copy_col1, copy_col2 = st.columns(2)

                    with copy_col1:
                        st.markdown("**📋 제목 (Title)**")
                        st.code(song['title'], language="text")

                    with copy_col2:
                        st.markdown("**📋 전체 (제목 + 가사)**")
                        combined_text = f"Title: {song['title']}\n\n{song['lyrics']}"
                        st.code(combined_text, language="text")

                    st.markdown("**📝 가사 (Lyrics)**")
                    st.code(song['lyrics'], language="text")

                    # Suno 생성 기능
                    st.divider()
                    st.subheader("🎼 Suno AI 음악 생성")

                    suno_key = f"suno_state_{idx}"
                    if suno_key not in st.session_state:
                        st.session_state[suno_key] = {
                            'status': 'ready',
                            'audio_ids': [],
                            'audio_urls': [],
                            'error_message': '',
                            'generation_count': 0
                        }

                    suno_state = st.session_state[suno_key]

                    # Suno API 상태 확인
                    api_connected = False
                    if SUNO_API_URL:
                        try:
                            health_resp = requests.get(f"{SUNO_API_URL}/api/get_limit", timeout=2)
                            if health_resp.status_code == 200:
                                api_connected = True
                        except:
                            pass

                    if api_connected:
                        st.success("✅ Suno API 서버 연결됨")
                    else:
                        st.error("❌ Suno API 서버 미연결")

                    # 상태별 UI
                    if suno_state['status'] == 'ready':
                        if st.button("🎵 음악 생성 시작 (2곡)", key=f"suno_gen_{idx}", disabled=not api_connected,
                                     type="primary"):
                            with st.spinner("🎵 Suno AI가 음악을 생성하고 있습니다..."):
                                ids, error = generate_music_with_suno(song['title'], song['lyrics'], song['style'])
                                if error:
                                    suno_state['status'] = 'error'
                                    suno_state['error_message'] = error
                                else:
                                    suno_state['status'] = 'generating'
                                    suno_state['audio_ids'] = ids
                                    suno_state['generation_count'] += 1
                                st.rerun()

                    elif suno_state['status'] == 'generating':
                        st.warning("🎵 음악 생성 중...")
                        if st.button("🔄 완성 상태 확인", key=f"suno_check_{idx}", type="primary"):
                            status_data, error = check_suno_status(suno_state['audio_ids'])
                            if status_data:
                                completed_tracks = []
                                for track in status_data:
                                    if track.get('status') in ['streaming', 'complete'] and track.get('audio_url'):
                                        completed_tracks.append({
                                            'id': track['id'],
                                            'audio_url': track['audio_url'],
                                            'video_url': track.get('video_url'),
                                            'image_url': track.get('image_url'),
                                            'title': track.get('title', song['title']),
                                            'duration': track.get('duration', 0)
                                        })

                                if completed_tracks:
                                    suno_state['status'] = 'completed'
                                    suno_state['audio_urls'] = completed_tracks
                                    st.success("✅ 음악 생성 완료!")
                                    st.rerun()
                                else:
                                    st.info("🎵 아직 생성 중입니다...")

                    elif suno_state['status'] == 'completed':
                        st.success(f"✅ 음악 생성 완료! ({len(suno_state['audio_urls'])}개 버전)")

                        if len(suno_state['audio_urls']) >= 2:
                            col_v1, col_v2 = st.columns(2)

                            with col_v1:
                                track1 = suno_state['audio_urls'][0]
                                st.markdown("### 🎵 버전 1")
                                if track1.get('image_url'):
                                    st.image(track1['image_url'], width=200)
                                if track1['audio_url']:
                                    st.audio(track1['audio_url'])
                                    st.markdown(f"[📥 오디오 다운로드]({track1['audio_url']})")

                            with col_v2:
                                track2 = suno_state['audio_urls'][1]
                                st.markdown("### 🎵 버전 2")
                                if track2.get('image_url'):
                                    st.image(track2['image_url'], width=200)
                                if track2['audio_url']:
                                    st.audio(track2['audio_url'])
                                    st.markdown(f"[📥 오디오 다운로드]({track2['audio_url']})")

                        if st.button("🔄 다시 생성하기", key=f"suno_regen_{idx}"):
                            suno_state['status'] = 'ready'
                            suno_state['audio_ids'] = []
                            suno_state['audio_urls'] = []
                            st.rerun()

                    elif suno_state['status'] == 'error':
                        st.error("❌ 음악 생성 중 오류 발생")
                        st.code(suno_state['error_message'])
                        if st.button("🔄 다시 시도", key=f"suno_retry_{idx}"):
                            suno_state['status'] = 'ready'
                            suno_state['error_message'] = ''
                            st.rerun()
                else:
                    st.info("👈 좌측에서 곡을 선택해주세요.")

                st.markdown('</div>', unsafe_allow_html=True)

# ==================== ✅ TAB 2: 이력 보기 (타이틀 제거) ====================
with tab2:
    # ✅ "생성 이력" 타이틀 제거됨

    df_history = load_history()

    if df_history.empty:
        st.warning("아직 저장된 이력이 없습니다.")
    else:
        # 필터링 UI
        col1, col2, col3 = st.columns(3)
        with col1:
            if 'timestamp' in df_history.columns:
                unique_dates = df_history['timestamp'].astype(str).str[:10].unique()
                selected_date = st.selectbox("📅 날짜 선택", ["전체"] + sorted(unique_dates, reverse=True))
            else:
                selected_date = "전체"
        with col2:
            if 'style' in df_history.columns:
                unique_styles = df_history['style'].unique()
                selected_style = st.selectbox("🎭 스타일 필터", ["전체"] + list(unique_styles))
            else:
                selected_style = "전체"
        with col3:
            search_term = st.text_input("🔍 제목 검색", placeholder="제목으로 검색...")

        # 필터 적용
        filtered_df = df_history.copy()
        if selected_date != "전체" and 'timestamp' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['timestamp'].astype(str).str.startswith(selected_date)]
        if selected_style != "전체" and 'style' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['style'] == selected_style]
        if search_term and 'title' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['title'].astype(str).str.contains(search_term, case=False, na=False)]

        st.divider()

        if filtered_df.empty:
            st.warning("필터 조건에 맞는 결과가 없습니다.")
        else:
            st.success(f"📊 총 {len(filtered_df)}곡이 검색되었습니다.")

            # 날짜별 그룹화
            filtered_df['date_only'] = pd.to_datetime(filtered_df['timestamp']).dt.date
            date_groups = filtered_df.groupby('date_only')

            # 플랫 리스트 생성
            flat_list = []
            for date, group_df in sorted(date_groups, key=lambda x: x[0], reverse=True):
                for _, row in group_df.iterrows():
                    flat_list.append(row)
            st.session_state.history_flat_list = flat_list

            # 병렬 배치
            hist_left, hist_right = st.columns([3, 7], gap="large")

            # ✅ 좌측: 스크롤 가능한 날짜별 트리 목록
            with hist_left:
                st.subheader("날짜별 곡 목록")

                st.markdown('<div class="history-list-scroll">', unsafe_allow_html=True)

                flat_index = 0
                for date, group_df in sorted(date_groups, key=lambda x: x[0], reverse=True):
                    date_str = date.strftime("%Y-%m-%d")

                    with st.expander(f"📅 {date_str} ({len(group_df)}곡)", expanded=(flat_index == 0)):
                        for _, row in group_df.iterrows():
                            is_selected = (st.session_state.selected_history_index == flat_index)

                            if st.button(
                                    row['title'],
                                    key=f"hist_btn_{flat_index}",
                                    type="primary" if is_selected else "secondary",
                                    use_container_width=True
                            ):
                                st.session_state.selected_history_index = flat_index
                                st.rerun()

                            flat_index += 1

                st.markdown('</div>', unsafe_allow_html=True)

            # ✅ 우측: 스크롤 가능한 상세 정보
            with hist_right:
                st.markdown('<div class="detail-scroll">', unsafe_allow_html=True)

                if 0 <= st.session_state.selected_history_index < len(flat_list):
                    selected_row = flat_list[st.session_state.selected_history_index]

                    title = str(selected_row.get('title', 'Untitled'))
                    theme_content = selected_row.get('theme_ko', selected_row.get('theme', '컨셉 정보 없음'))
                    raw_lyrics_content = str(selected_row.get('lyrics', ''))
                    lyrics_content = clean_lyrics_output(raw_lyrics_content)

                    st.subheader(title)
                    st.caption(f"📅 생성일시: {selected_row['timestamp']}")
                    st.markdown(f'<div class="style-tag">{selected_row["style"]}</div>', unsafe_allow_html=True)
                    st.markdown(f"**💡 컨셉:** {theme_content}")

                    st.divider()

                    # ✅ 안내 박스 제거됨

                    st.markdown("**📋 제목 (Title)**")
                    st.code(title, language="text")

                    st.markdown("**📝 가사 (Lyrics)**")
                    st.code(lyrics_content, language="text")
                else:
                    st.info("👈 좌측 목록에서 곡을 선택해주세요.")

                st.markdown('</div>', unsafe_allow_html=True)

# 푸터
st.divider()
st.markdown("""
<div style='text-align: center; color: #9AA0A6; padding: 20px;'>
    🎵 Found Studio | Powered by Gemini 2.5 Flash
</div>
""", unsafe_allow_html=True)
