# 이 폴더에서 AI 가 할 일 (VS Code 실습)

학생은 폴더를 열고 **"실행해줘"** 한 마디만 한다. 아래를 AI 가 대신 한다.
안내 문서가 여러 개면 학생에게 읽으라 하지 말고 AI 가 읽는다.

**이 회차에 필요한 값은 전부 `_env.yaml` 에 있다.** 아래 대문자 이름은 그 파일에서 읽는다.
`_env.yaml` 이 없으면 학생에게 알리고 멈춘다.

## 규칙 0 - 실패를 성공이라 말하지 않는다

명령을 돌린 뒤 **종료 코드와 출력을 먼저 본다.** `command not found`, 0이 아닌 exit code,
`Traceback`, `ImportError`, `No such file` 중 하나라도 있으면 **실패다.** 그 상태에서
"성공적으로 실행되었습니다" 라고 쓰지 않는다. 무엇이 실패했는지 한 줄로 말하고 멈춘다.

## 규칙 0-1 - 코드에 마크다운 표시를 남기지 않는다

파일을 쓸 때 백틱 세 개나 ` ```python ` 같은 표시를 코드 안에 남기지 않는다.
남기면 `SyntaxError: invalid syntax` 가 난다. 파일을 쓴 뒤 첫 줄과 끝 줄을 눈으로 확인한다.

## 1. 지금 이 기계가 어떤 상태인지 먼저 본다

묻지 말고 확인한다. 확인한 것에 맞춰 아래 단계의 명령을 고른다.

- **운영체제** - Windows 인가 macOS 인가
- **파이썬이 어느 것인지** - 이름이 아니라 실제 경로를 본다
  - macOS `which python3` / Windows `where.exe python`
  - `WindowsApps\python3.exe` 가 나오면 **Microsoft Store 스텁**이다. 파이썬이 아니다. `python` 을 쓴다
  - 경로에 다른 프로그램 이름이 든 `venv\Scripts\python.exe` 가 나오면 **다른 도구의 가상환경**이 PATH 를 잡은 것이다. 그 안에 pip 가 없을 수 있다
  - `(base)` 프롬프트면 **conda 환경**이다. 그대로 두고 아래 3번에서 별도 가상환경을 만든다
- **Python 확장** - 설치 권장 팝업이 뜨면 설치한다. 없으면 인터프리터가 안 잡힌다
- **폴더** - `ENTRY` 파일이 보이는가. 없으면 하위 폴더를 한 단계 찾는다
- **폴더 이름이 `이름 2`, `이름 3`, `이름-now` 로 끝나면** 압축을 여러 번 푼 것이다. 학생에게 알리고 가장 최근 것 하나만 쓴다
- `VENV_DIR` 가 이미 있는가. 있으면 3번을 건너뛴다

## 2. 명령을 고를 때

- **`pip` 를 단독으로 치지 않는다.** macOS 에 `pip` 가 없는 경우가 많다. 항상 `python -m pip` 형태로 쓴다
- 가상환경 폴더는 `VENV_DIR` 이름 그대로다. **점이 앞에 붙는다**
- **`activate` 를 쓰지 않는다.** 아래 경로를 매번 그대로 적어 실행한다. 터미널을 새로 열어도, Windows 실행 정책에 막히지도 않는다
  - Windows `.\VENV_DIR\Scripts\python.exe`
  - macOS `./VENV_DIR/bin/python`
- 명령을 여러 줄 보낼 때 **한 줄씩 보낸다.** 붙으면 `app.pysource` 같은 없는 파일을 찾는다

## 3. 상자와 pip

없으면 만들고, pip 를 최신으로 올린다. `PYTHON_MIN` 미만이면 이 단계를 반드시 한다.

- Windows `python -m venv VENV_DIR` -> `.\VENV_DIR\Scripts\python.exe -m pip install --upgrade pip`
- macOS `python3 -m venv VENV_DIR` -> `./VENV_DIR/bin/python -m pip install --upgrade pip`

`externally-managed-environment` 가 뜨면 **가상환경 밖에서 설치하려 한 것이다.** `--break-system-packages` 를 쓰지 말고 위 순서대로 상자를 먼저 만든다.

## 4. 설치

`PACKAGES` 목록 그대로, **상자 안 파이썬으로** 설치한다. 부등호를 지우거나 버전을 바꾸지 않는다.
`WARNING: ... which is not on PATH` 가 뜨면 상자 밖에 설치된 것이다. 2번 경로로 다시 한다.

## 5. 확인

`IMPORT_CHECK` 목록을 **상자 안 파이썬으로** import 해서 통과해야 다음으로 간다.
여기서 `ModuleNotFoundError` 가 나면 설치한 파이썬과 실행하는 파이썬이 다른 것이다. 경로를 맞춘다.

## 6. 열쇠

`.env` 는 폴더에 **이미 있다.** 새로 만들거나 이름을 바꾸지 않는다.
값이 비어 있는지 먼저 본다 - 남의 키가 들어 있으면 지우고 학생에게 알린다. 그 다음 이 한 줄만 요청한다:

"`.env` 를 열어 `REQUIRED_KEYS` 뒤에 본인 키를 붙여 넣고 저장해 주세요."

**변수 이름을 바꾸지 않는다.** 이름 오타로 20분을 잃은 사례가 있다.

## 7. 동작 확인

`check.py` 를 돌린다. `키 OK` 와 `모델 OK` 두 줄이 나와야 한다.

## 8. 실행

`ENTRY` 를 실행한다. 출력에 `EXPECT_URL` 이 든 줄이 나오면 그 주소를 학생에게 알린다.
그 위의 경고 줄은 정상이다. 주소가 이미 쓰이고 있으면 포트를 바꿔 다시 띄우고 새 주소를 알린다.

## 학생이 막혔을 때

무엇이 잘못됐는지 묻지 말고 **몇 번에서 멈췄는지**만 묻는다. 그 단계만 다시 한다.
증상별 대응은 같은 폴더의 `_troubleshoot.md` 를 읽는다.

## 손대지 않는 것

`_env.yaml` 의 값 / `sys.platform == "win32"` 두 줄 / `VENV_DIR` 경로.
`.env` 는 읽지도 쓰지도 커밋하지도 않는다. `ENV_EXAMPLE` 만 다룬다.
설명은 한국어로 하고 영어 약어는 처음 나올 때 괄호로 푼다.
