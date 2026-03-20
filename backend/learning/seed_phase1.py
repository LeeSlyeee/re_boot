"""
Phase 1 시드 데이터: 진단 문항 + 역량 + 직무 목표
python manage.py shell < learning/seed_phase1.py
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

from learning.models import PlacementQuestion, Skill, CareerGoal

# ══════════════════════════════════════════════════════════
# 1. 역량 (Skill) 시드 데이터
# ══════════════════════════════════════════════════════════

SKILLS = [
    # JavaScript
    ('JAVASCRIPT', '변수와 데이터 타입', 1, 1),
    ('JAVASCRIPT', '조건문과 반복문', 1, 2),
    ('JAVASCRIPT', '함수와 스코프', 1, 3),
    ('JAVASCRIPT', '배열과 객체 메서드', 2, 4),
    ('JAVASCRIPT', '클로저와 실행 컨텍스트', 2, 5),
    ('JAVASCRIPT', '비동기 처리 (Promise/async)', 2, 6),
    ('JAVASCRIPT', 'DOM 조작', 2, 7),
    ('JAVASCRIPT', '이벤트 루프', 3, 8),
    ('JAVASCRIPT', '모듈 시스템 (ES6)', 3, 9),
    # Python
    ('PYTHON', '기본 문법과 자료형', 1, 1),
    ('PYTHON', '리스트/딕셔너리 컴프리헨션', 2, 2),
    ('PYTHON', '클래스와 OOP', 2, 3),
    ('PYTHON', '데코레이터와 제너레이터', 3, 4),
    # HTML/CSS
    ('HTML_CSS', 'HTML 시맨틱 태그', 1, 1),
    ('HTML_CSS', 'CSS Flexbox/Grid 레이아웃', 2, 2),
    ('HTML_CSS', '반응형 디자인', 2, 3),
    # Framework
    ('FRAMEWORK', 'React 기초 (컴포넌트/Props)', 2, 1),
    ('FRAMEWORK', 'React 상태 관리 (useState/useEffect)', 2, 2),
    ('FRAMEWORK', 'Vue.js 기초', 2, 3),
    ('FRAMEWORK', 'Django/Flask REST API', 2, 4),
    ('FRAMEWORK', 'Next.js / Nuxt.js SSR', 3, 5),
    # Database
    ('DATABASE', 'SQL 기본 (SELECT/JOIN)', 1, 1),
    ('DATABASE', 'ORM 사용 (Django/SQLAlchemy)', 2, 2),
    ('DATABASE', 'NoSQL 기초 (MongoDB)', 3, 3),
    # DevOps
    ('DEVOPS', 'Git 기본 (add/commit/push)', 1, 1),
    ('DEVOPS', 'Git 브랜치 전략', 2, 2),
    ('DEVOPS', 'Docker 기초', 3, 3),
    ('DEVOPS', 'CI/CD 파이프라인', 3, 4),
    # CS 기초
    ('CS_BASIC', '자료구조 (배열/스택/큐)', 1, 1),
    ('CS_BASIC', '알고리즘 기초 (정렬/탐색)', 2, 2),
    ('CS_BASIC', 'HTTP/REST 개념', 1, 3),
    ('CS_BASIC', '네트워크 기초 (TCP/IP/DNS)', 2, 4),
]

print("🔧 Skill 시드 데이터 생성 중...")
skill_objects = {}
for cat, name, diff, order in SKILLS:
    skill, _ = Skill.objects.update_or_create(
        name=name, category=cat,
        defaults={'difficulty_level': diff, 'order': order}
    )
    skill_objects[name] = skill
print(f"  ✅ {len(SKILLS)}개 역량 생성 완료")

# ══════════════════════════════════════════════════════════
# 2. 직무 목표 (CareerGoal) 시드 데이터
# ══════════════════════════════════════════════════════════

CAREERS = [
    {
        'title': '프론트엔드 개발자',
        'icon': '🎨',
        'description': 'React/Vue 기반 웹 애플리케이션의 UI/UX를 구현하는 개발자 (HTML, CSS, JavaScript, React/Vue, 반응형 디자인)',
        'weeks': 16,
        'skills': ['변수와 데이터 타입', '조건문과 반복문', '함수와 스코프', '배열과 객체 메서드', '클로저와 실행 컨텍스트', '비동기 처리 (Promise/async)', 'DOM 조작', '이벤트 루프', '모듈 시스템 (ES6)', 'HTML 시맨틱 태그', 'CSS Flexbox/Grid 레이아웃', '반응형 디자인', 'React 기초 (컴포넌트/Props)', 'React 상태 관리 (useState/useEffect)', 'Git 기본 (add/commit/push)', 'Git 브랜치 전략', 'HTTP/REST 개념'],
    },
    {
        'title': '백엔드 개발자',
        'icon': '⚙️',
        'description': 'Django/Flask 기반 서버와 API를 설계하고 데이터베이스를 관리하는 개발자 (Python, SQL, REST API, Docker)',
        'weeks': 16,
        'skills': ['기본 문법과 자료형', '리스트/딕셔너리 컴프리헨션', '클래스와 OOP', '데코레이터와 제너레이터', 'Django/Flask REST API', 'SQL 기본 (SELECT/JOIN)', 'ORM 사용 (Django/SQLAlchemy)', 'Git 기본 (add/commit/push)', 'Git 브랜치 전략', 'Docker 기초', 'HTTP/REST 개념', '네트워크 기초 (TCP/IP/DNS)', '자료구조 (배열/스택/큐)', '알고리즘 기초 (정렬/탐색)'],
    },
    {
        'title': '풀스택 개발자',
        'icon': '🚀',
        'description': '프론트엔드와 백엔드를 모두 다루는 개발자 (JavaScript, Python, React, Django, SQL, DevOps)',
        'weeks': 24,
        'skills': ['변수와 데이터 타입', '조건문과 반복문', '함수와 스코프', '배열과 객체 메서드', '클로저와 실행 컨텍스트', '비동기 처리 (Promise/async)', 'DOM 조작', '기본 문법과 자료형', '클래스와 OOP', 'HTML 시맨틱 태그', 'CSS Flexbox/Grid 레이아웃', 'React 기초 (컴포넌트/Props)', 'Django/Flask REST API', 'SQL 기본 (SELECT/JOIN)', 'ORM 사용 (Django/SQLAlchemy)', 'Git 기본 (add/commit/push)', 'Git 브랜치 전략', 'Docker 기초', 'HTTP/REST 개념'],
    },
    {
        'title': '데이터 분석가',
        'icon': '📊',
        'description': 'Python 기반 데이터 수집, 분석, 시각화를 수행하는 분석가 (Python, SQL, Pandas, 통계학)',
        'weeks': 12,
        'skills': ['기본 문법과 자료형', '리스트/딕셔너리 컴프리헨션', '클래스와 OOP', 'SQL 기본 (SELECT/JOIN)', '자료구조 (배열/스택/큐)', '알고리즘 기초 (정렬/탐색)', 'Git 기본 (add/commit/push)'],
    },
]

print("🔧 CareerGoal 시드 데이터 생성 중...")
for c in CAREERS:
    goal, _ = CareerGoal.objects.update_or_create(
        title=c['title'],
        defaults={
            'icon': c['icon'],
            'description': c['description'],
            'estimated_weeks': c['weeks'],
        }
    )
    # M2M 연결
    skill_list = [skill_objects[s] for s in c['skills'] if s in skill_objects]
    goal.required_skills.set(skill_list)
print(f"  ✅ {len(CAREERS)}개 직무 목표 생성 완료")

# ══════════════════════════════════════════════════════════
# 3. 진단 문항 (PlacementQuestion) 시드 데이터
# ══════════════════════════════════════════════════════════

QUESTIONS = [
    # 개념 이해도 (CONCEPT) - 10문
    {'q': 'JavaScript에서 변수를 선언할 때 사용하는 키워드가 아닌 것은?', 'opts': ['var', 'let', 'const', 'def'], 'ans': 'def', 'cat': 'CONCEPT', 'diff': 1, 'exp': 'def는 Python의 함수 정의 키워드입니다. JavaScript에서는 var, let, const를 사용합니다.'},
    {'q': 'HTML에서 가장 큰 제목을 나타내는 태그는?', 'opts': ['<h6>', '<h1>', '<title>', '<header>'], 'ans': '<h1>', 'cat': 'CONCEPT', 'diff': 1, 'exp': '<h1>은 가장 큰 제목 태그이며, <h6>이 가장 작습니다.'},
    {'q': 'CSS에서 요소를 가로로 정렬하는 데 가장 적합한 속성은?', 'opts': ['float', 'display: flex', 'position: absolute', 'margin: auto'], 'ans': 'display: flex', 'cat': 'CONCEPT', 'diff': 1, 'exp': 'Flexbox(display: flex)는 현대 웹에서 가장 권장되는 가로 정렬 방법입니다.'},
    {'q': '다음 중 JavaScript의 원시 타입(Primitive Type)이 아닌 것은?', 'opts': ['string', 'number', 'array', 'boolean'], 'ans': 'array', 'cat': 'CONCEPT', 'diff': 2, 'exp': 'Array는 객체(Object) 타입입니다. 원시 타입은 string, number, boolean, undefined, null, symbol, bigint입니다.'},
    {'q': 'HTTP 상태 코드 404가 의미하는 것은?', 'opts': ['서버 오류', '요청 성공', '리소스 없음', '인증 필요'], 'ans': '리소스 없음', 'cat': 'CONCEPT', 'diff': 1, 'exp': '404 Not Found는 요청한 리소스를 서버에서 찾을 수 없음을 의미합니다.'},
    {'q': 'Python에서 리스트 [1,2,3]의 마지막 요소에 접근하는 방법은?', 'opts': ['list[3]', 'list[-1]', 'list.last()', 'list.end()'], 'ans': 'list[-1]', 'cat': 'CONCEPT', 'diff': 1, 'exp': 'Python에서 인덱스 -1은 마지막 요소를 가리킵니다.'},
    {'q': 'JavaScript에서 클로저(Closure)란?', 'opts': ['함수를 닫는 구문', '외부 변수를 기억하는 함수', '비동기 처리 패턴', '에러 처리 구문'], 'ans': '외부 변수를 기억하는 함수', 'cat': 'CONCEPT', 'diff': 2, 'exp': '클로저는 함수가 선언될 때의 렉시컬 환경(외부 변수)을 기억하고 접근할 수 있는 함수입니다.'},
    {'q': 'SQL에서 두 테이블을 결합하는 키워드는?', 'opts': ['MERGE', 'COMBINE', 'JOIN', 'LINK'], 'ans': 'JOIN', 'cat': 'CONCEPT', 'diff': 2, 'exp': 'JOIN은 두 개 이상의 테이블을 관계 기반으로 결합하는 SQL 키워드입니다.'},
    {'q': 'Git에서 변경사항을 원격 저장소에 업로드하는 명령어는?', 'opts': ['git commit', 'git push', 'git pull', 'git merge'], 'ans': 'git push', 'cat': 'CONCEPT', 'diff': 1, 'exp': 'git push는 로컬 커밋을 원격 저장소로 업로드합니다.'},
    {'q': 'REST API에서 데이터를 생성할 때 주로 사용하는 HTTP 메서드는?', 'opts': ['GET', 'POST', 'PUT', 'DELETE'], 'ans': 'POST', 'cat': 'CONCEPT', 'diff': 2, 'exp': 'POST는 새로운 리소스를 생성할 때 사용하는 HTTP 메서드입니다.'},

    # 실습 경험 (PRACTICE) - 6문
    {'q': 'React에서 상태를 관리하기 위해 사용하는 Hook은?', 'opts': ['useRef', 'useState', 'useContext', 'useMemo'], 'ans': 'useState', 'cat': 'PRACTICE', 'diff': 2, 'exp': 'useState는 함수형 컴포넌트에서 상태를 선언하고 관리하는 기본 Hook입니다.'},
    {'q': 'Django에서 URL과 뷰를 연결하는 파일은?', 'opts': ['views.py', 'urls.py', 'models.py', 'settings.py'], 'ans': 'urls.py', 'cat': 'PRACTICE', 'diff': 2, 'exp': 'urls.py에서 URL 패턴과 뷰 함수/클래스를 매핑합니다.'},
    {'q': 'npm install을 실행하면 패키지가 설치되는 폴더는?', 'opts': ['src/', 'build/', 'node_modules/', 'packages/'], 'ans': 'node_modules/', 'cat': 'PRACTICE', 'diff': 1, 'exp': 'npm install은 의존성 패키지를 node_modules/ 폴더에 설치합니다.'},
    {'q': 'Docker에서 컨테이너를 빌드하기 위한 설정 파일명은?', 'opts': ['docker-compose.yml', 'Dockerfile', 'package.json', '.dockerignore'], 'ans': 'Dockerfile', 'cat': 'PRACTICE', 'diff': 3, 'exp': 'Dockerfile은 Docker 이미지를 빌드하기 위한 명령어 시퀀스를 담는 파일입니다.'},
    {'q': 'Git에서 새 브랜치를 생성하고 전환하는 명령어는?', 'opts': ['git branch new', 'git checkout -b new', 'git switch new', 'git create new'], 'ans': 'git checkout -b new', 'cat': 'PRACTICE', 'diff': 2, 'exp': 'git checkout -b <이름>은 새 브랜치를 생성하고 즉시 전환합니다.'},
    {'q': 'async/await에서 에러를 처리하는 방법은?', 'opts': ['if/else', 'try/catch', 'then/catch', 'error/handle'], 'ans': 'try/catch', 'cat': 'PRACTICE', 'diff': 2, 'exp': 'async/await 패턴에서는 try/catch 블록으로 에러를 처리합니다.'},

    # 학습 패턴 (PATTERN) - 4문
    {'q': '새로운 프로그래밍 개념을 배울 때 가장 먼저 하는 행동은?', 'opts': ['공식 문서를 읽는다', '유튜브 강의를 본다', '바로 코드를 작성해본다', '블로그 글을 검색한다'], 'ans': '바로 코드를 작성해본다', 'cat': 'PATTERN', 'diff': 1, 'exp': '실습 우선 학습(Learning by Doing)은 프로그래밍에서 가장 효과적인 학습법입니다.'},
    {'q': '코드에서 에러가 발생했을 때 가장 먼저 확인하는 것은?', 'opts': ['에러 메시지를 읽는다', '전체 코드를 다시 작성한다', '다른 사람에게 물어본다', '프로그램을 재시작한다'], 'ans': '에러 메시지를 읽는다', 'cat': 'PATTERN', 'diff': 1, 'exp': '에러 메시지에는 문제의 원인과 위치가 포함되어 있어 가장 먼저 확인해야 합니다.'},
    {'q': '프로젝트를 진행할 때 가장 중요하다고 생각하는 것은?', 'opts': ['완벽한 설계', '빠른 프로토타이핑', '코드 품질', '팀 커뮤니케이션'], 'ans': '팀 커뮤니케이션', 'cat': 'PATTERN', 'diff': 2, 'exp': '소프트웨어 개발에서 팀 커뮤니케이션은 기술적 역량만큼 중요한 핵심 요소입니다.'},
    {'q': '학습 시 가장 효과적인 복습 주기는?', 'opts': ['당일 + 3일 후 + 1주일 후', '한 달에 한 번', '시험 전날 집중', '매일 같은 내용 반복'], 'ans': '당일 + 3일 후 + 1주일 후', 'cat': 'PATTERN', 'diff': 1, 'exp': '에빙하우스 망각 곡선에 따르면 간격을 두고 반복하는 것이 장기 기억에 효과적입니다.'},
]

print("🔧 PlacementQuestion 시드 데이터 생성 중...")
for i, q in enumerate(QUESTIONS, 1):
    PlacementQuestion.objects.update_or_create(
        order=i,
        defaults={
            'question_text': q['q'],
            'options': q['opts'],
            'correct_answer': q['ans'],
            'category': q['cat'],
            'difficulty': q['diff'],
            'explanation': q['exp'],
        }
    )
print(f"  ✅ {len(QUESTIONS)}개 진단 문항 생성 완료")

print("\n🎉 Phase 1 시드 데이터 생성 완료!")
print(f"  - 역량: {Skill.objects.count()}개")
print(f"  - 직무 목표: {CareerGoal.objects.count()}개")
print(f"  - 진단 문항: {PlacementQuestion.objects.count()}개")
