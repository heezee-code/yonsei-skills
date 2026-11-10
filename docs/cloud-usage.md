# 클라우드에서 사용하기

## 스킬 검색 준비

저장소 루트에서 `python3 -B scripts/setup_cloud_skills.py`를 실행한다.
`.agents/skills/<skill>`은 기존 플러그인 스킬 폴더로 향하는 상대 링크다.
복사본 없이 `scripts`, `references`, `agents/openai.yaml` 경로를 유지한다.
Codex를 이 저장소 디렉터리에서 새로 열어야 한다. 스킬 검색과 MCP 도구 등록은 별개이며,
이 설정은 `yonsei_student`를 현재 대화에 추가하거나 네트워크 정책을 변경하지 않는다.

## 플러그인 없이 직접 실행

`python3 -B scripts/run_cloud_skill.py --help`로 지원 스킬을 확인한다.

예:

```bash
python3 -B scripts/run_cloud_skill.py calculate-yonsei-graduation-progress --input work/graduation.json
python3 -B scripts/run_cloud_skill.py plan-yonsei-graduation-path --input work/path.json
python3 -B scripts/run_cloud_skill.py normalize-yonsei-courses --input work/courses.json
python3 -B scripts/run_cloud_skill.py build-yonsei-timetable --input work/choices.json
python3 -B scripts/run_cloud_skill.py check-yonsei-schedule --input work/selected-courses.json
python3 -B scripts/run_cloud_skill.py audit-yonsei-course-plan --input work/selected-courses.json
```

각 입력 계약은 해당 스킬의 `SKILL.md` 및 `references/`를 따른다.
생성기의 전체 출력 대신 선택한 해의 실제 과목 배열을 검사기에 전달한다.
입력을 생략하면 stdin에서 JSON을 읽고, 원본 스크립트의 종료코드와 출력을 전달한다.
인터넷, 로그인, 외부 패키지 설치 없이 제공된 자료에 대해 계산할 수 있다.
공식 요건 수집·성적표 해석·과목별 요건 연결은 별도로 필요하다.

## 졸업계획 결과 해석

학점 요건은 `remaining`, 과목 묶음은 `remaining_count`를 누적 차감한다.
`requirement_ids`는 공식 인정 관계에 근거해 입력한다. `fact`는 과목으로 해결하지 않는다.
`remaining_requirements`는 계획 뒤 남은 학점 또는 과목 수이며, 비학점 항목의 1은 미충족 표시다.
입력 진행표의 `complete`가 true가 아니면 졸업계획의 가능 여부를 true로 반환하지 않는다.
수강 중 과목은 완료로 자동 인정하지 않는다. 완료 여부는 실제 성적을 반영해 다시 계산한다.
탐욕적 배치이므로 가능한 모든 조합을 탐색하거나 최소 남은 학기를 증명하지 않는다.
`future_offerings_verified`는 개설학기 입력의 존재 여부만 나타내며 공식 서버 조회 증거가 아니다.

## 클라우드에서 기존 전체 테스트 실행

기본 브라우저 프로필 경로가 읽기 전용이면 기존 설정 변수로 쓰기 가능한 경로를 지정한다.
이것은 학교 로그인이나 네트워크 접속 성공을 의미하지 않는다.

```bash
YONSEI_BRIDGE_HOME="$PWD/work/yonsei-bridge" PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
YONSEI_BRIDGE_HOME="$PWD/work/yonsei-bridge" PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/run_plugin_tests.py
```
