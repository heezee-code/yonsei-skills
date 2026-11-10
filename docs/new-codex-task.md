# 새 Codex 작업으로 이어가기

## 보존 범위

현재 작업에서 파일이 유지된다는 사실은 새 클라우드 작업의 파일 보존을 보장하지 않는다.
로컬 커밋도 해당 실행 환경이 사라지면 접근하지 못할 수 있다. 원격에 푸시한 브랜치 또는
별도로 전달한 저장소 백업이 있어야 다른 환경에서 확실히 가져올 수 있다.
현재 환경의 설정 버전은 소스 코드 변경의 자동 저장이나 원격 반영을 증명하지 않는다.
푸시는 사용자가 대상 브랜치와 커밋을 검토하고 승인한 다음에만 실행한다.

## 새 작업에서 검색 확인

1. `heezee-code/yonsei-skills` 저장소와 이번 변경이 담긴 브랜치를 선택해 새 Codex 작업을 연다.
   푸시 전에는 원격에서 이 브랜치를 선택할 수 없다. 현재 환경을 재사용하더라도 커밋과 파일을 확인한다.
2. 아래 명령으로 경로·브랜치·커밋과 디스크의 스킬 연결을 확인한다. 경로는 새 환경에 맞춘다.

```bash
cd /workspace/yonsei-skills
git branch --show-current
git log -1 --oneline
git status --short
find .agents/skills -mindepth 1 -maxdepth 1 -type l | wc -l
test -f .agents/skills/calculate-yonsei-graduation-progress/SKILL.md
test -f .agents/skills/build-yonsei-timetable/SKILL.md
```

기대 링크 수는 52다. 이것은 디스크 준비 상태의 검사일 뿐 자동 검색 성공의 증거는 아니다.
파일이 없는 경우 먼저 올바른 브랜치인지 확인한다. 링크가 누락됐을 때만
`python3 -B scripts/setup_cloud_skills.py`로 복원하고 새 세션에서 확인한다.

3. 새 대화에서 다음과 같이 요청한다.

> 파일을 수동으로 읽어서 나열하기 전에, 현재 세션의 자동 제공 스킬 목록 또는
> executor skills 목록에서 이 저장소의 스킬이 검색되는지 확인해 줘.
> 52개 스킬의 실제 등록 여부와 calculate-yonsei-graduation-progress,
> plan-yonsei-graduation-path, build-yonsei-timetable의 검색 결과를 알려 줘.
> 목록을 확인할 기능이 없으면 미확인으로 표시하고 AGENTS.md의 직접 실행 방식을 사용해 줘.

4. `$calculate-yonsei-graduation-progress` 또는 `$build-yonsei-timetable`을 명시한 요청으로
해당 스킬이 실제 선택되고 스크립트가 실행되는지 확인한다. 자동 검색, 수동 지침 로드,
스크립트 실행, 공식 라이브 조회를 각각 구분하여 보고한다.
`yonsei_student`나 `yonsei_bridge_connect`는 별도 MCP 등록이 필요하다.

## 자동 검색 없이 자연어로 요청

이 저장소의 `AGENTS.md`가 에이전트에게 자연어 요청을 기존 실행기로 연결하도록 안내한다.
현재 디렉터리가 저장소 밖이면 먼저 저장소를 열거나 다음 요청에 경로를 명시한다.
실행기는 JSON을 받으며 자연어 해석은 Codex가 담당한다.

졸업요건 요청 예시:

> /workspace/yonsei-skills의 AGENTS.md를 읽고 직접 실행 방식을 사용해 줘.
> 첨부한 공식 졸업요건과 성적표를 기준으로 입학연도·전공을 맞춰
> calculate-yonsei-graduation-progress를 실행해 줘.
> JSON은 네가 work/에 준비하고, 완료·수강 중·부족 요건과 근거를 구분해 줘.
> 공식 자료나 과목별 정보가 부족하면 먼저 필요한 항목만 알려 줘.

시간표 요청 예시:

> /workspace/yonsei-skills의 AGENTS.md에 따라 run_cloud_skill.py를 사용해 줘.
> 첨부한 수강편람과 졸업요건 계산 결과로 필수과목을 포함한 15~18학점,
> 금요일 공강 시간표를 만들어 줘. 정규화·생성 후 선택한 후보에 대해
> 충돌 검사와 조건 검사를 모두 실행해 줘. 수업시간·학점·이동시간이
> 불명확하면 추정하지 말고 알려 줘. 실제 수강신청은 하지 마.

요건과 성적표 없이 총 이수학점만으로 정확한 졸업요건 시간표를 만들 수는 없다.
테스트용 가상 자료는 실제 학교 자료와 명확히 구분한다.

## 오프라인 실행 검증

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_cloud_skill_runner.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s plugins/yonsei-academic-copilot/tests -p test_graduation_skills.py -v
```

이 테스트는 모의 자료로 졸업 계산·계획·재계산과 시간표 정규화·생성·검사를 확인한다.
실제 학생 자료, 공식 사이트 접속, 새 Codex 세션의 자동 등록은 별도 검증 대상이다.
