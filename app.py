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
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import uvicorn
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

GRADIO_MAJOR = int(gr.__version__.split(".", 1)[0])

NAMES = [n for n, _ in settings.ASK_SLOTS]

# 오른쪽 기록 패널은 기존 챗봇의 슬롯을 화면용 이름으로 보여 준다.
# 택시 슬롯은 현재 챗봇에 추출 규칙이 없으므로 빈 값으로 유지한다.
RECORD_FIELDS = [
    "장소 종류",
    "장소 이름",
    "택시 출발지",
    "택시 도착지",
    "택시 출발시간",
    "택시 종류",
]

TEMP_USER_NAME = "가영"

# 같은 문장을 계속 Gemini에 보내지 않기 위한 캐시
_seen = {}

# 마지막 API 오류 기록
LAST_ERROR = [""]


# --------------------------------------------------
# 결과 기본값
# --------------------------------------------------

def empty_result():
    return {n: "" for n in NAMES}


def empty_record():
    return {name: "" for name in RECORD_FIELDS}


def record_values(record):
    """기록 패널에 표시할 값을 정해진 순서로 반환한다."""

    return [record.get(name, "") or "-" for name in RECORD_FIELDS]


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
# 기존 채팅 결과와 오른쪽 기록 패널 연결
# --------------------------------------------------

def chat_with_record(message, history, record):
    """
    기존 chat()의 답변은 그대로 사용하고, 현재 입력에서 확인된
    기존 장소 슬롯만 세션별 기록 패널에 최신 값으로 반영한다.
    """

    response = chat(message, history)
    current = extract(message)
    updated = dict(record or empty_record())

    if current.get("종류"):
        updated["장소 종류"] = current["종류"]

    if current.get("이름"):
        updated["장소 이름"] = current["이름"]

    return (response, *record_values(updated), updated)


def reset_conversation():
    """대화와 이 브라우저 세션의 기록 패널을 함께 초기화한다."""

    record = empty_record()
    return ([], "", *record_values(record), record)


# --------------------------------------------------
# Gradio 화면 및 실행
# --------------------------------------------------

APP_CSS = """
:root {
    --page-bg: #ffffff;
    --surface: #ffffff;
    --text: #17171c;
    --muted: #93939f;
    --body-muted: #616161;
    --line: #d9d9dd;
    --line-light: #e5e7eb;
    --deep-green: #003c33;
    --dark-navy: #071829;
    --soft-stone: #eeece7;
    --pale-green: #edfce9;
    --pale-blue: #f1f5ff;
    --coral: #ff7759;
    --coral-soft: #ffad9b;
}

html,
body {
    height: 100%;
    overflow: hidden;
}

body {
    margin: 0;
    color: var(--text);
    background: var(--page-bg) !important;
    font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", sans-serif;
    letter-spacing: -0.012em;
}

.gradio-container {
    width: min(100%, 1320px) !important;
    height: 100vh !important;
    min-height: 0 !important;
    margin: 0 auto !important;
    padding: 16px 20px !important;
    overflow: hidden !important;
    color: var(--text) !important;
    background: var(--page-bg) !important;
}

#app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    height: 52px;
    margin-bottom: 12px;
    padding: 0 4px 10px;
    border-bottom: 1px solid var(--line-light);
}

#app-header h1 {
    margin: 0;
    color: var(--text);
    font-size: 1.2rem;
    font-weight: 520;
    letter-spacing: -0.04em;
}

#user-identity {
    flex: 0 0 auto;
    padding: 6px 11px;
    border: 1px solid #cde7c7;
    border-radius: 999px;
    color: var(--deep-green);
    background: var(--pale-green);
    font-size: 0.84rem;
    font-weight: 700;
}

#main-workspace {
    display: grid !important;
    grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr) !important;
    grid-template-rows: minmax(0, 1fr) !important;
    flex-wrap: nowrap !important;
    gap: 16px !important;
    height: calc(100vh - 96px) !important;
    min-height: 0 !important;
    overflow: hidden !important;
}

.workspace-card {
    min-width: 0;
    min-height: 0;
    height: 100%;
    padding: 18px !important;
    overflow: hidden !important;
    border: 1px solid var(--line-light) !important;
    border-radius: 20px !important;
    background: var(--surface) !important;
    box-shadow: none !important;
}

#chat-panel,
#record-panel {
    width: 100% !important;
    max-width: none !important;
}

#chat-panel {
    display: flex !important;
    flex-direction: column !important;
}

#record-panel {
    overflow-y: auto !important;
}

#chat-panel {
    border-top-color: #9cb9a9 !important;
}

#record-panel {
    border-top-color: #ccd4e4 !important;
}

.section-title h2 {
    margin: 0 0 4px;
    color: var(--text);
    font-size: 1.12rem;
    font-weight: 520;
    letter-spacing: -0.035em;
}

#chat-panel .section-title h2 {
    color: var(--deep-green);
}

#record-panel .section-title h2 {
    color: var(--dark-navy);
}

.section-title p {
    margin: 0 0 10px;
    color: var(--body-muted);
    font-size: 0.82rem;
}

#chatbot {
    height: calc(100vh - 270px) !important;
    min-height: 280px !important;
    max-height: calc(100vh - 270px) !important;
    overflow-y: auto !important;
    border-color: var(--line-light) !important;
    background: var(--surface) !important;
}

#chatbot .overflow-y-auto {
    overflow-y: auto !important;
}

#chat-input {
    margin-top: auto !important;
}

#chat-input textarea {
    color: var(--text) !important;
    border-color: var(--line) !important;
    background: var(--surface) !important;
    border-radius: 14px !important;
    box-shadow: none !important;
}

#chat-input textarea:focus {
    border-color: var(--deep-green) !important;
    box-shadow: none !important;
}

#chat-input button {
    border-radius: 999px !important;
    color: #ffffff !important;
    background: var(--text) !important;
}

.record-field {
    min-width: 0 !important;
    margin: 0 !important;
    color: var(--text) !important;
    font-size: 0.9rem;
    font-weight: 700;
    text-align: right;
}

.record-field p {
    margin: 0 !important;
    overflow-wrap: anywhere;
}

.record-item {
    display: grid !important;
    grid-template-columns: minmax(92px, 0.9fr) minmax(0, 1.1fr) !important;
    align-items: center !important;
    gap: 12px !important;
    min-height: 40px;
    margin: 0 !important;
    padding: 8px 2px !important;
    border: 0 !important;
    border-bottom: 1px solid #f0f0f2 !important;
    border-radius: 0 !important;
    background: transparent !important;
}

.record-item:last-of-type {
    border-bottom: 0 !important;
}

.record-label {
    color: var(--muted);
    font-size: 0.82rem;
    font-weight: 550;
}

#reset-all {
    margin-top: 14px;
    border-color: var(--coral-soft) !important;
    border-radius: 999px !important;
    color: #c54e36 !important;
    background: #ffffff !important;
    font-weight: 600 !important;
}

#reset-all:hover {
    border-color: var(--coral) !important;
    color: #9e351f !important;
    background: #fff7f5 !important;
}

@media (max-width: 720px) {
    html,
    body {
        height: auto;
        overflow: auto;
    }

    .gradio-container {
        height: auto !important;
        min-height: 100vh !important;
        padding: 12px !important;
        overflow: visible !important;
    }

    #app-header {
        height: 48px;
        margin-bottom: 10px;
    }

    #main-workspace {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        grid-template-rows: auto auto !important;
        height: auto !important;
        overflow: visible !important;
    }

    .workspace-card {
        height: auto;
        overflow: visible !important;
    }

    #chatbot {
        height: 55vh !important;
        min-height: 340px !important;
        max-height: 55vh !important;
    }

    .record-field {
        text-align: left;
    }
}
"""

APP_JS = """
() => {
    const inputSelector = "#chat-input textarea";
    const chatbotSelector = "#chatbot";
    let focusTimer = null;
    let waitingForReply = false;
    let expectedMessageCount = 0;

    const messageCount = () => {
        const chatbot = document.querySelector(chatbotSelector);
        return chatbot ? chatbot.querySelectorAll(".message-wrap").length : 0;
    };

    const clearAndFocusMessageInput = () => {
        const input = document.querySelector(inputSelector);

        if (input && !input.disabled) {
            input.value = "";
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.focus({ preventScroll: true });
            waitingForReply = false;
        }
    };

    const restoreFocusAfterReply = () => {
        if (!waitingForReply || messageCount() < expectedMessageCount) {
            return;
        }

        window.clearTimeout(focusTimer);
        focusTimer = window.setTimeout(() => {
            if (messageCount() >= expectedMessageCount) {
                clearAndFocusMessageInput();
            }
        }, 120);
    };

    const markMessageSent = () => {
        const input = document.querySelector(inputSelector);

        if (!input || !input.value.trim()) {
            return;
        }

        expectedMessageCount = messageCount() + 2;
        waitingForReply = true;
    };

    const observeChat = () => {
        const chatbot = document.querySelector(chatbotSelector);

        if (!chatbot) {
            window.setTimeout(observeChat, 100);
            return;
        }

        const observer = new MutationObserver(restoreFocusAfterReply);
        observer.observe(chatbot, {
            childList: true,
            subtree: true,
            characterData: true,
        });

        clearAndFocusMessageInput();
    };

    document.addEventListener("keydown", (event) => {
        if (
            event.target.matches(inputSelector)
            && event.key === "Enter"
            && !event.shiftKey
            && !event.isComposing
        ) {
            markMessageSent();
        }
    }, true);

    document.addEventListener("click", (event) => {
        if (event.target.closest("#chat-input button")) {
            markMessageSent();
        }
    }, true);

    observeChat();
}
"""


blocks_options = {"title": "모임 장소·택시 챗봇"}

if GRADIO_MAJOR < 6:
    blocks_options["css"] = APP_CSS
    blocks_options["js"] = APP_JS


with gr.Blocks(**blocks_options) as demo:
    record_state = gr.State(empty_record())
    record_outputs = [
        gr.Markdown(
            value="-",
            elem_classes="record-field",
            render=False,
        )
        for field in RECORD_FIELDS
    ]

    gr.HTML(
        f"""
        <header id="app-header">
            <h1>모임 장소·택시 챗봇</h1>
            <div id="user-identity" aria-label="현재 사용자">사용자: {TEMP_USER_NAME}</div>
        </header>
        """
    )

    with gr.Row(equal_height=True, elem_id="main-workspace"):
        with gr.Column(
            scale=7,
            min_width=0,
            elem_id="chat-panel",
            elem_classes="workspace-card",
        ):
            gr.Markdown(
                "## 대화\n기존 챗봇과 대화하며 장소 정보를 정할 수 있습니다.",
                elem_classes="section-title",
            )

            chatbot = gr.Chatbot(
                label="대화 내역",
                height=520,
                elem_id="chatbot",
            )
            message_options = {
                "placeholder": "메시지를 입력하세요",
                "show_label": False,
                "container": False,
                "elem_id": "chat-input",
            }

            if GRADIO_MAJOR >= 6:
                message_options.update(
                    submit_btn="보내기",
                    stop_btn=False,
                )

            message_box = gr.Textbox(
                **message_options,
            )

            chat_options = {
                "fn": chat_with_record,
                "chatbot": chatbot,
                "textbox": message_box,
                "additional_inputs": [record_state],
                "additional_outputs": [*record_outputs, record_state],
                "autofocus": True,
                "fill_height": False,
            }

            if GRADIO_MAJOR < 6:
                chat_options.update(
                    submit_btn="보내기",
                    stop_btn=False,
                )

            chat_ui = gr.ChatInterface(**chat_options)

        with gr.Column(
            scale=4,
            min_width=0,
            elem_id="record-panel",
            elem_classes="workspace-card",
        ):
            gr.Markdown(
                "## 현재까지 기록된 내용\n대화에서 확인된 최신 값을 보여줍니다.",
                elem_classes="section-title",
            )

            for field, output in zip(RECORD_FIELDS, record_outputs):
                with gr.Group(elem_classes="record-item"):
                    gr.HTML(
                        f'<div class="record-label">{field}</div>'
                    )
                    output.render()

            reset_button = gr.Button(
                "처음부터 다시",
                variant="secondary",
                elem_id="reset-all",
            )

    reset_button.click(
        fn=reset_conversation,
        inputs=None,
        outputs=[chat_ui.chatbot, chat_ui.textbox, *record_outputs, record_state],
        show_progress="hidden",
    )


# --------------------------------------------------
# index.html과 챗봇을 같은 서버에서 연결
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
web_app = FastAPI(title="MEET & RIDE")


@web_app.get("/", include_in_schema=False)
def index_page():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@web_app.get("/index.html", include_in_schema=False)
def index_html_page():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@web_app.get("/manual.html", include_in_schema=False)
def manual_page():
    return FileResponse(os.path.join(BASE_DIR, "manual.html"))


@web_app.post("/api/chat")
def chat_api(payload: dict):
    message = str(payload.get("message", "")).strip()

    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    history = payload.get("history", [])
    if not isinstance(history, list):
        history = []

    received_record = payload.get("record", {})
    if not isinstance(received_record, dict):
        received_record = {}

    record = {
        field: str(received_record.get(field, "")).strip()
        for field in RECORD_FIELDS
    }

    result = chat_with_record(message, history, record)

    return {
        "response": result[0],
        "record": result[-1],
    }


web_app = gr.mount_gradio_app(web_app, demo, path="/gradio")


if __name__ == "__main__":
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    uvicorn.run(web_app, host="127.0.0.1", port=server_port)
