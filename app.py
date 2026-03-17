# app.py (완전한 스타일 관리 시스템)
"""
🎵 AI 작사 스튜디오 Pro - Gemini AI 기반 작사 도구
- 사용자가 직접 금지어 입력 (제목 + 가사 적용)
- 스타일 추가/수정/삭제 관리
- 다중 API 키 자동 전환
- 7일 자동 보관
"""

import streamlit as st
import json
import time
import os
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import google.generativeai as genai
from typing import Optional, Tuple, List


# ==================== 상수 정의 ====================
LYRICS_STORAGE_FILE = "lyrics_storage.json"
HISTORY_CACHE_FILE = "lyrics_history_cache.json"
API_USAGE_LOG = "api_usage_log.json"
STYLES_CONFIG_FILE = "styles_config.json"
MAX_HISTORY_DAYS = 7
MAX_RECENT_PATTERNS = 50
OPENING_WORDS_THRESHOLD = 3


# ==================== 스타일 관리 ====================
class StyleManager:
    """사용자 정의 스타일 관리"""

    def __init__(self, filename=STYLES_CONFIG_FILE):
        self.filename = filename
        self.styles = self._load_styles()

    def _load_styles(self):
        """저장된 스타일 로드"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._get_default_styles()
        return self._get_default_styles()

    def _get_default_styles(self):
        """기본 스타일"""
        return {
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
4. CREATE UNIQUE opening lines that are FRESH and ORIGINAL
5. Each song must have completely different first verse content

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

OUTPUT FORMAT: Pure lyrics only"""
                    },

                    "Dandelion Style": {
                        "description": "따뜻하고 감성적인 R&B - 고백, 포근함, 순수한 사랑",
                        "system_prompt": """You are a professional R&B songwriter helping create songs for a music project using Suno AI.

CRITICAL REQUIREMENTS:
1. Song titles MUST be in natural and fluent English only
2. All lyrics MUST be in natural and fluent English only
3. DO NOT include metadata, titles, or descriptions in lyrics output
4. CREATE UNIQUE opening lines that are FRESH and ORIGINAL
5. Each song must have completely different first verse content

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

OUTPUT FORMAT: Pure lyrics only"""
                    }
                }
            }
        }

    def _save_styles(self):
        """스타일 저장"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.styles, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            st.error(f"스타일 저장 실패: {e}")
            return False

    def get_genres(self):
        """모든 장르 반환"""
        return list(self.styles.keys())

    def get_genre_styles(self, genre):
        """특정 장르의 스타일 반환"""
        if genre in self.styles:
            return self.styles[genre].get("styles", {})
        return {}

    def get_style_prompt(self, genre, style):
        """스타일의 프롬프트 반환"""
        if genre in self.styles and style in self.styles[genre].get("styles", {}):
            return self.styles[genre]["styles"][style].get("system_prompt", "")
        return ""

    def add_genre(self, genre_name, description):
        """새로운 장르 추가"""
        if genre_name not in self.styles:
            self.styles[genre_name] = {
                "description": description,
                "styles": {}
            }
            return self._save_styles()
        return False

    def add_style(self, genre, style_name, style_description, system_prompt):
        """새로운 스타일 추가"""
        if genre in self.styles:
            if style_name not in self.styles[genre]["styles"]:
                self.styles[genre]["styles"][style_name] = {
                    "description": style_description,
                    "system_prompt": system_prompt
                }
                return self._save_styles()
        return False

    def update_style(self, genre, style_name, style_description, system_prompt):
        """스타일 수정"""
        if genre in self.styles and style_name in self.styles[genre]["styles"]:
            self.styles[genre]["styles"][style_name] = {
                "description": style_description,
                "system_prompt": system_prompt
            }
            return self._save_styles()
        return False

    def delete_style(self, genre, style_name):
        """스타일 삭제"""
        if genre in self.styles and style_name in self.styles[genre]["styles"]:
            del self.styles[genre]["styles"][style_name]
            return self._save_styles()
        return False

    def export_styles(self):
        """스타일을 JSON으로 내보내기"""
        return json.dumps(self.styles, ensure_ascii=False, indent=2)

    def import_styles(self, json_str):
        """JSON에서 스타일 가져오기"""
        try:
            new_styles = json.loads(json_str)
            self.styles = new_styles
            return self._save_styles()
        except Exception as e:
            st.error(f"스타일 가져오기 실패: {e}")
            return False


# ==================== 다중 API 키 관리자 ====================
class MultiAPIKeyManager:
    """여러 개의 Gemini API 키를 관리하고 자동으로 전환"""

    def __init__(self):
        self.api_keys = self._load_api_keys()
        self.current_key_index = 0
        self.usage_log = self._load_usage_log()

    def _load_api_keys(self):
        """secrets.toml에서 API 키 로드"""
        api_keys = []
        try:
            api_key_1 = st.secrets.get("GEMINI_API_KEY", None)
            api_key_2 = st.secrets.get("GEMINI_API_KEY_2", None)

            if api_key_1:
                api_keys.append({"key": api_key_1, "name": "Key 1"})
            if api_key_2:
                api_keys.append({"key": api_key_2, "name": "Key 2"})

        except Exception:
            pass

        if not api_keys:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                api_key_1 = os.getenv('GEMINI_API_KEY')
                api_key_2 = os.getenv('GEMINI_API_KEY_2')

                if api_key_1:
                    api_keys.append({"key": api_key_1, "name": "Key 1"})
                if api_key_2:
                    api_keys.append({"key": api_key_2, "name": "Key 2"})

            except ImportError:
                pass

        return api_keys

    def _load_usage_log(self):
        """API 사용 기록 로드"""
        if os.path.exists(API_USAGE_LOG):
            try:
                with open(API_USAGE_LOG, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"keys": {}}
        return {"keys": {}}

    def _save_usage_log(self):
        """API 사용 기록 저장"""
        try:
            with open(API_USAGE_LOG, 'w', encoding='utf-8') as f:
                json.dump(self.usage_log, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _test_api_key(self, api_key):
        """API 키가 유효한지 테스트"""
        try:
            test_genai = genai.GenerativeModel('models/gemini-2.5-flash')
            genai.configure(api_key=api_key)
            response = test_genai.generate_content("test", generation_config={'max_output_tokens': 1})
            return True
        except Exception as e:
            return False

    def get_current_key(self):
        """현재 사용 가능한 API 키 반환"""
        if not self.api_keys:
            return None

        for i in range(len(self.api_keys)):
            key_data = self.api_keys[i]
            if self._test_api_key(key_data["key"]):
                self.current_key_index = i
                return key_data["key"]

        return None

    def get_next_key(self):
        """다음 API 키로 전환"""
        if not self.api_keys:
            return None

        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return self.api_keys[self.current_key_index]["key"]

    def mark_key_exhausted(self, api_key):
        """특정 API 키를 소진된 것으로 표시"""
        for i, key_data in enumerate(self.api_keys):
            if key_data["key"] == api_key:
                key_data["exhausted"] = True
                self._save_usage_log()
                break

    def get_status(self):
        """API 키 상태 반환"""
        status = []
        for i, key_data in enumerate(self.api_keys):
            is_current = (i == self.current_key_index)
            status.append({
                "name": key_data["name"],
                "is_current": is_current,
                "is_exhausted": key_data.get("exhausted", False)
            })
        return status


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


def extract_opening_words(lyrics):
    """가사에서 첫 번째 Verse의 처음 3단어 추출"""
    lines = lyrics.split('\n')
    verse_words = []
    in_first_verse = False

    for line in lines:
        stripped = line.strip()

        if '[Verse 1]' in stripped:
            in_first_verse = True
            continue

        if in_first_verse:
            if stripped.startswith('[') and 'Verse' not in stripped:
                break
            if stripped and not stripped.startswith('['):
                words = stripped.lower().split()
                verse_words.extend(words)

                if len(verse_words) >= OPENING_WORDS_THRESHOLD:
                    return ' '.join(verse_words[:OPENING_WORDS_THRESHOLD])

    return ' '.join(verse_words[:OPENING_WORDS_THRESHOLD])


def calculate_text_hash(text):
    """텍스트의 해시값 계산"""
    return hashlib.md5(text.encode()).hexdigest()[:8]


def check_banned_words(text: str, banned_words: List[str]) -> Tuple[bool, List[str]]:
    """제목/가사에서 금지어 검사"""
    if not banned_words:
        return False, []

    text_lower = text.lower()
    found_words = []

    for banned_word in banned_words:
        if banned_word.lower() in text_lower:
            if banned_word not in found_words:
                found_words.append(banned_word)

    return len(found_words) > 0, found_words


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


# ==================== 반복 패턴 감지 ====================
class DuplicatePatternDetector:
    """반복 패턴 감지 및 방지"""

    def __init__(self, cache_file=HISTORY_CACHE_FILE):
        self.cache_file = cache_file
        self.patterns = self._load_patterns()

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
            data = {"patterns": self.patterns[-MAX_RECENT_PATTERNS:]}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_pattern(self, lyrics):
        """새로운 패턴 추가"""
        opening_words = extract_opening_words(lyrics)
        opening_hash = calculate_text_hash(opening_words)

        self.patterns.append({
            "hash": opening_hash,
            "opening": opening_words,
            "timestamp": datetime.now().isoformat()
        })

        self.patterns = self.patterns[-MAX_RECENT_PATTERNS:]
        self._save_patterns()

    def is_duplicate(self, lyrics) -> Tuple[bool, str]:
        """중복 패턴 감지"""
        opening_words = extract_opening_words(lyrics)
        opening_hash = calculate_text_hash(opening_words)

        for pattern in self.patterns:
            if pattern["hash"] == opening_hash:
                return True, pattern.get("opening", "")

        return False, ""

    def get_pattern_stats(self):
        """패턴 통계"""
        return len(self.patterns)


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
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .song-history-card {
        background: #1a1a1a;
        border-left: 4px solid #FF4B4B;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    .banned-word-tag {
        background-color: #FF6B6B;
        color: white;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 13px;
        display: inline-block;
        margin: 5px 5px 5px 0;
    }
    .warning-box {
        background-color: #ff6b6b20;
        border-left: 4px solid #FF6B6B;
        padding: 12px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #4CAF5020;
        border-left: 4px solid #4CAF50;
        padding: 12px;
        border-radius: 8px;
        margin: 10px 0;
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
    if 'banned_words' not in st.session_state:
        st.session_state.banned_words = []
    if 'setlist' not in st.session_state:
        st.session_state.setlist = []
    if 'generated_lyrics' not in st.session_state:
        st.session_state.generated_lyrics = []


init_session_state()

# ==================== 초기화 ====================
api_manager = MultiAPIKeyManager()
style_manager = StyleManager()

if not api_manager.api_keys:
    st.error("❌ API 키가 설정되지 않았습니다.")
    st.stop()

storage = LyricsStorage()
detector = DuplicatePatternDetector()

# ==================== 메인 UI ====================
st.title("🎵 AI 작사 스튜디오 Pro")
st.markdown("**Gemini AI 기반 프로페셔널 Urban R&B 작사 도구**")

# ==================== 탭 구성 ====================
tab1, tab2, tab3, tab4 = st.tabs(["✍️ 작사하기", "📚 이력 보기", "⚙️ 스타일 관리", "🔧 고급 설정"])

# ==================== TAB 3: 스타일 관리 ====================
with tab3:
    st.header("⚙️ 스타일 관리")

    style_tab1, style_tab2, style_tab3 = st.tabs(["📖 조회", "➕ 추가", "✏️ 수정/삭제"])

    # TAB 3-1: 스타일 조회
    with style_tab1:
        st.subheader("📖 등록된 스타일 조회")

        genres = style_manager.get_genres()
        selected_genre = st.selectbox("장르 선택", genres, key="view_genre")

        if selected_genre:
            genre_styles = style_manager.get_genre_styles(selected_genre)

            if genre_styles:
                for style_name, style_info in genre_styles.items():
                    with st.expander(f"🎨 {style_name}"):
                        st.markdown(f"**설명:** {style_info.get('description', '')}")
                        st.divider()
                        st.markdown("**프롬프트:**")
                        st.code(style_info.get('system_prompt', ''), language="text")
            else:
                st.warning("등록된 스타일이 없습니다.")

    # TAB 3-2: 스타일 추가
    with style_tab2:
        st.subheader("➕ 새로운 스타일 추가")

        col1, col2 = st.columns(2)

        with col1:
            # 기존 장르에 추가하는지, 새 장르를 만드는지 선택
            add_option = st.radio(
                "추가 방식 선택",
                ["기존 장르에 추가", "새 장르 생성"],
                key="add_option"
            )

        with col2:
            st.markdown("")

        if add_option == "기존 장르에 추가":
            genres = style_manager.get_genres()
            selected_genre = st.selectbox("장르 선택", genres, key="add_genre")

            style_name = st.text_input("스타일 이름", placeholder="예: Minimal Style")
            style_description = st.text_area(
                "스타일 설명",
                placeholder="이 스타일의 특징을 한글로 설명하세요",
                height=100
            )

            st.markdown("**시스템 프롬프트** (AI에게 주는 지시사항)")
            system_prompt = st.text_area(
                "프롬프트 입력",
                placeholder="You are a professional R&B songwriter...",
                height=300,
                label_visibility="collapsed"
            )

            if st.button("✅ 스타일 추가", type="primary"):
                if style_name and style_description and system_prompt:
                    if style_manager.add_style(selected_genre, style_name, style_description, system_prompt):
                        st.success(f"✅ '{style_name}' 스타일이 추가되었습니다!")
                        st.rerun()
                    else:
                        st.error("❌ 스타일 추가 실패 (이미 존재합니다)")
                else:
                    st.error("❌ 모든 필드를 입력해주세요")

        else:  # 새 장르 생성
            genre_name = st.text_input("새 장르 이름", placeholder="예: K-POP")
            genre_description = st.text_area(
                "장르 설명",
                placeholder="이 장르의 특징을 설명하세요",
                height=100
            )

            style_name = st.text_input("스타일 이름 (함께 생성)", placeholder="예: Trendy Style")
            style_description = st.text_area(
                "스타일 설명",
                placeholder="이 스타일의 특징을 한글로 설명하세요",
                height=100
            )

            st.markdown("**시스템 프롬프트**")
            system_prompt = st.text_area(
                "프롬프트 입력",
                placeholder="You are a professional songwriter...",
                height=300,
                label_visibility="collapsed"
            )

            if st.button("✅ 장르 및 스타일 생성", type="primary"):
                if genre_name and genre_description and style_name and style_description and system_prompt:
                    if style_manager.add_genre(genre_name, genre_description):
                        if style_manager.add_style(genre_name, style_name, style_description, system_prompt):
                            st.success(f"✅ '{genre_name}' 장르와 '{style_name}' 스타일이 생성되었습니다!")
                            st.rerun()
                        else:
                            st.error("❌ 스타일 생성 실패")
                    else:
                        st.error("❌ 장르 생성 실패 (이미 존재합니다)")
                else:
                    st.error("❌ 모든 필드를 입력해주세요")

    # TAB 3-3: 스타일 수정/삭제
    with style_tab3:
        st.subheader("✏️ 스타일 수정/삭제")

        col1, col2 = st.columns(2)

        with col1:
            genres = style_manager.get_genres()
            selected_genre = st.selectbox("장르 선택", genres, key="edit_genre")

        with col2:
            if selected_genre:
                genre_styles = style_manager.get_genre_styles(selected_genre)
                style_names = list(genre_styles.keys())

                if style_names:
                    selected_style = st.selectbox("스타일 선택", style_names, key="edit_style")
                else:
                    st.warning("이 장르에 스타일이 없습니다.")
                    selected_style = None
            else:
                selected_style = None

        if selected_style and selected_genre:
            style_info = style_manager.get_genre_styles(selected_genre)[selected_style]

            st.divider()
            st.markdown(f"### 현재 스타일: {selected_style}")

            edit_tab1, edit_tab2 = st.tabs(["✏️ 수정", "🗑️ 삭제"])

            with edit_tab1:
                new_description = st.text_area(
                    "스타일 설명 수정",
                    value=style_info.get('description', ''),
                    height=100
                )

                new_prompt = st.text_area(
                    "프롬프트 수정",
                    value=style_info.get('system_prompt', ''),
                    height=300
                )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("✅ 수정 저장", type="primary"):
                        if style_manager.update_style(selected_genre, selected_style, new_description, new_prompt):
                            st.success(f"✅ '{selected_style}' 스타일이 수정되었습니다!")
                            st.rerun()
                        else:
                            st.error("❌ 수정 실패")

                with col2:
                    st.markdown("")

            with edit_tab2:
                st.warning(f"⚠️ '{selected_style}' 스타일을 삭제하시겠습니까?")
                st.info("⚠️ 이 작업은 되돌릴 수 없습니다.")

                if st.button("🗑️ 삭제", type="secondary"):
                    if style_manager.delete_style(selected_genre, selected_style):
                        st.success(f"✅ '{selected_style}' 스타일이 삭제되었습니다!")
                        st.rerun()
                    else:
                        st.error("❌ 삭제 실패")

    st.divider()
    st.subheader("📤 스타일 내보내기/가져오기")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📤 내보내기", use_container_width=True):
            export_json = style_manager.export_styles()
            st.download_button(
                "💾 styles.json 다운로드",
                data=export_json,
                file_name=f"styles_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )

    with col2:
        st.markdown("**📥 가져오기**")
        uploaded_file = st.file_uploader("JSON 파일 선택", type="json")

        if uploaded_file:
            try:
                json_content = uploaded_file.read().decode('utf-8')
                if st.button("✅ 가져오기", use_container_width=True):
                    if style_manager.import_styles(json_content):
                        st.success("✅ 스타일을 가져왔습니다!")
                        st.rerun()
                    else:
                        st.error("❌ 가져오기 실패")
            except Exception as e:
                st.error(f"❌ 파일 읽기 실패: {e}")


# ==================== TAB 4: 고급 설정 ====================
with tab4:
    st.header("🔧 고급 설정")

    st.subheader("🔑 API 키 상태")
    api_status = api_manager.get_status()
    for status in api_status:
        if status["is_exhausted"]:
            st.error(f"❌ {status['name']} - 소진됨")
        elif status["is_current"]:
            st.success(f"✅ {status['name']} - 사용중")
        else:
            st.info(f"⏳ {status['name']} - 대기중")

    st.divider()
    st.subheader("📊 통계 및 정보")

    col1, col2, col3 = st.columns(3)

    with col1:
        stats = storage.get_stats()
        st.metric("저장된 세션", stats["total_sessions"])

    with col2:
        st.metric("생성된 곡", stats["total_songs"])

    with col3:
        st.metric("반복 패턴", f"{detector.get_pattern_stats()}곡")

    st.divider()
    st.subheader("🗑️ 데이터 초기화")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 모든 이력 삭제", type="secondary"):
            storage.data["sessions"] = []
            storage._save_data()
            st.success("✅ 모든 이력이 삭제되었습니다!")
            st.rerun()

    with col2:
        if st.button("🔄 반복 패턴 초기화", type="secondary"):
            detector.patterns = []
            detector._save_patterns()
            st.success("✅ 반복 패턴이 초기화되었습니다!")
            st.rerun()


# ==================== TAB 1: 작사하기 ====================
with tab1:
    with st.sidebar:
        st.header("📊 진행 상황")
        steps = [
            "1️⃣ 장르 선택",
            "2️⃣ 스타일 선택",
            "3️⃣ 곡 수 설정",
            "4️⃣ 금지어 설정",
            "5️⃣ 셋리스트 생성",
            "6️⃣ 가사 생성",
            "7️⃣ 결과 확인"
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
        st.header("🔑 API 상태")

        api_status = api_manager.get_status()
        for status in api_status:
            if status["is_exhausted"]:
                st.error(f"❌ {status['name']} (소진)")
            elif status["is_current"]:
                st.success(f"✅ {status['name']} (사용중)")
            else:
                st.info(f"⏳ {status['name']} (대기)")

        st.divider()
        if st.button("🔄 처음부터 다시 시작", type="secondary"):
            for key in ['current_step', 'selected_genre', 'selected_style', 'num_songs', 'banned_words', 'setlist', 'generated_lyrics']:
                if key in st.session_state:
                    del st.session_state[key]
            init_session_state()
            st.rerun()

    # STEP 1: 장르 선택
    if st.session_state.current_step == 1:
        st.header("1️⃣ 장르를 선택하세요")

        genres = style_manager.get_genres()

        for genre_name in genres:
            genre_info = style_manager.styles[genre_name]
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"""
                <div class="song-card">
                    <div style="color: #FF4B4B; font-size: 22px; font-weight: bold; margin-bottom: 8px;">{genre_name}</div>
                    <p>{genre_info.get('description', '')}</p>
                    <p><strong>사용 가능한 스타일:</strong> {len(genre_info.get('styles', {}))}개</p>
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

        genre_styles = style_manager.get_genre_styles(st.session_state.selected_genre)

        for style_name, style_info in genre_styles.items():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"""
                <div class="song-card">
                    <div style="color: #FF4B4B; font-size: 22px; font-weight: bold; margin-bottom: 8px;">{style_name}</div>
                    <p>{style_info.get('description', '')}</p>
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
            if st.button("➡️ 금지어 설정하기", type="primary"):
                st.session_state.num_songs = num_songs
                st.session_state.current_step = 4
                st.rerun()

    # STEP 4: 금지어 설정
    elif st.session_state.current_step == 4:
        st.header("4️⃣ 금지어를 설정하세요 (선택사항)")

        st.info("곡 제목과 가사에 포함되지 않기를 원하는 단어들을 입력하세요. 쉼표로 구분합니다.")
        st.markdown(f"**선택됨:** {st.session_state.selected_genre} - {st.session_state.selected_style}")
        st.markdown(f"**곡 수:** {st.session_state.num_songs}곡")

        banned_input = st.text_area(
            "금지어 입력 (쉼표로 구분)",
            placeholder="예: Streetlights, neon signs, the city hums, late night settles",
            height=100,
            label_visibility="collapsed"
        )

        st.divider()

        if banned_input.strip():
            banned_list = [word.strip() for word in banned_input.split(',') if word.strip()]
            st.session_state.banned_words = banned_list

            st.markdown("**설정된 금지어:**")
            st.markdown(" ".join([f'<span class="banned-word-tag">{word}</span>' for word in banned_list]),
                        unsafe_allow_html=True)
        else:
            st.session_state.banned_words = []
            st.info("⏭️ 금지어를 설정하지 않으셨습니다.")

        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("⬅️ 곡 수 다시 설정"):
                st.session_state.current_step = 3
                st.rerun()

        with col2:
            if st.button("➡️ 다음으로", type="primary", use_container_width=True):
                st.session_state.current_step = 5
                st.rerun()

        with col3:
            st.markdown("")

    # STEP 5: 셋리스트 생성
    elif st.session_state.current_step == 5:
        st.header("5️⃣ 셋리스트(곡 컨셉) 생성")

        st.info(f"{st.session_state.selected_style} 스타일로 {st.session_state.num_songs}곡의 컨셉을 만듭니다.")

        if st.session_state.banned_words:
            st.markdown(f"""
            <div class="warning-box">
            <strong>🚫 금지어 설정됨:</strong> {', '.join(st.session_state.banned_words)}
            </div>
            """, unsafe_allow_html=True)

        if st.button("🎲 AI 자동 생성", type="primary"):
            with st.spinner("AI가 곡 아이디어를 구상하고 있습니다..."):
                try:
                    api_key = api_manager.get_current_key()
                    if not api_key:
                        st.error("❌ 사용 가능한 API 키가 없습니다.")
                        st.stop()

                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('models/gemini-2.5-flash')

                    concept_prompt = f"""
Based on the {st.session_state.selected_style} style of {st.session_state.selected_genre}, generate {st.session_state.num_songs} unique song concepts.

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
                    st.session_state.current_step = 6
                    st.rerun()

    # STEP 6: 가사 생성
    elif st.session_state.current_step == 6:
        st.header("6️⃣ 가사 생성 중...")

        st.markdown(f"**총 {len(st.session_state.setlist)}곡 생성을 시작합니다.**")
        st.markdown(f"**스타일:** {st.session_state.selected_genre} - {st.session_state.selected_style}")

        if st.session_state.banned_words:
            st.markdown(f"""
            <div class="warning-box">
            <strong>🚫 금지어:</strong> {', '.join(st.session_state.banned_words)}
            </div>
            """, unsafe_allow_html=True)

        progress_bar = st.progress(0)
        status_text = st.empty()
        generated_songs = []

        style_prompt = style_manager.get_style_prompt(st.session_state.selected_genre, st.session_state.selected_style)

        for idx, song in enumerate(st.session_state.setlist):
            status_text.text(f"작사 중: {song['title']} ({idx + 1}/{len(st.session_state.setlist)})")

            # 금지어 포함 프롬프트
            banned_instruction = ""
            if st.session_state.banned_words:
                banned_str = ", ".join(st.session_state.banned_words)
                banned_instruction = f"\n\nCRITICAL: NEVER use these words or phrases in the title or lyrics: {banned_str}\nMake absolutely sure these banned words do NOT appear in the output."

            lyrics_prompt = f"""
{style_prompt}{banned_instruction}

SPECIFIC SONG REQUEST:
Title: {song['title']}
Theme/Concept: {song['theme']}

Write complete English lyrics for this song following all the guidelines above.
Ensure the opening lyrics are COMPLETELY DIFFERENT from typical song patterns.
Make the first verse unique and memorable with fresh, specific details.

Remember: Start directly with [Verse 1], output ONLY lyrics.
"""

            try:
                api_key = api_manager.get_current_key()
                if not api_key:
                    st.error("❌ 사용 가능한 API 키가 없습니다.")
                    break

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-2.5-flash')

                response = model.generate_content(lyrics_prompt)
                raw_lyrics = response.text.strip()
                clean_lyrics = clean_lyrics_output(raw_lyrics)

                # 🔥 제목에서도 금지어 체크
                title_has_banned, title_found = check_banned_words(song['title'], st.session_state.banned_words)

                if title_has_banned:
                    st.warning(f"""
                    ⚠️ **제목에서 금지어 감지** - {song['title']}
                    감지된 금지어: {', '.join(title_found)}
                    """)

                # 가사에서 금지어 체크
                has_banned, found_words = check_banned_words(clean_lyrics, st.session_state.banned_words)

                if has_banned:
                    st.warning(f"""
                    ⚠️ **가사에서 금지어 감지** - {song['title']}
                    감지된 금지어: {', '.join(found_words)}
                    """)

                # 반복 패턴 감지
                is_duplicate, preview = detector.is_duplicate(clean_lyrics)

                if is_duplicate:
                    st.warning(f"""
                    ⚠️ **반복 패턴 감지** - {song['title']}
                    감지된 반복: {preview}
                    """)
                else:
                    detector.add_pattern(clean_lyrics)

                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "lyrics": clean_lyrics
                })

            except Exception as e:
                error_msg = str(e)

                if "429" in error_msg or "quota" in error_msg.lower():
                    st.warning(f"⚠️ {api_manager.api_keys[api_manager.current_key_index]['name']} 할당량 초과")
                    api_manager.mark_key_exhausted(api_key)

                    next_key = api_manager.get_next_key()
                    if next_key:
                        st.info(f"🔄 {api_manager.api_keys[api_manager.current_key_index]['name']}로 전환합니다.")
                        genai.configure(api_key=next_key)
                        continue
                    else:
                        st.error("❌ 사용 가능한 API 키가 모두 소진되었습니다.")
                        break

                st.error(f"{song['title']} 생성 중 오류: {error_msg[:100]}")
                generated_songs.append({
                    "title": song['title'],
                    "theme": song['theme'],
                    "lyrics": f"가사 생성 오류: {error_msg[:50]}"
                })

            progress_bar.progress((idx + 1) / len(st.session_state.setlist))
            time.sleep(1)

        st.session_state.generated_lyrics = generated_songs

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
        st.session_state.current_step = 7
        time.sleep(1)
        st.rerun()

    # STEP 7: 결과 표시
    elif st.session_state.current_step == 7:
        st.header("7️⃣ 생성 완료! (자동 저장됨)")

        if not st.session_state.generated_lyrics:
            st.error("생성된 가사가 없습니다.")
        else:
            st.success(f"🎉 총 {len(st.session_state.generated_lyrics)}곡의 가사가 완성되어 7일간 저장되었습니다!")

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
                    st.session_state.current_step = 5
                    st.session_state.setlist = []
                    st.rerun()

            st.divider()
            st.info("💡 각 곡을 클릭하여 펼치고 가사를 확인하세요.")

            for idx, song in enumerate(st.session_state.generated_lyrics, 1):
                with st.expander(f"🎵 {idx}. {song['title']}", expanded=(idx == 1)):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown(f"**컨셉:** {song.get('theme', '')}")

                    with col2:
                        if st.button(f"📋 복사", key=f"copy_{idx}", use_container_width=True):
                            st.code(song['lyrics'], language="text")

                    st.divider()
                    st.markdown("### 📝 가사")
                    st.markdown(f"""
                    <div class="lyrics-container">
                    {song['lyrics'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)


# ==================== TAB 2: 이력 보기 ====================
with tab2:
    st.header("📚 생성 이력 보기")
    st.info("🌅 저장된 가사를 검색하고 관리할 수 있습니다. 최대 7일간 보관됩니다.")

    sessions = storage.get_all_sessions()

    if not sessions:
        st.warning("아직 저장된 이력이 없습니다.")
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            unique_genres = list(set(s["genre"] for s in sessions))
            selected_genre_filter = st.selectbox("🎭 장르 필터", ["전체"] + unique_genres)

        with col2:
            unique_styles = list(set(s["style"] for s in sessions))
            selected_style_filter = st.selectbox("🎨 스타일 필터", ["전체"] + unique_styles)

        with col3:
            search_term = st.text_input("🔍 제목 검색", placeholder="제목으로 검색...")

        filtered_sessions = [
            s for s in sessions
            if (selected_genre_filter == "전체" or s["genre"] == selected_genre_filter) and
               (selected_style_filter == "전체" or s["style"] == selected_style_filter)
        ]

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

            for session in filtered_sessions:
                session_created = datetime.fromisoformat(session["created_at"])
                session_expires = datetime.fromisoformat(session["expires_at"])
                time_left = (session_expires - datetime.now()).days

                st.markdown(f"""
                <div class="song-history-card">
                    <strong>📁 {session_created.strftime('%Y-%m-%d %H:%M')}</strong> | 
                    <strong>{session['genre']}</strong> - <strong>{session['style']}</strong> | 
                    <strong>{len(session['songs'])}곡</strong> | 
                    ⏰ <strong>{time_left}일 남음</strong>
                </div>
                """, unsafe_allow_html=True)

                col_download, col_delete = st.columns([1, 1])

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
                        key=f"download_{session['session_id']}",
                        use_container_width=True
                    )

                with col_delete:
                    if st.button("🗑️ 삭제", key=f"delete_{session['session_id']}", use_container_width=True):
                        storage.delete_session(session['session_id'])
                        st.rerun()

                st.divider()

                for idx, song in enumerate(session["songs"], 1):
                    with st.expander(f"🎵 {idx}. {song['title']}"):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.markdown(f"**컨셉:** {song.get('theme', '')}")

                        with col2:
                            if st.button(f"📋 복사", key=f"copy_history_{session['session_id']}_{idx}", use_container_width=True):
                                st.code(song['lyrics'], language="text")

                        st.divider()
                        st.markdown("### 📝 가사")
                        st.markdown(f"""
                        <div class="lyrics-container">
                        {song['lyrics'].replace(chr(10), '<br>')}
                        </div>
                        """, unsafe_allow_html=True)

                st.divider()

# ==================== 푸터 ====================
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    🎵 AI 작사 스튜디오 Pro | Gemini AI 기반 전문 작사 도구
    <br>
    <small>금지어 직접 입력 (제목+가사) | 스타일 관리 | 생성된 가사는 7일간 자동 보관 | 반복 패턴 자동 감지 | 다중 API 키 지원</small>
</div>
""", unsafe_allow_html=True)
