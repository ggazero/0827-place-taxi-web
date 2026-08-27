# 환경이 제대로 됐는지 확인합니다. 고치지 않아도 됩니다.
import os
import sys

# Windows 터미널은 한글을 cp949 로 그려서 안내문이 깨진다(260827 실측).
# 이 두 줄이 있어야 오류 메시지를 학생이 읽을 수 있다.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL = "gemini-3.5-flash-lite"

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import dotenv
    import google.generativeai as genai
except ImportError as e:
    print(f"설치 안 됨: {e.name}  -> 4번을 다시 하세요")
    sys.exit(1)

dotenv.load_dotenv()
key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not key:
    print("키 없음  -> .env 라는 이름이 맞는지, 그 안에 키가 있는지 보세요")
    sys.exit(1)
if key.strip() != key or key.startswith(("'", '"')):
    print("키 앞뒤에 빈칸이나 따옴표가 있습니다  -> 지우고 다시 하세요")
    sys.exit(1)
if "여기에" in key or "API" in key.upper()[:5]:
    print("예시 문구가 그대로 있습니다  -> 자기 키로 바꾸세요")
    sys.exit(1)
print(f"키 OK  길이 {len(key)}")

genai.configure(api_key=key)
try:
    r = genai.GenerativeModel(MODEL).generate_content("한 단어로 답: 하늘색은?")
    print(f"모델 OK  {MODEL}  응답: {r.text.strip()[:20]}")
except Exception as e:
    msg = str(e)
    if "429" in msg or "quota" in msg.lower() or "exhaust" in msg.lower():
        print("429  1분 안에 15번을 넘겼습니다. 화면에 적힌 초만큼 기다렸다 다시 하세요")
        print("      한도는 모델마다 따로입니다. Continue 가 같은 모델이면 서로 잡아먹습니다")
    elif "API key not valid" in msg or "API_KEY_INVALID" in msg:
        print("키가 맞지 않습니다  -> .env 의 키를 다시 복사해 넣으세요")
    elif "404" in msg or "not found" in msg.lower():
        print(f"모델 이름을 못 찾습니다: {MODEL}  -> 강사에게 알려주세요")
    else:
        print(f"모델 실패: {type(e).__name__}  {msg[:100]}")
    sys.exit(1)
