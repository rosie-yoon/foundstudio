# app.py
"""
🎵 AI 작사 스튜디오 Pro - Gemini AI 기반 작사 도구
Suno 연동 제거, 7일 자동 보관, 반복 패턴 방지 기능 추가
"""

import streamlit as st
import json
import time
import os
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import google.generativeai as genai


# ==================== 상수 정의 ====================
LYRICS_STORAGE_FILE = "lyrics_storage.json"
HISTORY_CACHE_FILE = "lyrics_history_cache.json"
MAX_HISTORY_DAYS = 7
MAX_RECENT_PATTERNS = 50


# ==================== 유틸리티 함수 ====================
def clean_lyrics_output(raw_lyrics):
    """AI가 생성한 가사에서 메타데이터 제거"""
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


def extract_first_verse(lyrics):
    """가사에서 첫 번째 Verse 추출 (반복 감지용)"""
    lines = lyrics.split('\n')
    verse_content = []
    in_first_verse = False

    for line in lines:
        stripped = line.strip()

        if '[Verse 1]' in stripped:
            in_first_verse = True
            continue

        if in_first_verse:
            if stripped.startswith('[') and 'Verse' not in stripped:
                break
            if stripped:
                verse_content.append(stripped.lower())

    return ' '.join(verse_content[:3])  # 첫 3줄 기준


def calculate_text_hash(text):
    """텍스트의 해시값 계산"""
    return hashlib.md5(text.encode()).hexdigest()[:8]


# ==================== 저장소 관리 ====================
class LyricsStorage:
    """7일 보관 가사 저장소"""

    def __init__(self, filename=LYRICS_STORAGE_FILE):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        """저장된 데이터 로드"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"sessions": []}
        return {"sessions": []}

    def _save_data(self):
        """데이터 저장"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"저장 오류: {e}")

    def _cleanup_expired(self):
        """7일이 지난 데이터 자동 삭제"""
        cutoff_date = (datetime.now() - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
        original_count = len(self.data["sessions"])

        self.data["sessions"] = [
            session for session in self.data["sessions"]
            if session.get("created_at", "") > cutoff_date
        ]

        if len(self.data["sessions"]) < original_count:
            self._save_data()
            return original_count - len(self.data["sessions"])
        return 0

    def add_session(self, genre, style, songs):
        """새로운 세션 추가"""
        self._cleanup_expired()

        session = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "created_at": datetime.now().isoformat(),
            "genre": genre,
            "style": style,
            "songs": songs,
            "expires_at": (datetime.now() + timedelta(days=MAX_HISTORY_DAYS)).isoformat()
        }

        self.data["sessions"].insert(0, session)
        self._save_data()
        return session["session_id"]

    def get_all_sessions(self):
        """모든 유효한 세션 반환"""
        self._cleanup_expired()
        return self.data.get("sessions", [])

    def get_session(self, session_id):
        """특정 세션 조회"""
        for session in self.data.get("sessions", []):
            if session.get("session_id") == session_id:
                return session
        return None

    def delete_session(self, session_id):
        """세션 삭제"""
        self.data["sessions"] = [
            s for s in self.data["sessions"]
            if s.get("session_id") != session_id
        ]
        self._save_data()

    def get_stats(self):
        """통계 반환"""
        self._cleanup_expired()
        total_songs = sum(len(s.get("songs", [])) for s in self.data["sessions"])
        return {
            "total_sessions": len(self.data["sessions"]),
            "total_songs": total_songs,
            "oldest_expires": min(
                [s.get("expires_at", "") for s in self.data["sessions"]],
                default="없음"
            )
        }


# ==================== 반복 패턴 감지 시스템 ====================
class DuplicatePatternDetector:
    """반복 패턴 감지 및 방지"""

    def __init__(self, cache_file=HISTORY_CACHE_FILE):
        self.cache_file = cache_file
        self.verse_patterns = self._load_patterns()

    def _load_patterns(self):
        """기존 패턴 로드"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("patterns", [])
            except:
                return []
        return []

    def _save_patterns(self):
        """패턴 저장"""
        try:
            data = {"patterns": self.verse_patterns[-MAX_RECENT_PATTERNS:]}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.warning(f"패턴 저장 실패: {e}")

    def add_pattern(self, lyrics):
        """새로운 패턴 추가"""
        first_verse = extract_first_verse(lyrics)
        verse_hash = calculate_text_hash(first_verse)

        self.verse_patterns.append({
            "hash": verse_hash,
            "timestamp": datetime.now().isoformat(),
            "preview": first_verse[:100]
        })

        # 최근 50곡만 유지
        self.verse_patterns = self.verse_patterns[-MAX_RECENT_PATTERNS:]
        self._save_patterns()

    def is_duplicate(self, lyrics):
        """중복 패턴 감지"""
        first_verse = extract_first_verse(lyrics)
        verse_hash = calculate_text_hash(first_verse)

        for pattern in self.verse_patterns:
            if pattern["hash"] == verse_hash:
                return True, pattern.get("preview", "")
        return False, ""

    def get_pattern_stats(self):
        """패턴 통계"""
        return len(self.verse_patterns)


# ==================== 페이지 설정 ====================
st.set_page_config(
    page_title="🎵 AI 작사 스튜디오 Pro",
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
    .lyrics-container {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        font-family: 'Courier New', monospace;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)


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


init_session_state()

# ==================== 장르 및 스타일 정의 ====================
GENRE_PROMPTS = {
    "Urban R&B": {
        "description": "JAEHYUN 'J' 앨범 스타일의 모던 R&B",
        "styles": {
            "Smoke Style": {
                "description": "도시적이고 로맨틱한 R&B - 늦은 밤, 자신감, 그루비함",
                "system_prompt": """You are a professional R&B songwriter helping create songs for a music project using Suno AI.

CRITICAL REQUIREMENTS:
1. Song titles MUST be in natural and fluent English only
2. All lyrics MUST be in natural and fluent English only
3. DO NOT include metadata, titles, or descriptions in lyrics output

STYLE: "Smoke Style" - Urban Romantic R&B
Mood: Late night, City atmosphere, Confident but soft romance, Flirting energy, Smooth groove
Themes: late night drives, city lights, playful romance, magnetic attraction, confident intimacy
Tone: smooth, cool, groovy, stylish, urban

SONG STRUCTURE (MANDATORY):
[Verse 1] -> [Pre-Chorus] -> [Chorus] -> [Verse 2] -> [Pre-Chorus] -> [Chorus] -> [Bridge] -> [Final Chorus]

WRITING STYLE: Natural, conversational, emotionally believable, simple but memorable

CRITICAL OUTPUT REQUIREMENTS:
- START directly with [Verse 1]
- Output ONLY lyrics with section tags
- NO metadata, titles, or descriptions
- Each verse should have unique, fresh content
- Avoid repeating opening lines from previous songs

OUTPUT FORMAT: Pure lyrics only"""
            },

            "Dandelion Style": {
                "description": "따뜻하고 감성적인 R&B - 고백, 포근함, 순수한 사랑",
                "system_prompt": """You are a professional R&B songwriter helping create songs for a music project using Suno AI.

CRITICAL REQUIREMENTS:
1. Song titles MUST be in natural and fluent English only
2. All lyrics MUST be in natural and fluent English only
3. DO NOT include metadata, titles, or descriptions in lyrics output

STYLE: "Dandelion Style" - Warm Romantic R&B
Mood: Soft love, Confession, Warm emotional connection, Pure romance, Gentle affection
Themes: first love, deep emotional connection, comfort in love, slow relationship growth, quiet moments together
Tone: warm, sincere, romantic, gentle, emotional

SONG STRUCTURE (MANDATORY):
[Verse 1] -> [Pre-Chorus] -> [Chorus] -> [Verse 2] -> [Pre-Chorus] -> [Chorus] -> [Bridge] -> [Final Chorus]

WRITING STYLE: Natural, conversational, emotionally believable, simple but memorable

CRITICAL OUTPUT REQUIREMENTS:
- START directly with [Verse 1]
- Output ONLY lyrics with section tags
- NO metadata, titles, or descriptions
- Each verse should have unique, fresh content
- Avoid repeating opening lines from previous songs

OUTPUT FORMAT: Pure lyrics only"""
            }
        }
    }
}

# ==================== API 설정 ====================
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

if API_KEY and API_KEY.strip():
    try:
        genai.configure(api_key=API_KEY.strip())
    except Exception as e:
        st.error(f"❌ API 키 오류: {e}")
        st.stop()
else:
    st.error("❌ API 키가 설정되지 않았습니다.")
    st.stop()

# ==================== 메인 UI ====================
st.title("🎵 AI 작사 스튜디오 Pro")
st.markdown("**Gemini AI 기반 프로페셔널 Urban R&B 작사 도구**")

# 저장소 초기화
storage = LyricsStorage()
detector = DuplicatePatternDetector()

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
        stats = storage.get_stats()
        st.metric("저장된 세션", stats["total_sessions"])
        st.metric("생성 곡수", stats["total_songs"])
        st.metric("중복 방지", f"{detector.get_pattern_stats()}곡 기록중")

        st.divider()
        st.info(f"""
        **📅 자동 보관 기간**
        - {MAX_HISTORY_DAYS}일 동안 자동 저장
        - 만료: {stats['oldest_expires']}
        """)

        st.divider()
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

        if st.button("🎲 AI 자동 생성", type="primary"):
            with st.spinner("AI가 곡 아이디어를 구상하고 있습니다..."):
                try:
                    model = genai.GenerativeModel('models/gemini-2.5-flash')

                    style_info = GENRE_PROMPTS[st.session_state.selected_genre]['styles'][
                        st.session_state.selected_style]

                    concept_prompt = f"""
Based on the {st.session_state.selected_style} style of {st.session_state.selected_genre}, generate {st.session_state.num_songs} unique song concepts.

Style Description: {style_info['description']}

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
            st.subheader("📋 확정된 셋리스트")

            edited_setlist = st.data_editor(
                st.session_state.setlist,
                width='stretch',
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
Ensure the opening lyrics are COMPLETELY DIFFERENT from typical song patterns.
Make the first verse unique and memorable with fresh, specific details.

Remember: Start directly with [Verse 1], output ONLY lyrics.
"""

            try:
                response = model.generate_content(lyrics_prompt)
                raw_lyrics = response.text.strip()
                clean_lyrics = clean_lyrics_output(raw_lyrics)

                # 🔥 반복 패턴 감지
                is_duplicate, preview = detector.is_duplicate(clean_lyrics)

                if is_duplicate:
                    st.warning(f"""
                    ⚠️ **반복 패턴 감지** - {song['title']}
                    유사한 도입부가 감지되었습니다. 다시 생성 권장합니다.
                    """)
                    # 반복 감지되어도 일단 추가 (사용자 판단)
                else:
                    detector.add_pattern(clean_lyrics)

                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "lyrics": clean_lyrics
                })

            except Exception as e:
                st.error(f"{song['title']} 생성 중 오류: {str(e)}")
                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "lyrics": f"가사 생성 오류: {str(e)}"
                })

            progress_bar.progress((idx + 1) / len(st.session_state.setlist))
            time.sleep(1)

        st.session_state.generated_lyrics = generated_songs

        # 💾 저장소에 저장
        try:
            session_id = storage.add_session(
                st.session_state.selected_genre,
                st.session_state.selected_style,
                generated_songs
            )
            st.toast(f"✅ {len(generated_songs)}곡이 7일간 자동 저장되었습니다!", icon="💾")
        except Exception as e:
            st.warning(f"⚠️ 저장 중 오류: {e}")

        status_text.text("✅ 모든 작사가 완료되었습니다!")
        st.session_state.current_step = 6
        time.sleep(1)
        st.rerun()

    # STEP 6: 결과 표시
    elif st.session_state.current_step == 6:
        st.header("6️⃣ 생성 완료! (자동 저장됨)")

        if not st.session_state.generated_lyrics:
            st.error("생성된 가사가 없습니다.")
        else:
            st.success(f"🎉 총 {len(st.session_state.generated_lyrics)}곡의 가사가 완성되어 7일간 저장되었습니다!")

            # 전체 제어 버튼
            col1, col2 = st.columns(2)

            with col1:
                all_lyrics_text = "\n\n" + "=" * 80 + "\n\n".join([
                    f"[{idx}] {song['title']}\n\n{song['lyrics']}"
                    for idx, song in enumerate(st.session_state.generated_lyrics, 1)
                ])

                st.download_button(
                    "💾 전체 가사 다운로드",
                    data=all_lyrics_text,
                    file_name=f"{st.session_state.selected_genre}_{st.session_state.selected_style}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain"
                )

            with col2:
                if st.button("🔄 추가 생성하기"):
                    st.session_state.current_step = 4
                    st.session_state.setlist = []
                    st.rerun()

            st.divider()

            # 개별 곡 표시
            st.info("💡 각 곡을 클릭하여 펼치고 가사를 확인하세요.")

            for idx, song in enumerate(st.session_state.generated_lyrics, 1):
                with st.expander(f"🎵 {idx}. {song['title']}", expanded=(idx == 1)):
                    st.markdown(f"**컨셉:** {song.get('theme', '')}")
                    st.divider()

                    # 가사만 표시
                    st.markdown("### 📝 가사")
                    st.markdown(f"""
                    <div class="lyrics-container">
                    {song['lyrics'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)

                    # 복사 버튼
                    if st.button(f"📋 복사하기", key=f"copy_{idx}"):
                        st.code(song['lyrics'], language="text")

# ==================== TAB 2: 이력 보기 ====================
with tab2:
    st.header("📚 생성 이력 보기")
    st.info("🌅 저장된 가사를 검색하고 관리할 수 있습니다. 최대 7일간 보관됩니다.")

    sessions = storage.get_all_sessions()

    if not sessions:
        st.warning("아직 저장된 이력이 없습니다.")
    else:
        # 필터 섹션
        col1, col2, col3 = st.columns(3)

        with col1:
            unique_genres = list(set(s["genre"] for s in sessions))
            selected_genre_filter = st.selectbox("🎭 장르 필터", ["전체"] + unique_genres)

        with col2:
            unique_styles = list(set(s["style"] for s in sessions))
            selected_style_filter = st.selectbox("🎨 스타일 필터", ["전체"] + unique_styles)

        with col3:
            search_term = st.text_input("🔍 제목 검색", placeholder="제목으로 검색...")

        # 필터 적용
        filtered_sessions = [
            s for s in sessions
            if (selected_genre_filter == "전체" or s["genre"] == selected_genre_filter) and
               (selected_style_filter == "전체" or s["style"] == selected_style_filter)
        ]

        # 곡 수준 검색 필터
        if search_term:
            filtered_sessions = [
                {
                    **s,
                    "songs": [
                        song for song in s["songs"]
                        if search_term.lower() in song["title"].lower()
                    ]
                }
                for s in filtered_sessions
            ]
            filtered_sessions = [s for s in filtered_sessions if s["songs"]]

        st.divider()

        if not filtered_sessions:
            st.warning("필터 조건에 맞는 결과가 없습니다.")
        else:
            total_filtered_songs = sum(len(s["songs"]) for s in filtered_sessions)
            st.success(f"📊 {len(filtered_sessions)}개 세션, 총 {total_filtered_songs}곡 검색됨")

            # 세션별 표시
            for session in filtered_sessions:
                session_created = datetime.fromisoformat(session["created_at"])
                session_expires = datetime.fromisoformat(session["expires_at"])
                time_left = (session_expires - datetime.now()).days

                with st.expander(
                    f"📁 {session_created.strftime('%Y-%m-%d %H:%M')} | "
                    f"{session['genre']} - {session['style']} | "
                    f"{len(session['songs'])}곡 | "
                    f"⏰ {time_left}일 남음",
                    expanded=False
                ):
                    col_delete, col_download = st.columns([1, 1])

                    with col_download:
                        session_lyrics = "\n\n" + "=" * 80 + "\n\n".join([
                            f"[{idx}] {song['title']}\n\n{song['lyrics']}"
                            for idx, song in enumerate(session["songs"], 1)
                        ])

                        st.download_button(
                            "💾 세션 다운로드",
                            data=session_lyrics,
                            file_name=f"{session['session_id']}.txt",
                            mime="text/plain",
                            key=f"download_{session['session_id']}"
                        )

                    with col_delete:
                        if st.button("🗑️ 삭제", key=f"delete_{session['session_id']}"):
                            storage.delete_session(session['session_id'])
                            st.rerun()

                    st.divider()

                    # 개별 곡 표시
                    for idx, song in enumerate(session["songs"], 1):
                        with st.expander(f"🎵 {idx}. {song['title']}", expanded=False):
                            st.markdown(f"**컨셉:** {song.get('theme', '')}")
                            st.divider()

                            # 가사만 표시
                            st.markdown("### 📝 가사")
                            st.markdown(f"""
                            <div class="lyrics-container">
                            {song['lyrics'].replace(chr(10), '<br>')}
                            </div>
                            """, unsafe_allow_html=True)

                            # 복사 버튼
                            if st.button(f"📋 복사하기", key=f"copy_history_{session['session_id']}_{idx}"):
                                st.code(song['lyrics'], language="text")

# ==================== 푸터 ====================
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    🎵 AI 작사 스튜디오 Pro | Gemini AI 기반 전문 작사 도구
    <br>
    <small>생성된 가사는 7일간 자동 보관됩니다. 반복 패턴을 자동으로 감지합니다.</small>
</div>
""", unsafe_allow_html=True)
