import requests
import json

SUNO_API_URL = "http://localhost:3000"


def test_suno_connection():
    """Suno API 연결 및 기능 테스트"""

    # 1. 연결 테스트
    print("🔄 1단계: Suno API 서버 연결 테스트")
    try:
        health_resp = requests.get(f"{SUNO_API_URL}/api/get_limit", timeout=5)
        print(f"   ✅ 연결 성공: {health_resp.status_code}")
        if health_resp.status_code == 200:
            credit_info = health_resp.json()
            print(f"   💰 크레딧: {credit_info}")
        else:
            print(f"   ❌ 연결 실패: {health_resp.text}")
            return
    except Exception as e:
        print(f"   ❌ 연결 오류: {e}")
        return

    # 2. 음악 생성 테스트 (고정 태그 적용)
    print("\n🎵 2단계: 음악 생성 테스트 (고정 태그)")

    test_payload = {
        "prompt": "[Verse 1]\nTest lyrics for debugging\nSimple urban R&B style\n\n[Chorus]\nThis is just a test\nTo check if Suno works",
        "tags": "R&B, Hiphop, Groovy Beat, indie, Urban Soul",  # 고정 태그
        "title": "Debug Test Song",
        "make_instrumental": False,
        "wait_audio": False,
        "mv": "chirp-v3-5"
    }

    print(f"   📤 요청 데이터:")
    print(f"      Tags: {test_payload['tags']}")
    print(f"      Title: {test_payload['title']}")
    print(f"      Model: {test_payload['mv']}")

    try:
        response = requests.post(
            f"{SUNO_API_URL}/api/custom_generate",
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        print(f"\n   📥 응답:")
        print(f"      Status: {response.status_code}")
        print(f"      Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 성공! 생성된 곡 수: {len(result)}")
            for i, item in enumerate(result, 1):
                print(f"      곡 {i}: ID={item.get('id')}, Status={item.get('status')}")
        else:
            print(f"   ❌ 실패: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"   ❌ 요청 오류: {e}")


if __name__ == "__main__":
    test_suno_connection()
