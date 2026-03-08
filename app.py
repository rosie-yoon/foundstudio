import streamlit as st
import google.generativeai as genai
import json
import time
import os
import pandas as pd
import requests

# Suno API 설정
SUNO_API_URL = os.getenv('SUNO_API_URL', 'http://localhost:3000')
from datetime import datetime


# ==================== 유틸리티 함수: 가사 정리 ====================
def clean_lyrics_output(raw_lyrics):
    """
    AI가 생성한 가사에서 Title, Theme Description 등 메타데이터를 제거하고
    순수한 가사 구조([Verse], [Chorus] 등)만 반환
    """
    if not raw_lyrics:
        return ""

    lines = raw_lyrics.strip().split('\n')
    cleaned_lines = []
    lyrics_started = False

    for line in lines:
        stripped_line = line.strip()

        # 빈 줄은 가사 시작 후에만 유지
        if not stripped_line:
            if lyrics_started:
                cleaned_lines.append(line)
            continue

        # 메타데이터 줄들 건너뛰기
        lower_line = stripped_line.lower()
        if any(lower_line.startswith(prefix) for prefix in [
            'title:', 'theme:', 'theme description:', 'concept:',
            'style:', 'mood:', 'genre:', 'description:', 'song:', 'track:'
        ]):
            continue

        # [Verse], [Chorus] 등이 나오면 가사 시작으로 판단
        if stripped_line.startswith('[') and any(tag in lower_line for tag in [
            'verse', 'chorus', 'pre-chorus', 'bridge', 'intro', 'outro', 'final', 'hook'
        ]):
            lyrics_started = True

        if lyrics_started:
            cleaned_lines.append(line)

    # 태그를 못 찾았으면 원본 반환 (안전장치)
    if not cleaned_lines:
        return raw_lyrics.strip()

    return '\n'.join(cleaned_lines).strip()


def generate_music_with_suno(title, lyrics, style):
    """Suno API를 통해 음악 생성 - Urban R&B 고정 태그 적용"""
    try:
        # 1. 서버 연결 확인
        health_check = requests.get(f"{SUNO_API_URL}/api/get_limit", timeout=5)
        if health_check.status_code != 200:
            return None, f"Suno API 서버 연결 실패: {health_check.status_code}"

        # 2. 데이터 전처리 (안전성 강화)
        cleaned_lyrics = lyrics.strip()[:2500]  # 보수적인 길이 제한
        cleaned_title = title.strip()[:80]  # 제목 길이 제한

        # 3. ✨ 요청하신 Urban R&B 고정 태그 (영어로 변경)
        fixed_tags = "R&B, Hiphop, Groovy Beat, indie, Urban Soul"

        # 4. 페이로드 구성
        payload = {
            "prompt": cleaned_lyrics,
            "tags": fixed_tags,  # 고정 태그 사용
            "title": cleaned_title,
            "make_instrumental": False,
            "wait_audio": False,
            "mv": "chirp-v3-5"  # 최신 모델 버전 명시
        }

        # 5. 디버깅용 로그 (터미널에서 확인 가능)
        print(f"\n{'=' * 60}")
        print(f"🎵 Suno API 요청 정보")
        print(f"{'=' * 60}")
        print(f"📌 URL: {SUNO_API_URL}/api/custom_generate")
        print(f"🎼 Title: {cleaned_title}")
        print(f"🏷️ Fixed Tags: {fixed_tags}")
        print(f"📝 Lyrics Length: {len(cleaned_lyrics)} chars")
        print(f"⚙️ Model: chirp-v3-5")
        print(f"{'=' * 60}")

        # 6. 요청 전송
        response = requests.post(
            f"{SUNO_API_URL}/api/custom_generate",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60  # 충분한 타임아웃
        )

        # 7. 응답 처리 및 상세 로깅
        print(f"\n📡 Suno API 응답:")
        print(f"🔢 Status Code: {response.status_code}")
        print(f"📄 Response: {response.text[:300]}...")

        if response.status_code == 200:
            result = response.json()
            if result and len(result) > 0:
                ids = [item.get('id') for item in result if item.get('id')]
                if ids:
                    print(f"✅ 생성 성공! IDs: {ids}")
                    return ids, None
                else:
                    return None, "Suno에서 유효한 ID를 반환하지 않았습니다."
            else:
                return None, f"Suno 응답이 비어있습니다: {response.text}"
        else:
            # 에러 상세 정보
            error_detail = response.text[:200] if response.text else "응답 없음"
            print(f"❌ 에러: {error_detail}")
            return None, f"Suno API 오류 {response.status_code}: {error_detail}"

    except requests.exceptions.ConnectionError:
        return None, "❌ Suno API 서버 연결 실패. 터미널에서 'npm run dev' 실행 여부 확인"
    except requests.exceptions.Timeout:
        return None, "⏱️ Suno API 요청 시간 초과 (60초)"
    except Exception as e:
        import traceback
        print(f"\n💥 예외 발생:\n{traceback.format_exc()}")
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
    # ✨ 2분할 UI용 선택 인덱스 추가
    if 'selected_song_index' not in st.session_state:
        st.session_state.selected_song_index = 0
    if 'selected_history_index' not in st.session_state:
        st.session_state.selected_history_index = 0


init_session_state()

# ==================== 페이지 설정 ====================
st.set_page_config(
    page_title="🎵 Found Studio",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2분할 UI를 위한 개선된 CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }

    /* 좌측 곡 목록 스타일 */
    .song-list-container {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 15px;
        max-height: 600px;
        overflow-y: auto;
    }

    /* 우측 상세 패널 스타일 */
    .detail-panel {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 20px;
        min-height: 600px;
    }

    /* 선택된 곡 하이라이트 */
    .selected-song {
        background-color: #FF4B4B !important;
        color: white !important;
    }

    .song-card {
        background: linear-gradient(135deg, #1E1E1E 0%, #2D2D2D 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        border-left: 4px solid #FF4B4B;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
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
        width: 100%;
        text-align: left;
    }

    .stButton>button:hover {
        background-color: #FF6B6B;
        transform: translateY(-1px);
    }

    /* 스크롤바 스타일 */
    .song-list-container::-webkit-scrollbar {
        width: 8px;
    }

    .song-list-container::-webkit-scrollbar-track {
        background: #2D2D2D;
        border-radius: 4px;
    }

    .song-list-container::-webkit-scrollbar-thumb {
        background: #FF4B4B;
        border-radius: 4px;
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
st.title("🎵 Found Studio")
st.markdown("**Gemini AI 기반 프로페셔널 Urban R&B 작사 도구 + 이력 관리**")

# API 키 확인 및 설정
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

        recent_titles = get_recent_titles(50)
        if recent_titles:
            with st.expander("📋 최근 생성된 제목들 (중복 방지 참고용)"):
                st.write("AI가 다양한 제목을 생성할 수 있도록 최근 제목들을 참고합니다:")
                st.write(", ".join(recent_titles[:20]) + ("..." if len(recent_titles) > 20 else ""))

        if st.button("🎲 AI 자동 생성 (제목: 영어 / 컨셉: 한글)", type="primary"):
            with st.spinner("AI가 곡 아이디어를 구상하고 있습니다..."):
                try:
                    model = genai.GenerativeModel('models/gemini-2.5-flash')

                    style_info = GENRE_PROMPTS[st.session_state.selected_genre]['styles'][
                        st.session_state.selected_style]

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
            st.subheader("📋 확정된 셋리스트 (제목: 영어 / 컨셉: 한글)")

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
                raw_lyrics = response.text.strip()

                # 메타데이터 제거하고 순수 가사만 추출
                clean_lyrics = clean_lyrics_output(raw_lyrics)

                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "style": st.session_state.selected_style,
                    "lyrics": clean_lyrics
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
            time.sleep(1)

        st.session_state.generated_lyrics = generated_songs

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

    # ==================== ✨ STEP 6: 2분할 레이아웃 결과 표시 ====================
    elif st.session_state.current_step == 6:
        st.header("6️⃣ 생성 완료! (자동 저장됨)")

        if not st.session_state.generated_lyrics:
            st.error("생성된 가사가 없습니다.")
        else:
            st.success(f"🎉 총 {len(st.session_state.generated_lyrics)}곡의 가사가 완성되어 이력에 저장되었습니다!")

            # 상단 액션 버튼
            col1, col2, col3 = st.columns([1, 1, 1])

            with col1:
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
                    st.text_area(
                        "전체 가사 (클릭하여 전체 선택 후 Ctrl+C로 복사)",
                        value=all_lyrics_text,
                        height=400,
                        key="all_lyrics_display"
                    )

            with col3:
                if st.button("🔄 추가 생성하기"):
                    st.session_state.current_step = 4
                    st.session_state.setlist = []
                    st.rerun()

            st.divider()
            st.info("💡 좌측에서 곡을 선택하면, 우측에 가사와 Suno 생성 기능이 표시됩니다.")

            # ==================== 🎯 2분할 레이아웃 시작 ====================
            left_col, right_col = st.columns([3, 7])

            # ========== 좌측: 곡 목록 ==========
            with left_col:
                st.markdown('<div class="song-list-container">', unsafe_allow_html=True)
                st.subheader("🎵 곡 목록")

                for idx, song in enumerate(st.session_state.generated_lyrics):
                    is_selected = (st.session_state.selected_song_index == idx)
                    button_type = "primary" if is_selected else "secondary"

                    if st.button(
                            f"{'🔵 ' if is_selected else ''}{idx + 1}. {song['title']}",
                            key=f"song_select_{idx}",
                            type=button_type,
                            use_container_width=True
                    ):
                        st.session_state.selected_song_index = idx
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

            # ========== 우측: 선택된 곡 상세 정보 ==========
            with right_col:
                st.markdown('<div class="detail-panel">', unsafe_allow_html=True)

                if 0 <= st.session_state.selected_song_index < len(st.session_state.generated_lyrics):
                    song = st.session_state.generated_lyrics[st.session_state.selected_song_index]
                    idx = st.session_state.selected_song_index

                    st.subheader(f"🎵 {song['title']}")

                    col_info, col_style = st.columns([2, 1])
                    with col_info:
                        st.markdown(f"**컨셉/주제:** {song['theme']}")
                    with col_style:
                        st.markdown(f'<div class="style-tag">{song["style"]}</div>', unsafe_allow_html=True)

                    st.divider()

                    # 복사 기능
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if st.button("📋 제목만 복사", key=f"copy_title_btn_{idx}"):
                            st.session_state[f"show_title_{idx}"] = True

                        if st.session_state.get(f"show_title_{idx}", False):
                            st.text_area(
                                "제목 (Ctrl+A → Ctrl+C)",
                                value=song['title'],
                                height=60,
                                key=f"title_copy_{idx}",
                                label_visibility="collapsed"
                            )

                    with col2:
                        if st.button("📋 가사만 복사", key=f"copy_lyrics_btn_{idx}"):
                            st.session_state[f"show_lyrics_{idx}"] = True

                        if st.session_state.get(f"show_lyrics_{idx}", False):
                            st.text_area(
                                "가사 (Ctrl+A → Ctrl+C)",
                                value=song['lyrics'],
                                height=300,
                                key=f"lyrics_copy_{idx}",
                                label_visibility="collapsed"
                            )

                    with col3:
                        combined_text = f"Title: {song['title']}\n\n{song['lyrics']}"
                        if st.button("📋 전체 복사", key=f"copy_all_btn_{idx}"):
                            st.session_state[f"show_combined_{idx}"] = True

                        if st.session_state.get(f"show_combined_{idx}", False):
                            st.text_area(
                                "제목+가사 (Ctrl+A → Ctrl+C)",
                                value=combined_text,
                                height=300,
                                key=f"combined_copy_{idx}",
                                label_visibility="collapsed"
                            )

                    st.divider()
                    st.subheader("📝 가사 내용")
                    st.text(song['lyrics'])

                    # ============ Suno 음악 생성 섹션 ============
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

                    # Suno API 서버 연결 상태 확인
                    api_connected = False
                    credit_info = None

                    if SUNO_API_URL:
                        try:
                            health_resp = requests.get(f"{SUNO_API_URL}/api/get_limit", timeout=2)
                            if health_resp.status_code == 200:
                                api_connected = True
                                credit_info = health_resp.json()
                        except:
                            pass

                    if api_connected:
                        col_status, col_credit = st.columns([2, 1])
                        with col_status:
                            st.success("✅ Suno API 서버 연결됨")
                        with col_credit:
                            if credit_info:
                                st.metric("남은 크레딧", credit_info.get('credits_left', 'N/A'))
                    else:
                        st.error("❌ Suno API 서버 미연결 (suno-api 폴더에서 'npm run dev' 확인)")

                    # 상태별 UI
                    if suno_state['status'] == 'ready':
                        if suno_state['generation_count'] > 0:
                            st.info(f"💡 이전에 {suno_state['generation_count']}번 생성했습니다.")

                        button_text = "🎵 음악 생성 시작 (2곡)" if suno_state['generation_count'] == 0 else "🔄 새로 생성하기 (2곡)"

                        if st.button(button_text, key=f"suno_gen_{idx}", disabled=not api_connected, type="primary"):
                            with st.spinner("🎵 Suno AI가 2개 버전의 음악을 생성하고 있습니다..."):
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
                        st.warning(f"🎵 음악 생성 중... (2곡 요청됨)")

                        col_check, col_cancel = st.columns([1, 1])

                        with col_check:
                            if st.button("🔄 완성 상태 확인", key=f"suno_check_{idx}", type="primary"):
                                with st.spinner("생성 상태를 확인하고 있습니다..."):
                                    status_data, error = check_suno_status(suno_state['audio_ids'])

                                    if error:
                                        st.error(f"상태 확인 실패: {error}")
                                    elif status_data:
                                        completed_tracks = []
                                        pending_count = 0

                                        for track in status_data:
                                            track_status = track.get('status', '')
                                            if track_status in ['streaming', 'complete'] and track.get('audio_url'):
                                                completed_tracks.append({
                                                    'id': track['id'],
                                                    'audio_url': track['audio_url'],
                                                    'video_url': track.get('video_url'),
                                                    'image_url': track.get('image_url'),
                                                    'title': track.get('title', song['title']),
                                                    'duration': track.get('duration', 0)
                                                })
                                            elif track_status in ['submitted', 'queued', 'processing']:
                                                pending_count += 1

                                        if completed_tracks:
                                            suno_state['status'] = 'completed'
                                            suno_state['audio_urls'] = completed_tracks
                                            st.success(f"✅ {len(completed_tracks)}개 버전 완성!")
                                            st.rerun()
                                        elif pending_count > 0:
                                            st.info(f"🎵 아직 생성 중입니다... ({pending_count}개 트랙 처리 중)")

                        with col_cancel:
                            if st.button("❌ 취소하고 돌아가기", key=f"suno_cancel_{idx}"):
                                suno_state['status'] = 'ready'
                                suno_state['audio_ids'] = []
                                st.rerun()

                        st.caption(f"생성 ID: {', '.join(suno_state['audio_ids'])}")

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
                                    if track1.get('video_url'):
                                        st.markdown(f"[🎬 비디오 다운로드]({track1['video_url']})")

                            with col_v2:
                                track2 = suno_state['audio_urls'][1]
                                st.markdown("### 🎵 버전 2")
                                if track2.get('image_url'):
                                    st.image(track2['image_url'], width=200)
                                if track2['audio_url']:
                                    st.audio(track2['audio_url'])
                                    st.markdown(f"[📥 오디오 다운로드]({track2['audio_url']})")
                                    if track2.get('video_url'):
                                        st.markdown(f"[🎬 비디오 다운로드]({track2['video_url']})")

                        if st.button("🔄 마음에 안 들어요? 다시 생성하기", key=f"suno_regenerate_{idx}"):
                            suno_state['status'] = 'ready'
                            suno_state['audio_ids'] = []
                            suno_state['audio_urls'] = []
                            st.rerun()

                    elif suno_state['status'] == 'error':
                        st.error(f"❌ 음악 생성 중 오류 발생")
                        st.code(suno_state['error_message'])

                        col_retry, col_back = st.columns([1, 1])

                        with col_retry:
                            if st.button("🔄 다시 시도", key=f"suno_retry_{idx}"):
                                suno_state['status'] = 'ready'
                                suno_state['error_message'] = ''
                                st.rerun()

                        with col_back:
                            if st.button("⬅️ 포기하고 돌아가기", key=f"suno_back_{idx}"):
                                suno_state['status'] = 'ready'
                                suno_state['error_message'] = ''
                                st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

# ==================== ✨ TAB 2: 이력 보기 (2분할 UI 적용) ====================
with tab2:
    st.header("📚 생성 이력 보기")
    st.info("🌅 아침에 생성하고 🌆 저녁에 확인하는 워크플로우를 위한 이력 관리")

    df_history = load_history()

    if df_history.empty:
        st.warning("아직 저장된 이력이 없습니다.")
    else:
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

            # 이력도 2분할 레이아웃 적용
            filtered_df = filtered_df.reset_index(drop=True)

            # ==================== 🎯 이력 2분할 레이아웃 ====================
            hist_left_col, hist_right_col = st.columns([3, 7])

            # ========== 좌측: 이력 목록 ==========
            with hist_left_col:
                st.markdown('<div class="song-list-container">', unsafe_allow_html=True)
                st.subheader("📑 곡 목록")

                for idx, row in filtered_df.iterrows():
                    is_selected = (st.session_state.selected_history_index == idx)
                    button_type = "primary" if is_selected else "secondary"

                    display_text = f"{'🔵 ' if is_selected else ''}{row['title']}\n📅 {row['timestamp'][5:16]} | 🎭 {row['style']}"

                    if st.button(
                            display_text,
                            key=f"hist_select_{idx}",
                            type=button_type,
                            use_container_width=True
                    ):
                        st.session_state.selected_history_index = idx
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

            # ========== 우측: 선택된 이력 상세 정보 ==========
            with hist_right_col:
                st.markdown('<div class="detail-panel">', unsafe_allow_html=True)

                if 0 <= st.session_state.selected_history_index < len(filtered_df):
                    selected_row = filtered_df.iloc[st.session_state.selected_history_index]

                    title = str(selected_row.get('title', 'Untitled'))
                    theme_content = selected_row.get('theme_ko', selected_row.get('theme', '컨셉 정보 없음'))
                    raw_lyrics_content = str(selected_row.get('lyrics', ''))
                    lyrics_content = clean_lyrics_output(raw_lyrics_content)

                    st.subheader(f"🎵 {title}")
                    st.markdown(f"**📅 생성일시:** {selected_row['timestamp']}")
                    st.markdown(f"**🎭 스타일:** {selected_row['style']}")
                    st.markdown(f"**💡 컨셉:** {theme_content}")

                    st.divider()

                    # 복사 기능
                    col_a, col_b, col_c = st.columns(3)
                    unique_key = f"hist_{st.session_state.selected_history_index}"

                    with col_a:
                        if st.button("📋 제목 복사", key=f"h_title_btn_{unique_key}"):
                            st.session_state[f"h_show_title_{unique_key}"] = True

                        if st.session_state.get(f"h_show_title_{unique_key}", False):
                            st.text_area(
                                "제목 (Ctrl+A → Ctrl+C)",
                                value=title,
                                height=60,
                                key=f"h_title_copy_{unique_key}",
                                label_visibility="collapsed"
                            )

                    with col_b:
                        if st.button("📋 가사 복사", key=f"h_lyrics_btn_{unique_key}"):
                            st.session_state[f"h_show_lyrics_{unique_key}"] = True

                        if st.session_state.get(f"h_show_lyrics_{unique_key}", False):
                            st.text_area(
                                "가사 (Ctrl+A → Ctrl+C)",
                                value=lyrics_content,
                                height=300,
                                key=f"h_lyrics_copy_{unique_key}",
                                label_visibility="collapsed"
                            )

                    with col_c:
                        combined = f"Title: {title}\n\n{lyrics_content}"
                        if st.button("📋 전체 복사", key=f"h_all_btn_{unique_key}"):
                            st.session_state[f"h_show_combined_{unique_key}"] = True

                        if st.session_state.get(f"h_show_combined_{unique_key}", False):
                            st.text_area(
                                "제목+가사 (Ctrl+A → Ctrl+C)",
                                value=combined,
                                height=300,
                                key=f"h_combined_copy_{unique_key}",
                                label_visibility="collapsed"
                            )

                    st.divider()
                    st.subheader("📝 가사 내용")
                    st.text(lyrics_content)

                st.markdown('</div>', unsafe_allow_html=True)

# ==================== 푸터 ====================
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    🎵 Found Studio | Gemini 2.5 Flash + 이력 관리 시스템
</div>
""", unsafe_allow_html=True)
