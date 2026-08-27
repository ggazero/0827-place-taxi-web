# 막혔을 때 - 증상별 대응

`AGENTS-vscode.md` 가 이 파일을 가리킨다. 학생이 막혔을 때만 읽는다.
전부 260827 에 D18-D27 캡처 431장과 기계 2대에서 실제로 관측된 것이다.

무엇이 잘못됐는지 묻지 말고 **몇 번에서 멈췄는지**만 묻는다. 그 단계만 다시 한다.

| 화면에 뜬 것 | 무엇인가 | 어떻게 |
|---|---|---|
| `command not found: python` | macOS 는 `python3` 다 | `python3` 또는 상자 안 경로 |
| `command not found: pip` | macOS 에 `pip` 가 없다 | `python3 -m pip` |
| `command not found: source:` | 콜론까지 붙여넣었다 | 그 줄만 다시 친다 |
| `no such file: venv/bin/activate` | 점이 빠졌거나 상자가 없다 | `VENV_DIR` 이름으로 다시 만든다 |
| `ModuleNotFoundError` | 설치한 파이썬과 실행하는 파이썬이 다르다 | 상자 안 경로로 실행 |
| `externally-managed-environment` | 상자 밖에 설치하려 했다 | 3번부터 다시 |
| `... is not on PATH` | 상자 밖 사용자 영역에 설치됐다 | 상자 안 경로로 다시 설치 |
| `Failed building wheel for cryptography` | pip 가 낡았다 | 3번을 하고 4번을 다시 |
| `NotOpenSSLWarning ... LibreSSL` | 경고다. 멈추지 않는다 | 그대로 진행 |
| `SyntaxError: invalid syntax` | 파일에 마크다운 표시가 남았다 | 그 줄을 지운다 |
| `[Errno 2] ... app.pysource` | 명령 두 줄이 붙었다 | 한 줄씩 다시 |
| `429` | 세 종류다 - 아래 참고 | |
| `Continue (config error)` | 설정 파일에 문서가 두 개 붙었다 | 위쪽 한 벌만 남긴다. **덮어쓰기**로 붙인다 |
| `No models configured` | 설정의 apiKey 가 비어 있다 | 값을 채우거나 그 모델 블록을 지운다 |
| `Set-ExecutionPolicy` 를 매번 친다 | 실행 정책이 `activate.ps1` 을 막는다 | `activate` 를 쓰지 않는다. 2번 경로로 직접 실행 |
| 한글이 깨진다 | Windows 화면 인코딩 | 파이썬 파일 위의 `win32` 두 줄을 지우지 않는다 |
| 20번 넘게 해도 안 된다 | 껐다 켜기 전에 | 어느 단계에서 무엇이 떴는지 한 줄로 남기고 그 단계만 다시 |

**429 세 종류**
- `limit: 15` - 1분에 15번을 넘겼다. 한도는 모델마다 따로다. **다른 모델로 바꾸면 그 자리에서 계속된다**
- `limit: 500` - 하루치를 다 썼다. 날이 바뀌어야 풀린다
- 상태 `제한됨` - 프로젝트가 잠겼다. 강사에게 알린다

