import requests
import json
import time

# 당신이 복사한 완벽한 쿠키를 여기에 직접 입력
SUNO_COOKIE = 'ssr_bucket=34; statsig_stable_id=12ddcaa8-683a-48b8-974b-9ed14f809c7a; suno_device_id=314ac136-abfa-41b1-af08-bbff2ab2ad86; _gcl_au=1.1.802899375.1772978499; singular_device_id=8def851f-c7cc-49cb-b556-14ae1050a6d9; _axwrt=f976e00a-c678-4e32-98a1-fbff877cf844; _fbp=fb.1.1772978499296.69369689545543448; _ga=GA1.1.2022331954.1772978499; _twpid=tw.1772978499359.848509111940835540; IR_gbd=suno.com; _sp_ses.e685=*; _tt_enable_cookie=1; _ttp=01KK6W1VXVPV9GWV43RV0E85PQ_.tt.1; _scid=N35DdMTZj0VQUtyDgwpRYVqDD_ie18Le; _ScCbts=%5B%5D; ajs_anonymous_id=314ac136-abfa-41b1-af08-bbff2ab2ad86; _clck=gh344c%5E2%5Eg46%5E0%5E2258; _sctr=1%7C1772895600000; __session=eyJhbGciOiJSUzI1NiIsImtpZCI6InN1bm8tYXBpLXJzMjU2LWtleS0xIiwidHlwIjoiSldUIn0.eyJzdW5vLmNvbS9jbGFpbXMvdXNlcl9pZCI6ImRmOWE1ZDU1LTQ1YTAtNDAzYi1iNWJhLTIwNjgyMWRlYjM3ZCIsImh0dHBzOi8vc3Vuby5haS9jbGFpbXMvY2xlcmtfaWQiOiJ1c2VyXzJvMndUVkZrU3ZCbnBFR3M2N1lnMHRQQzZmbyIsInN1bm8uY29tL2NsYWltcy90b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzcyOTgyMjA2LCJhdWQiOiJzdW5vLWFwaSIsInN1YiI6InVzZXJfMm8yd1RWRmtTdkJucEVHczY3WWcwdFBDNmZvIiwiYXpwIjoiaHR0cHM6Ly9zdW5vLmNvbSIsImZ2YSI6WzAsLTFdLCJpYXQiOjE3NzI5Nzg2MDYsImlzcyI6Imh0dHBzOi8vYXV0aC5zdW5vLmNvbSIsImppdCI6IjBlYmY2ZDUxLTkwZWUtNDI2Ny1hZGE5LTcyZjg1NjIxNTdhMyIsInZpeiI6ZmFsc2UsInNpZCI6InNlc3Npb25fYzlmMjEyMjBiNTk0NGZjYjAzNzMzNiIsInN1bm8uY29tL2NsYWltcy9lbWFpbCI6Inlvb25lZTMyQGdtYWlsLmNvbSIsImh0dHBzOi8vc3Vuby5haS9jbGFpbXMvZW1haWwiOiJ5b29uZWUzMkBnbWFpbC5jb20ifQ.nLUuOdFWkq349aWtTwNWRF2x8EtVT_7cTadVdRpO7zoItSuYOvEaKG6T0mOM_gqCh7misHvEXDdP61NjpSJTuqOe1XUfCST4hudrkDiAAkFPu36cwVdDGbxNVA0lFAG6ygnKrStee9XJrZBF77g5IKW76KK2d-FJ5LlfQ_teYVaSsMLp65b4hXo50ck22lFAvUheIVmKWHd0rfH1XtFIUdQYK1hSoCXGZowQwF7hlROVkYgj37xRGxEoxdNy-_R1eFljipS0K9xjoWxNaVb3WUiODaTfgNCQKW0d4rcBo6g9dANb_4AVZQzonymibn3bu3W0H34iS8RodRMo8no85w; __client_uat=1772978518; __client_uat_Jnxw-muT=1772978518; clerk_active_context=session_c9f21220b5944fcb037336:; ab.storage.userId.b67099e5-3183-4de8-8f8f-fdea9ac93d15=g%3Adf9a5d55-45a0-403b-b5ba-206821deb37d%7Ce%3Aundefined%7Cc%3A1772978521252%7Cl%3A1772978521254; ab.storage.deviceId.b67099e5-3183-4de8-8f8f-fdea9ac93d15=g%3A703a7600-b751-4360-b66e-9f48c9acd1c9%7Ce%3Aundefined%7Cc%3A1772978521255%7Cl%3A1772978521255; has_logged_in_before=true; ax_visitor=%7B%22firstVisitTs%22%3A1772978499383%2C%22lastVisitTs%22%3Anull%2C%22currentVisitStartTs%22%3A1772978499383%2C%22ts%22%3A1772978606722%2C%22visitCount%22%3A1%7D; _scid_r=Mv5DdMTZj0VQUtyDgwpRYVqDD_ie18LeTvJuog; IR_46384=1772978606832%7C0%7C1772978606832%7C%7C; _ga_7B0KEDD7XP=GS2.1.s1772978499$o1$g1$t1772978607$j12$l0$h0$d7txkiG_BnzhoA_mlWoEU36s0wTgRcbHaJA; tatari-cookie-test=79314141; tatari-session-cookie=949ff0fb-9744-eabe-9190-71be8e2f7ca9; _uetsid=53f5ee801af711f1995c7dd0ddf7decb|g3hmi7|2|g46|0|2258; __session_Jnxw-muT=eyJhbGciOiJSUzI1NiIsImtpZCI6InN1bm8tYXBpLXJzMjU2LWtleS0xIiwidHlwIjoiSldUIn0.eyJzdW5vLmNvbS9jbGFpbXMvdXNlcl9pZCI6ImRmOWE1ZDU1LTQ1YTAtNDAzYi1iNWJhLTIwNjgyMWRlYjM3ZCIsImh0dHBzOi8vc3Vuby5haS9jbGFpbXMvY2xlcmtfaWQiOiJ1c2VyXzJvMndUVkZrU3ZCbnBFR3M2N1lnMHRQQzZmbyIsInN1bm8uY29tL2NsYWltcy90b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzcyOTgyMjA2LCJhdWQiOiJzdW5vLWFwaSIsInN1YiI6InVzZXJfMm8yd1RWRmtTdkJucEVHczY3WWcwdFBDNmZvIiwiYXpwIjoiaHR0cHM6Ly9zdW5vLmNvbSIsImZ2YSI6WzAsLTFdLCJpYXQiOjE3NzI5Nzg2MDYsImlzcyI6Imh0dHBzOi8vYXV0aC5zdW5vLmNvbSIsImppdCI6IjBlYmY2ZDUxLTkwZWUtNDI2Ny1hZGE5LTcyZjg1NjIxNTdhMyIsInZpeiI6ZmFsc2UsInNpZCI6InNlc3Npb25fYzlmMjEyMjBiNTk0NGZjYjAzNzMzNiIsInN1bm8uY29tL2NsYWltcy9lbWFpbCI6Inlvb25lZTMyQGdtYWlsLmNvbSIsImh0dHBzOi8vc3Vuby5haS9jbGFpbXMvZW1haWwiOiJ5b29uZWUzMkBnbWFpbC5jb20ifQ.nLUuOdFWkq349aWtTwNWRF2x8EtVT_7cTadVdRpO7zoItSuYOvEaKG6T0mOM_gqCh7misHvEXDdP61NjpSJTuqOe1XUfCST4hudrkDiAAkFPu36cwVdDGbxNVA0lFAG6ygnKrStee9XJrZBF77g5IKW76KK2d-FJ5LlfQ_teYVaSsMLp65b4hXo50ck22lFAvUheIVmKWHd0rfH1XtFIUdQYK1hSoCXGZowQwF7hlROVkYgj37xRGxEoxdNy-_R1eFljipS0K9xjoWxNaVb3WUiODaTfgNCQKW0d4rcBo6g9dANb_4AVZQzonymibn3bu3W0H34iS8RodRMo8no85w; _sp_id.e685=abc6d6a2-c38f-4653-80e3-ba0fb15830ed.1772978499.1.1772978607..c9eaf049-9d90-4e84-b346-73c7cf2a869c..cc03c0cf-1c72-422b-8f9a-ee5d477b3538.1772978499403.5; ttcsid=1772978499521::k8v8gtXyL0jtx4tkpX8s.1.1772978607543.0; ttcsid_CT67HURC77UB52N3JFBG=1772978499521::c2hUNnkVrsIOQ2zltysU.1.1772978607543.1; ab.storage.sessionId.b67099e5-3183-4de8-8f8f-fdea9ac93d15=g%3Ab8c89d4b-b675-47b9-9aee-82b95bc00104%7Ce%3A1772980407825%7Cc%3A1772978521254%7Cl%3A1772978607825; _uetvid=53f5e0a01af711f18d83db4f1a52f95f|eko5af|1772978608103|4|1|bat.bing.com/p/conversions/c/j; _clsk=1i6z7sr%5E1772978608944%5E4%5E0%5Ej.clarity.ms%2Fcollect; _dd_s=aid=3aace256-1c53-4a71-a829-aeab9c3a3eb5&rum=0&expire=1772979746357'


def test_suno_direct():
    """suno-api 없이 직접 Suno API 테스트"""

    headers = {
        'Cookie': SUNO_COOKIE,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Origin': 'https://suno.com',
        'Referer': 'https://suno.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
    }

    # 1단계: 크레딧 확인 (인증 테스트)
    print("🔄 1단계: 직접 Suno API 크레딧 확인")
    try:
        response = requests.get(
            'https://studio-api.suno.ai/api/billing/info/',
            headers=headers,
            timeout=10
        )
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            credit_info = response.json()
            print(f"   ✅ 인증 성공! 크레딧: {credit_info}")

            # 2단계: 음악 생성 테스트
            print("\n🎵 2단계: 직접 음악 생성 테스트")

            payload = {
                "prompt": "[Verse 1]\nDirect API test\nNo more middleware\n\n[Chorus]\nFinally working\nDirect connection",
                "tags": "R&B, Hiphop, Groovy Beat, indie, Urban Soul",
                "title": "Direct API Success",
                "make_instrumental": False,
                "wait_audio": False,
                "mv": "chirp-v3-5"
            }

            gen_response = requests.post(
                'https://studio-api.suno.ai/api/custom_generate/',
                headers=headers,
                json=payload,
                timeout=30
            )

            print(f"   Status: {gen_response.status_code}")
            if gen_response.status_code == 200:
                result = gen_response.json()
                print(f"   ✅ 음악 생성 성공! 생성된 곡 수: {len(result)}")
                for i, track in enumerate(result, 1):
                    print(f"      곡 {i}: ID={track.get('id')}, Status={track.get('status')}")
                return True, result
            else:
                print(f"   ❌ 음악 생성 실패: {gen_response.text[:200]}")
                return False, None

        elif response.status_code == 401:
            print("   ❌ 인증 실패 (401): 쿠키가 만료되었습니다")
            return False, None
        else:
            print(f"   ❌ 예상치 못한 응답: {response.status_code} - {response.text[:200]}")
            return False, None

    except Exception as e:
        print(f"   ❌ 연결 오류: {e}")
        return False, None


def generate_music_direct(title, lyrics, style):
    """suno-api 대신 사용할 직접 음악 생성 함수"""

    headers = {
        'Cookie': SUNO_COOKIE,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Origin': 'https://suno.com',
        'Referer': 'https://suno.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
    }

    payload = {
        "prompt": lyrics[:2500],
        "tags": "R&B, Hiphop, Groovy Beat, indie, Urban Soul",
        "title": title,
        "make_instrumental": False,
        "wait_audio": False,
        "mv": "chirp-v3-5"
    }

    try:
        response = requests.post(
            'https://studio-api.suno.ai/api/custom_generate/',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ids = [item.get('id') for item in result if item.get('id')]
            return ids, None
        else:
            return None, f"Suno API 오류: {response.status_code} - {response.text[:200]}"

    except Exception as e:
        return None, f"요청 실패: {str(e)}"


def check_music_status_direct(audio_ids):
    """직접 음악 생성 상태 확인"""

    headers = {
        'Cookie': SUNO_COOKIE,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Origin': 'https://suno.com',
        'Referer': 'https://suno.com/'
    }

    try:
        ids_str = ','.join(audio_ids)
        response = requests.get(
            f'https://studio-api.suno.ai/api/feed/?ids={ids_str}',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"상태 확인 실패: {response.status_code}"

    except Exception as e:
        return None, f"상태 확인 오류: {str(e)}"


if __name__ == "__main__":
    print("🚀 suno-api 우회 직접 테스트 시작\n")
    success, result = test_suno_direct()

    if success:
        print("\n🎉 성공! 이제 Streamlit 앱에서 직접 API 함수들을 사용할 수 있습니다.")
        print("💡 다음 단계: 기존 generate_music_with_suno 함수를 generate_music_direct로 교체하세요.")
    else:
        print("\n❌ 직접 API도 실패. 쿠키 갱신이 필요할 수 있습니다.")
