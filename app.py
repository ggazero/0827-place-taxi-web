# 이 파일은 열지 않습니다. settings.py 만 바꿉니다.
import warnings

# 켤 때마다 뜨는 deprecated 경고를 감춘다.
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="gradio")

import sys

# Windows 터미널 한글 깨짐 방지
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import re

import gradio as gr
import google.generativeai as genai
from dotenv import load_dotenv
import settings


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".env"
    )
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-3.5-flash-lite")

NAMES = [n for n, _ in settings.ASK_SLOTS]

# 같은 문장을 계속 Gemini에 보내지 않기 위한 캐시
_seen = {}

# 마지막 API 오류 기록
LAST_ERROR = [""]


# --------------------------------------------------
# 결과 기본값
# --------------------------------------------------

def empty_result():
    return {n: "" for n in NAMES}


# --------------------------------------------------
# 확실한 단어는 Gemini 없이 직접 인식
# --------------------------------------------------

def direct_extract(text):
    """
    쇼핑 / 관람 / 체험처럼
    사용자가 명확하게 말한 값은 Gemini에 맡기지 않고 직접 인식한다.
    """

    result = empty_result()

    text = str(text).strip()

    if "종류" in NAMES:
        found = []

        for value in ["쇼핑", "관람", "체험"]:
            if value in text:
                found.append(value)

        # 한 가지 종류만 명확히 등장했을 때만 저장
        if len(found) == 1:
            result["종류"] = found[0]

    return result


# --------------------------------------------------
# 사용자 입력에서 슬롯 추출
# --------------------------------------------------

def extract(text):
    text = str(text).strip()

    # ----------------------------------------------
    # 1. 쇼핑 / 관람 / 체험 단답은 바로 처리
    # Gemini가 첫 입력을 놓치는 문제 방지
    # ----------------------------------------------

    if text in ["쇼핑", "관람", "체험"]:
        got = empty_result()

        if "종류" in NAMES:
            got["종류"] = text

        return got

    key = (text, tuple(NAMES))

    # 이미 정상적으로 분석한 문장이면 재사용
    if key in _seen:
        return dict(_seen[key])

    # 직접 판단 가능한 값
    direct = direct_extract(text)

    # Gemini 분석
    got, success = _extract_once(text)

    # 직접 확인된 값이 있으면 Gemini보다 우선
    for k, v in direct.items():
        if v:
            got[k] = v

    # API 호출 자체가 정상적으로 끝났을 때만 캐시한다.
    # API 오류로 빈 결과가 나온 것을 영구 저장하지 않는다.
    if success:
        _seen[key] = dict(got)

    return got


# --------------------------------------------------
# Gemini로 슬롯 추출
# --------------------------------------------------

def _extract_once(text):
    """
    유저가 친 말 한 개에서 필요한 칸을 뽑는다.
    못 찾으면 빈 문자열로 둔다.
    """

    LAST_ERROR[0] = ""

    prompt = (
        "다음 사용자 문장에서 필요한 정보를 찾아 JSON으로만 답하세요.\n"
        "설명은 절대 쓰지 마세요.\n"
        "찾지 못한 항목은 빈 문자열로 두세요.\n\n"

        f"찾을 항목: {', '.join(NAMES)}\n\n"

        "중요한 규칙:\n"
        "1. '종류'는 쇼핑, 관람, 체험 중 사용자가 원하는 활동을 뜻합니다.\n"
        "2. 장소의 업종이나 시설 종류를 '종류'에 넣지 마세요.\n"
        "3. 예를 들어 사용자가 '코엑스'라고 말했다고 해서 "
        "'종류'를 '컨벤션센터'로 바꾸면 안 됩니다.\n"
        "4. 사용자가 쇼핑이라고 말했다면 종류는 '쇼핑'입니다.\n"
        "5. 이름은 장소 이름입니다. 예: 코엑스, 경복궁, 롯데월드\n"
        "6. 지역은 장소를 통해 확실하게 알 수 있을 때만 넣어도 됩니다.\n"
        "7. 사용자가 말하지 않았거나 확실하지 않은 값은 빈 문자열로 두세요.\n\n"

        "반드시 아래 형태의 JSON만 출력하세요.\n"
        f"{json.dumps({n: '' for n in NAMES}, ensure_ascii=False)}\n\n"

        f"사용자 문장: {text}"
    )

    try:
        raw = model.generate_content(prompt).text

        raw = raw.replace("```json", "")
        raw = raw.replace("```", "")

        m = re.search(r"\{.*\}", raw, re.S)

        if m:
            got = json.loads(m.group(0))
        else:
            got = {}

        result = {
            n: str(got.get(n, "")).strip()
            for n in NAMES
        }

        return result, True

    except Exception as e:
        LAST_ERROR[0] = (
            f"{type(e).__name__}: {str(e)[:120]}"
        )

        return empty_result(), False


# --------------------------------------------------
# Gradio history에서 사용자 발화만 추출
# --------------------------------------------------

def _user_said(history):
    """
    Gradio 버전에 따라 history 형식이 다를 수 있어서
    사용자 발화만 안전하게 추출한다.
    """

    out = []

    for h in history:

        if isinstance(h, dict):

            if h.get("role") == "user":
                out.append(
                    str(h.get("content", ""))
                )

        else:

            try:
                out.append(str(h[0]))
            except Exception:
                pass

    return out


# --------------------------------------------------
# HISTORY_TURNS 범위 안의 슬롯 모으기
# --------------------------------------------------

def merge(history):
    """
    최근 HISTORY_TURNS 범위에서 슬롯을 모은다.

    중요한 변경:
    이미 채운 값은 뒤의 문장이 덮어쓰지 않는다.
    """

    box = {n: "" for n in NAMES}

    said = _user_said(history)

    if settings.HISTORY_TURNS > 0:
        recent = said[-settings.HISTORY_TURNS:]
    else:
        recent = []

    for u in recent:

        extracted = extract(u)

        for k, v in extracted.items():

            # 기존 값이 비어 있을 때만 넣는다.
            # 쇼핑 → 코엑스 입력 후
            # 쇼핑이 컨벤션센터로 바뀌는 것 방지
            if v and not box[k]:
                box[k] = v

    return box


# --------------------------------------------------
# 전체 대화에서 한 번이라도 나온 슬롯 확인
# --------------------------------------------------

def all_seen(history):

    seen = {n: "" for n in NAMES}

    for u in _user_said(history):

        extracted = extract(u)

        for k, v in extracted.items():

            # 처음 들어온 값을 유지
            if v and not seen[k]:
                seen[k] = v

    return seen


# --------------------------------------------------
# 실제 채팅 함수
# --------------------------------------------------

def chat(message, history):

    # 이전 대화에서 슬롯 복구
    box = merge(history)

    # 전체 대화에서 한 번이라도 나온 값
    ever = all_seen(history)

    # 현재 사용자가 입력한 문장 분석
    current = extract(message)

    # ----------------------------------------------
    # 현재 입력 적용
    # ----------------------------------------------

    for k, v in current.items():

        if not v:
            continue

        # 이미 현재 범위 안에서 값이 있으면 덮어쓰지 않는다.
        if not box[k]:
            box[k] = v

        # 전체 기록도 최초 값 유지
        if not ever[k]:
            ever[k] = v

    # ----------------------------------------------
    # 아직 비어 있는 항목 확인
    # ----------------------------------------------

    missing = [
        n for n in NAMES
        if not box[n]
    ]

    filled = len(NAMES) - len(missing)

    # ----------------------------------------------
    # 상태 표시
    # ----------------------------------------------

    head = (
        f"채운 칸: {filled}/{len(NAMES)}  "
        f"(ASK_STYLE={settings.ASK_STYLE}, "
        f"HISTORY_TURNS={settings.HISTORY_TURNS})\n"
        + " | ".join(
            (
                f"{n}: {box[n]}"
                if box[n]
                else (
                    f"{n}: - (범위 밖으로 밀림)"
                    if ever[n]
                    else f"{n}: -"
                )
            )
            for n in NAMES
        )
        + "\n"
        + "-" * 46
        + "\n"
    )

    # ----------------------------------------------
    # 아직 필요한 값이 있을 때
    # ----------------------------------------------

    if missing:

        ask = dict(settings.ASK_SLOTS)

        if settings.ASK_STYLE == "all_at_once":

            body = (
                "장소를 찾으려면 아래 내용을 알려 주세요.\n"
                + "\n".join(
                    f"- {n}: {ask[n]}"
                    for n in missing
                )
            )

        else:

            body = ask[missing[0]]

        # Gemini 오류가 있었으면 터미널에서 확인 가능
        if LAST_ERROR[0]:
            print("Gemini 오류:", LAST_ERROR[0])

        return head + body

    # ----------------------------------------------
    # 모든 값이 채워졌을 때
    # ----------------------------------------------

    auto = "\n".join(
        f"- {k}: {v}"
        for k, v in settings.AUTO_SLOTS.items()
    )

    return (
        head
        + "장소를 찾았습니다.\n"
        + "\n".join(
            f"- {n}: {box[n]}"
            for n in NAMES
        )
        + "\n"
        + auto
    )


# --------------------------------------------------
# Gradio 실행
# --------------------------------------------------

demo = gr.ChatInterface(chat)
demo.launch()