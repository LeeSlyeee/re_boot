import os, sys, django

# Add the backend directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

from account.models import User
from learning.models import Lecture, Syllabus, LearningObjective

def seed_vue_syllabus():
    try:
        instructor = User.objects.get(username='test_instructor')
    except User.DoesNotExist:
        print("Error: Instructor test_instructor not found.")
        return

    try:
        lecture = Lecture.objects.get(instructor=instructor, title__icontains='vue.js 기초')
        print(f"Found lecture: {lecture.title} (ID: {lecture.id})")
    except Lecture.DoesNotExist:
        print("Error: Lecture vue.js 기초 not found for instructor test_instructor.")
        return
    except Lecture.MultipleObjectsReturned:
        lectures = Lecture.objects.filter(instructor=instructor, title__icontains='vue.js 기초')
        lecture = lectures.first()
        print(f"Warning: Multiple lectures found. Using the first one: {lecture.title} (ID: {lecture.id})")

    weeks_data = [
        {'week': 1, 'title': 'Vue.js 소개 및 환경 설정', 'desc': 'Vue.js의 특징과 장점 이해, 개발 환경(Node.js, Vue CLI, VSCode) 구축', 'objectives': ['Vue.js 프레임워크의 개념 이해', 'Node.js 및 패키지 매니저(npm) 사용법 숙지', 'Vue CLI를 이용한 프로젝트 생성 및 실행']},
        {'week': 2, 'title': 'Vue 인스턴스와 데이터 바인딩', 'desc': 'Vue 인스턴스 생성, 데이터 렌더링 방식 및 기본 디렉티브 학습', 'objectives': ['Vue 인스턴스의 라이프사이클 이해', '보간법(Interpolation)을 이용한 데이터 출력', 'v-bind, v-html 등 기본 디렉티브 활용']},
        {'week': 3, 'title': '이벤트 처리와 폼 입력 바인딩', 'desc': '사용자 입력 처리, 이벤트 수식어 활용 및 양방향 데이터 바인딩', 'objectives': ['v-on 디렉티브를 이용한 이벤트 처리', '이벤트 수식어(.prevent, .stop 등) 활용', 'v-model을 이용한 폼 데이터 양방향 바인딩']},
        {'week': 4, 'title': '조건부 랜더링과 리스트 랜더링', 'desc': '조건에 따른 UI 표시, 배열/객체 데이터를 반복 랜더링하는 방법', 'objectives': ['v-if, v-else, v-show 디렉티브의 차이점 및 활용', 'v-for 디렉티브를 이용한 배열 및 객체 반복 출력', '리스트 랜더링 시 key 속성의 중요성 이해']},
        {'week': 5, 'title': '계산된 속성(Computed)과 감시자(Watch)', 'desc': '복잡한 데이터 로직을 처리하는 Computed와 데이터 변화를 감지하는 Watch', 'objectives': ['Computed 속성을 이용한 데이터 캐싱 및 의존성 관리', 'Watch 속성을 이용한 비동기 작업 및 부수 효과 처리', 'Computed와 Watch의 적절한 사용 상황 구분']},
        {'week': 6, 'title': '컴포넌트 기초', 'desc': '재사용 가능한 UI 블록인 컴포넌트의 개념과 생성, 활용', 'objectives': ['전역 및 지역 컴포넌트 등록 방법 이해', '컴포넌트 템플릿 작성 및 데이터(data) 함수 활용', '컴포넌트 기반 아키텍처의 장점 이해']},
        {'week': 7, 'title': '컴포넌트 통신 (Props와 Emit)', 'desc': '부모-자식 컴포넌트 간 데이터 전달 및 이벤트 발생 구조 학습', 'objectives': ['Props를 이용한 부모에서 자식으로 데이터 전달', '데이터 타입 체크 및 기본값 설정', 'Emit을 이용한 자식에서 부모로 커스텀 이벤트 발생']},
        {'week': 8, 'title': '중간 평가 및 실습', 'desc': '1~7주차 내용 복습 및 간단한 Todo 애플리케이션 만들기 실습', 'objectives': ['그동안 배운 디렉티브, 컴포넌트, 통신 방식 종합 활용', '기본적인 CRUD 기능 구현', '코드 리뷰 및 최적화 방법 논의']},
        {'week': 9, 'title': '컴포넌트 슬롯(Slots)', 'desc': '컴포넌트 템플릿의 일부를 부모에서 정의하여 주입하는 방법', 'objectives': ['기본 슬롯(Default Slot) 활용', '이름이 있는 슬롯(Named Slots) 활용', '범위가 지정된 슬롯(Scoped Slots) 개념 이해 및 적용']},
        {'week': 10, 'title': 'Vue Router 연동 (1)', 'desc': 'SPA(Single Page Application) 라우팅을 위한 Vue Router 기본 설정', 'objectives': ['Vue Router 설치 및 기본 라우터 설정', 'router-link와 router-view 컴포넌트 활용', '동적 라우트 매칭 이해']},
        {'week': 11, 'title': 'Vue Router 연동 (2)', 'desc': '중첩 라우팅, 프로그래밍 방식 네비게이션 및 네비게이션 가드', 'objectives': ['중첩된 라우트 구조 설계 및 구현', 'router.push() 등을 이용한 프로그래밍 방식 페이지 이동', '네비게이션 가드를 이용한 접근 제어 (예: 로그인 확인)']},
        {'week': 12, 'title': '상태 관리 기초 (Pinia 또는 Vuex)', 'desc': '앱 전역 상태 관리 필요성 이해 및 상태 관리 라이브러리(Pinia) 도입', 'objectives': ['컴포넌트 간 상태 공유의 어려움 인지 및 중앙 집중식 상태 관리 개념 이해', 'Pinia 설치 및 기본 스토어 생성', 'State, Getters, Actions 활용']},
        {'week': 13, 'title': '상태 관리 심화', 'desc': 'Pinia를 이용한 데이터 비동기 처리 및 모듈화', 'objectives': ['Actions에서 비동기 데이터 통신(API 호출) 처리', '여러 개의 스토어로 상태 분리 및 조합', 'Pinia 플러그인 생태계 소개']},
        {'week': 14, 'title': 'API 연동과 비동기 처리 (Axios)', 'desc': 'Axios를 이용한 백엔드 API 통신 및 데이터 렌더링', 'objectives': ['Axios 라이브러리 설치 및 기본 사용법', 'GET, POST, PUT, DELETE 요청 실습', 'API 호출 시 로딩 및 에러 상태 처리']},
        {'week': 15, 'title': '컴포지션 API (Composition API) 기초', 'desc': 'Vue 3의 핵심인 Composition API (setup 구조) 이해', 'objectives': ['Options API와 Composition API의 차이점 및 장점 이해', 'setup 함수 내에서 reactive, ref를 이용한 반응형 데이터 정의', '생명주기 훅 활용 (onMounted 등)']},
        {'week': 16, 'title': '단일 파일 컴포넌트(SFC)와 <script setup>', 'desc': 'Vue 3 최신 문법 기반의 코드 작성 및 최적화 방법', 'objectives': ['<script setup> 구문을 활용한 간결한 컴포넌트 작성', 'defineProps, defineEmits 사용법 익히기', 'Composables(재사용 가능한 로직) 작성 및 적용']},
        {'week': 17, 'title': '미니 프로젝트 (1)', 'desc': '강의 내용을 총망라한 실전 웹 애플리케이션 프론트엔드 개발 시작', 'objectives': ['프로젝트 기획 및 화면 설계', 'Vue Router 및 Pinia 초기 설정', '인터페이스 레이아웃 및 기본 컴포넌트 구성 (API 연동)']},
        {'week': 18, 'title': '미니 프로젝트 (2) 및 배포', 'desc': '기능 완성, 최적화 및 빌드를 통한 웹 호스팅 배포', 'objectives': ['비동기 데이터 흐름 완성 및 기능 테스트', '운영 환경을 위한 빌드 명령어(npm run build) 실행', 'Vercel, Netlify 등을 활용한 프론트엔드 배포 실습']}
    ]

    for data in weeks_data:
        syllabus, created = Syllabus.objects.get_or_create(
            lecture=lecture,
            week_number=data['week'],
            defaults={
                'title': data['title'],
                'description': data['desc']
            }
        )
        if not created:
            syllabus.title = data['title']
            syllabus.description = data['desc']
            syllabus.save()
        
        # 기존 objectives 삭제 후 재생성 (또는 없으면 추가)
        syllabus.objectives.all().delete()
        for i, obj_content in enumerate(data['objectives']):
            LearningObjective.objects.create(
                syllabus=syllabus,
                content=obj_content,
                order=i+1
            )
        print(f"Week {data['week']} added/updated.")

    print("Done!")

if __name__ == '__main__':
    seed_vue_syllabus()
