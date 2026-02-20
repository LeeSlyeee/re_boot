import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
sys.path.append(os.getcwd())
django.setup()

from learning.models import Lecture, Syllabus, LearningObjective

lecture = Lecture.objects.get(title='Vue.js 기초')

syllabus_data = [
    {
        'week': 1,
        'title': 'Vue.js 소개 및 개발 환경 구축',
        'desc': 'Vue.js의 핵심 철학과 프로젝트 생성, 컴포넌트 기초 이해',
        'objectives': [
            'Vue.js의 반응성(Reactivity) 원리를 설명할 수 있다',
            'Vite를 사용하여 Vue 프로젝트를 생성할 수 있다',
            'SFC(Single File Component) 구조를 이해한다',
            'template, script, style 블록의 역할을 구분할 수 있다',
            'v-bind와 이중 중괄호(Mustache) 문법으로 데이터를 바인딩할 수 있다',
        ]
    },
    {
        'week': 2,
        'title': '디렉티브와 이벤트 핸들링',
        'desc': '조건부 렌더링, 리스트 렌더링, 이벤트 처리 및 양방향 바인딩',
        'objectives': [
            'v-if / v-else / v-show의 차이를 설명할 수 있다',
            'v-for를 사용하여 배열 데이터를 렌더링할 수 있다',
            'v-on(@click 등)으로 이벤트를 처리할 수 있다',
            'v-model을 활용한 양방향 데이터 바인딩을 구현할 수 있다',
            'computed 속성과 watch의 차이를 이해한다',
            'ref()와 reactive()의 차이를 설명할 수 있다',
        ]
    },
    {
        'week': 3,
        'title': '컴포넌트 설계와 상태 관리',
        'desc': 'Props/Emit, 컴포넌트 통신 패턴, Pinia를 활용한 전역 상태 관리',
        'objectives': [
            'Props를 통해 부모에서 자식으로 데이터를 전달할 수 있다',
            'Emit을 통해 자식에서 부모로 이벤트를 발생시킬 수 있다',
            'Slot을 활용하여 재사용 가능한 레이아웃 컴포넌트를 만들 수 있다',
            'Pinia 스토어를 생성하고 컴포넌트에서 사용할 수 있다',
            'provide/inject 패턴을 이해한다',
        ]
    },
    {
        'week': 4,
        'title': 'Vue Router와 API 통신',
        'desc': 'SPA 라우팅, Axios를 활용한 REST API 연동, 배포 준비',
        'objectives': [
            'Vue Router를 설정하고 페이지 네비게이션을 구현할 수 있다',
            '동적 라우트 파라미터(:id)를 활용할 수 있다',
            'Navigation Guard(beforeEach)로 인증 보호를 구현할 수 있다',
            'Axios를 사용하여 REST API와 CRUD 통신을 할 수 있다',
            'onMounted 등 Lifecycle Hook을 활용하여 데이터를 로딩할 수 있다',
            'Vite build로 프로덕션 빌드를 생성할 수 있다',
        ]
    },
]

for item in syllabus_data:
    syl, created = Syllabus.objects.get_or_create(
        lecture=lecture,
        week_number=item['week'],
        defaults={'title': item['title'], 'description': item['desc']}
    )
    action = 'NEW' if created else 'EXISTS'
    print(f"[{action}] {item['week']}W: {item['title']}")
    
    for idx, obj_text in enumerate(item['objectives'], 1):
        obj, obj_created = LearningObjective.objects.get_or_create(
            syllabus=syl,
            content=obj_text,
            defaults={'order': idx}
        )
        symbol = '  +' if obj_created else '  ='
        print(f"{symbol} {obj_text}")

print()
total_obj = LearningObjective.objects.filter(syllabus__lecture=lecture).count()
print(f"TOTAL: {Syllabus.objects.filter(lecture=lecture).count()} weeks / {total_obj} objectives")
