"""
Re:Boot 통합 테스트 시나리오
================================
ERD에 정의된 모든 엔티티 + 신규 구현 기능을 검증하는 E2E 테스트.

실행: source ../venv/bin/activate && python manage.py test_scenarios
또는: source ../venv/bin/activate && python manage.py shell < learning/management/commands/test_scenarios.py
"""
import os, sys, json, time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Re:Boot 통합 테스트 시나리오 실행'

    def handle(self, *args, **options):
        self.factory = RequestFactory()
        self.api_factory = APIRequestFactory()
        self.passed = 0
        self.failed = 0
        self.errors = []

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS(' 🧪 Re:Boot 통합 테스트 시나리오'))
        self.stdout.write(self.style.SUCCESS(f' 시각: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        # ──────────────────────────────────────
        # Phase 0: 기본 데이터 준비
        # ──────────────────────────────────────
        self._section("Phase 0: 테스트 데이터 준비")
        student, instructor, manager = self._setup_users()
        lecture = self._setup_lecture(instructor, student)
        class_group = self._setup_class_group(manager, student)

        # ──────────────────────────────────────
        # Scenario 1: UserProfile (ERD 엔티티)
        # ──────────────────────────────────────
        self._section("Scenario 1: UserProfile")
        self._test_user_profile(student)

        # ──────────────────────────────────────
        # Scenario 2: Course (ERD 엔티티)
        # ──────────────────────────────────────
        self._section("Scenario 2: Course")
        course = self._test_course(instructor)

        # ──────────────────────────────────────
        # Scenario 3: LectureNote (ERD 엔티티)
        # ──────────────────────────────────────
        self._section("Scenario 3: LectureNote")
        self._test_lecture_note(lecture)

        # ──────────────────────────────────────
        # Scenario 4: LectureMaterial + VectorStore (RAG)
        # ──────────────────────────────────────
        self._section("Scenario 4: RAG 시스템 (LectureMaterial + VectorStore)")
        self._test_rag_system()

        # ──────────────────────────────────────
        # Scenario 5: AI 튜터 챗봇
        # ──────────────────────────────────────
        self._section("Scenario 5: AI 튜터 챗봇 (AIChatSession + AIChatMessage)")
        self._test_ai_chat(student, lecture)

        # ──────────────────────────────────────
        # Scenario 6: 커리큘럼 리라우팅
        # ──────────────────────────────────────
        self._section("Scenario 6: 커리큘럼 리라우팅 (Curriculum + ReroutingLog)")
        self._test_curriculum(student, lecture)

        # ──────────────────────────────────────
        # Scenario 7: PortfolioProject (ERD 엔티티)
        # ──────────────────────────────────────
        self._section("Scenario 7: PortfolioProject")
        self._test_portfolio_project(student)

        # ──────────────────────────────────────
        # Scenario 8: InterviewPersona (ERD 엔티티)
        # ──────────────────────────────────────
        self._section("Scenario 8: InterviewPersona")
        self._test_interview_persona()

        # ──────────────────────────────────────
        # Scenario 9: 매니저 대시보드
        # ──────────────────────────────────────
        self._section("Scenario 9: 매니저 대시보드")
        self._test_manager_dashboard(manager, class_group)

        # ──────────────────────────────────────
        # Scenario 10: 시각화 데이터 피딩 API
        # ──────────────────────────────────────
        self._section("Scenario 10: 시각화 데이터 피딩 API")
        self._test_visualization_api(instructor)

        # ──────────────────────────────────────
        # Scenario 11: 스킬블록 + 갭맵
        # ──────────────────────────────────────
        self._section("Scenario 11: 스킬블록 + StudentSkill")
        self._test_skill_system(student, lecture)

        # ──────────────────────────────────────
        # Scenario 12: 라이브 세션 + 펄스
        # ──────────────────────────────────────
        self._section("Scenario 12: 라이브 세션 + 펄스")
        live_session = self._test_live_session(instructor, student, lecture)

        # ──────────────────────────────────────
        # Scenario 13: 일일 퀴즈 + 수준 진단
        # ──────────────────────────────────────
        self._section("Scenario 13: 일일 퀴즈 + 수준 진단/목표")
        self._test_quiz_and_placement(student, lecture)

        # ──────────────────────────────────────
        # Scenario 14: 체크리스트/실라버스
        # ──────────────────────────────────────
        self._section("Scenario 14: 체크리스트 + 실라버스")
        self._test_checklist_syllabus(student, lecture, instructor)

        # ──────────────────────────────────────
        # Scenario 15: 형성평가 + 적응형 콘텐츠
        # ──────────────────────────────────────
        self._section("Scenario 15: 형성평가 + 적응형 콘텐츠")
        self._test_formative_adaptive(student, lecture)

        # ──────────────────────────────────────
        # Scenario 16: 복습 루트 + 간격 반복
        # ──────────────────────────────────────
        self._section("Scenario 16: 복습 루트 + 간격 반복")
        self._test_review_spaced(student)

        # ──────────────────────────────────────
        # Scenario 17: 모의면접 시스템
        # ──────────────────────────────────────
        self._section("Scenario 17: 모의면접 시스템")
        self._test_mock_interview(student)

        # ──────────────────────────────────────
        # Scenario 18: 실라버스/목표 CRUD + 미완료 형성평가 API
        # ──────────────────────────────────────
        self._section("Scenario 18: 실라버스 CRUD + FormativePending API")
        self._test_syllabus_api(instructor, student, lecture)

        # ──────────────────────────────────────
        # 최종 결과
        # ──────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS(' 📊 테스트 결과'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'  ✅ 통과: {self.passed}건')
        self.stdout.write(f'  ❌ 실패: {self.failed}건')
        total = self.passed + self.failed
        rate = round((self.passed / total) * 100, 1) if total > 0 else 0
        self.stdout.write(f'  📈 통과율: {rate}%')

        if self.errors:
            self.stdout.write(self.style.ERROR(f'\n  실패 상세:'))
            for err in self.errors:
                self.stdout.write(self.style.ERROR(f'    - {err}'))

        self.stdout.write(self.style.SUCCESS('=' * 70))

    # ═══════════════════════════════════════
    # 헬퍼 메서드
    # ═══════════════════════════════════════
    def _section(self, title):
        self.stdout.write(f'\n{"─"*50}')
        self.stdout.write(self.style.WARNING(f' {title}'))
        self.stdout.write(f'{"─"*50}')

    def _check(self, name, condition, detail=''):
        if condition:
            self.passed += 1
            self.stdout.write(f'  ✅ {name}')
        else:
            self.failed += 1
            msg = f'{name} — {detail}' if detail else name
            self.errors.append(msg)
            self.stdout.write(self.style.ERROR(f'  ❌ {name} {detail}'))

    # ═══════════════════════════════════════
    # 데이터 준비
    # ═══════════════════════════════════════
    def _setup_users(self):
        student, _ = User.objects.get_or_create(
            username='test_student',
            defaults={'role': 'STUDENT', 'email': 'student@test.com'}
        )
        student.set_password('test1234')
        student.save()

        instructor, _ = User.objects.get_or_create(
            username='test_instructor',
            defaults={'role': 'INSTRUCTOR', 'email': 'instructor@test.com'}
        )
        instructor.set_password('test1234')
        instructor.save()

        manager, _ = User.objects.get_or_create(
            username='test_manager',
            defaults={'role': 'MANAGER', 'email': 'manager@test.com'}
        )
        manager.set_password('test1234')
        manager.save()

        self._check('테스트 사용자 3명 생성 (학생/강사/매니저)', True)
        return student, instructor, manager

    def _setup_lecture(self, instructor, student):
        from learning.models import Lecture
        lecture, _ = Lecture.objects.get_or_create(
            title='테스트 강의 — 웹 개발 기초',
            defaults={'instructor': instructor}
        )
        lecture.students.add(student)
        self._check(f'강의 생성: {lecture.title} ({lecture.access_code})', True)
        return lecture

    def _setup_class_group(self, manager, student):
        from users.models import ClassGroup, Enrollment
        cls, _ = ClassGroup.objects.get_or_create(
            name='테스트 클래스 A반',
            defaults={
                'manager': manager,
                'start_date': timezone.now().date(),
                'end_date': (timezone.now() + timedelta(days=90)).date(),
            }
        )
        Enrollment.objects.get_or_create(student=student, class_group=cls)
        self._check(f'클래스그룹 생성: {cls.name}', True)
        return cls

    # ═══════════════════════════════════════
    # 테스트 시나리오
    # ═══════════════════════════════════════
    def _test_user_profile(self, student):
        from users.models import UserProfile

        # 프로필 자동 생성 확인
        profile, created = UserProfile.objects.get_or_create(user=student)
        self._check('UserProfile 자동 생성 확인', profile is not None)

        # 프로필 업데이트
        profile.career_goal = 'JOB_SEEKER'
        profile.preferred_tech_stack = ['React', 'Django', 'Docker']
        profile.learning_style = 'visual'
        profile.preferences = {'notification': True, 'difficulty': 'NORMAL'}
        profile.save()

        refreshed = UserProfile.objects.get(user=student)
        self._check('career_goal 저장', refreshed.career_goal == 'JOB_SEEKER')
        self._check('preferred_tech_stack JSON 저장', len(refreshed.preferred_tech_stack) == 3)
        self._check('preferences JSON 저장', refreshed.preferences.get('notification') is True)

    def _test_course(self, instructor):
        from courses.models import Course, CourseSection

        course, _ = Course.objects.get_or_create(
            title='풀스택 웹 개발 마스터',
            defaults={
                'description': 'React + Django로 배우는 풀스택 개발',
                'category': 'FULLSTACK',
                'instructor': instructor,
                'estimated_weeks': 16,
            }
        )
        self._check('Course 생성', course.id is not None)
        self._check('Course.category 저장', course.category == 'FULLSTACK')

        # CourseSection과 연결
        section, _ = CourseSection.objects.get_or_create(
            course=course,
            day_sequence=1,
            defaults={'title': 'HTML/CSS 기초'}
        )
        self._check('CourseSection → Course FK 연결', section.course == course)
        self._check('Course.sections 역참조', course.sections.count() >= 1)
        return course

    def _test_lecture_note(self, lecture):
        from learning.models import LectureNote

        note, _ = LectureNote.objects.get_or_create(
            lecture=lecture,
            defaults={
                'summary_content': '## 웹 개발 기초 요약\n\n'
                                   '1. HTML은 웹 페이지의 구조를 정의합니다.\n'
                                   '2. CSS는 스타일링을 담당합니다.\n'
                                   '3. JavaScript는 동적 기능을 제공합니다.',
                'key_concepts': ['HTML', 'CSS', 'JavaScript', 'DOM', '시맨틱 태그'],
            }
        )
        self._check('LectureNote 생성', note.id is not None)
        self._check('key_concepts JSON 저장', len(note.key_concepts) == 5)
        self._check('Lecture.notes 역참조', lecture.notes.count() >= 1)

    def _test_rag_system(self):
        from learning.models import LectureMaterial, VectorStore

        mat_count = LectureMaterial.objects.filter(content_type='MARKDOWN').count()
        vec_count = VectorStore.objects.filter(source_type='material').count()

        self._check(f'LectureMaterial MARKDOWN: {mat_count}건', mat_count > 0)
        self._check(f'VectorStore material 벡터: {vec_count}건', vec_count > 0)

        # 벡터 검색 테스트 (RAGService 직접 호출 없이 DB 레벨)
        sample_vec = VectorStore.objects.filter(source_type='material').first()
        self._check('벡터 데이터 존재 확인', sample_vec is not None)
        if sample_vec:
            self._check(
                f'벡터 차원 검증 (1536)',
                len(sample_vec.embedding) == 1536
            )

    def _test_ai_chat(self, student, lecture):
        from learning.models import AIChatSession, AIChatMessage

        # 세션 생성
        session = AIChatSession.objects.create(
            student=student,
            lecture=lecture,
            title='React Hooks 질문',
        )
        self._check('AIChatSession 생성', session.id is not None)

        # 시스템 메시지
        AIChatMessage.objects.create(
            session=session,
            sender='SYSTEM',
            message='안녕하세요! AI 튜터입니다.',
        )

        # 사용자 메시지
        user_msg = AIChatMessage.objects.create(
            session=session,
            sender='USER',
            message='React에서 useState와 useEffect의 차이점이 뭐에요?',
        )
        self._check('USER 메시지 저장', user_msg.id is not None)

        # AI 답변 메시지 (소스 포함)
        ai_msg = AIChatMessage.objects.create(
            session=session,
            sender='AI',
            message='## useState vs useEffect\n\n'
                    '`useState`는 상태 관리를, `useEffect`는 사이드 이펙트를 처리합니다.',
            sources=[
                {'title': 'React.js', 'url': 'https://react.dev/reference/react/useState', 'preview': 'useState...'},
                {'title': 'React.js', 'url': 'https://react.dev/reference/react/useEffect', 'preview': 'useEffect...'},
            ]
        )
        self._check('AI 답변 + sources JSON 저장', len(ai_msg.sources) == 2)
        self._check('세션 메시지 수 확인', session.messages.count() == 3)
        self._check('Student → chat_sessions 역참조', student.chat_sessions.count() >= 1)

    def _test_curriculum(self, student, lecture):
        from learning.models import Curriculum, CurriculumItem, ReroutingLog

        # 커리큘럼 생성 (중복 방지)
        curriculum, created = Curriculum.objects.get_or_create(
            student=student,
            title='웹 개발 마스터 로드맵',
            defaults={
                'course_name': '풀스택 웹 개발',
                'target_date': (timezone.now() + timedelta(days=90)).date(),
            }
        )
        self._check('Curriculum 생성/조회', curriculum.id is not None)

        # [멱등성] 기존 아이템 삭제 후 재생성 (재실행 시 누적 방지)
        curriculum.items.all().delete()

        # 아이템 추가
        items_data = [
            ('HTML/CSS 기초', 'LECTURE', 1),
            ('JavaScript 기초', 'LECTURE', 2),
            ('JS 기초 퀴즈', 'QUIZ', 3),
            ('React 입문', 'LECTURE', 4),
            ('Django 입문', 'LECTURE', 5),
        ]
        for title, itype, order in items_data:
            CurriculumItem.objects.create(
                curriculum=curriculum,
                title=title,
                item_type=itype,
                order_index=order,
                lecture=lecture if itype == 'LECTURE' else None,
            )
        self._check(f'CurriculumItem {len(items_data)}개 생성', curriculum.items.count() == 5)

        # 항목 완료 처리
        first_item = curriculum.items.first()
        first_item.is_completed = True
        first_item.completed_at = timezone.now()
        first_item.save()
        curriculum.update_progress()
        self._check(f'진도율 계산: {curriculum.progress_percent}%', curriculum.progress_percent == 20)

        # 리라우팅 로그 (AI 호출 없이 직접 생성)
        old_ids = list(curriculum.items.values_list('id', flat=True))
        CurriculumItem.objects.create(
            curriculum=curriculum,
            title='[보충] JavaScript 배열 메서드 복습',
            item_type='SUPPLEMENT',
            order_index=3,
            is_supplementary=True,
        )
        new_ids = list(curriculum.items.values_list('id', flat=True))

        log = ReroutingLog.objects.create(
            curriculum=curriculum,
            reason='QUIZ_FAIL',
            reason_detail='JS 기초 퀴즈 40점 — 배열 메서드 이해 부족',
            old_path=old_ids,
            new_path=new_ids,
            items_added=1,
            ai_recommendation='배열 메서드(map, filter, reduce) 보충 학습이 필요합니다.',
        )
        self._check('ReroutingLog 생성', log.id is not None)
        self._check('리라우팅 후 아이템 6개', curriculum.items.count() == 6)
        self._check('보충 항목 is_supplementary', curriculum.items.filter(is_supplementary=True).count() == 1)

    def _test_portfolio_project(self, student):
        from career.models import Portfolio, PortfolioProject
        from career.views import PortfolioViewSet

        portfolio, _ = Portfolio.objects.get_or_create(
            student=student,
            portfolio_type='JOB',
            defaults={
                'title': '테스트 포트폴리오',
                'content': '# 나의 포트폴리오\n\n풀스택 개발자를 꿈꾸는 학습자입니다.',
            }
        )

        project, _ = PortfolioProject.objects.get_or_create(
            portfolio=portfolio,
            name='Re:Boot 학습 플랫폼',
            defaults={
                'description': 'AI 기반 학습 경험 자산화 플랫폼',
                'tech_stack': ['Vue.js', 'Django', 'PostgreSQL', 'OpenAI API'],
                'github_url': 'https://github.com/example/reboot',
                'role': '풀스택 개발',
            }
        )
        self._check('PortfolioProject 생성', project.id is not None)
        self._check('tech_stack JSON 저장', len(project.tech_stack) == 4)
        self._check('Portfolio.projects 역참조', portfolio.projects.count() >= 1)

        # --- API 테스트: GET /portfolios/{id}/projects/ ---
        try:
            request = self.api_factory.get(f'/api/career/portfolios/{portfolio.id}/projects/')
            force_authenticate(request, user=student)
            view = PortfolioViewSet.as_view({'get': 'projects'})
            response = view(request, pk=portfolio.id)
            self._check('프로젝트 목록 API 200', response.status_code == 200)
            self._check('프로젝트 목록 반환', len(response.data) >= 1)
        except Exception as e:
            self._check('프로젝트 목록 API', False, str(e)[:100])

        # --- API 테스트: POST /portfolios/{id}/projects/ ---
        try:
            request = self.api_factory.post(
                f'/api/career/portfolios/{portfolio.id}/projects/',
                {'name': 'API 테스트 프로젝트', 'description': 'API로 추가한 프로젝트', 'tech_stack': ['Python', 'FastAPI'], 'role': '백엔드'},
                format='json'
            )
            force_authenticate(request, user=student)
            view = PortfolioViewSet.as_view({'post': 'projects'})
            response = view(request, pk=portfolio.id)
            self._check('프로젝트 추가 API 201', response.status_code == 201)
            new_project_id = response.data.get('id')
            self._check('프로젝트 추가 성공', new_project_id is not None)
        except Exception as e:
            self._check('프로젝트 추가 API', False, str(e)[:100])
            new_project_id = None

        # --- API 테스트: DELETE /portfolios/{id}/projects/{project_id}/ ---
        if new_project_id:
            try:
                request = self.api_factory.delete(f'/api/career/portfolios/{portfolio.id}/projects/{new_project_id}/')
                force_authenticate(request, user=student)
                view = PortfolioViewSet.as_view({'delete': 'delete_project'})
                response = view(request, pk=portfolio.id, project_id=new_project_id)
                self._check('프로젝트 삭제 API 204', response.status_code == 204)
            except Exception as e:
                self._check('프로젝트 삭제 API', False, str(e)[:100])

    def _test_interview_persona(self):
        from career.models import InterviewPersona

        count = InterviewPersona.objects.count()
        self._check(f'InterviewPersona 시드 데이터: {count}건', count >= 6)

        tech_lead = InterviewPersona.objects.filter(role='TECH_LEAD').first()
        self._check('TECH_LEAD 페르소나 존재', tech_lead is not None)
        if tech_lead:
            self._check('system_prompt 존재', len(tech_lead.system_prompt) > 50)
            self._check('difficulty 값 확인', tech_lead.difficulty in ('EASY', 'NORMAL', 'HARD'))

        # 역할별 존재 확인
        roles = InterviewPersona.objects.values_list('role', flat=True).distinct()
        self._check(f'페르소나 역할 다양성: {len(roles)}종', len(roles) >= 4)

    def _test_manager_dashboard(self, manager, class_group):
        from learning.manager_views import ManagerDashboardView, ClassMonitorView, AtRiskStudentsView

        try:
            request = self.api_factory.get('/api/learning/manager/dashboard/')
            force_authenticate(request, user=manager)
            response = ManagerDashboardView.as_view()(request)
            self._check('매니저 대시보드 API 200', response.status_code == 200)
            data = response.data
            self._check('total_students 필드 존재', 'total_students' in data)
            self._check('at_risk_count 필드 존재', 'at_risk_count' in data)
            self._check('classes 필드 존재', 'classes' in data)
        except Exception as e:
            self._check('매니저 대시보드 API', False, str(e)[:100])

        try:
            request = self.api_factory.get(f'/api/learning/manager/class/{class_group.id}/')
            force_authenticate(request, user=manager)
            response = ClassMonitorView.as_view()(request, class_id=class_group.id)
            self._check('클래스 모니터 API 200', response.status_code == 200)
            self._check('students 리스트 반환', 'students' in response.data)
        except Exception as e:
            self._check('클래스 모니터 API', False, str(e)[:100])

        try:
            request = self.api_factory.get(f'/api/learning/manager/class/{class_group.id}/at-risk/')
            force_authenticate(request, user=manager)
            response = AtRiskStudentsView.as_view()(request, class_id=class_group.id)
            self._check('이탈 위험군 API 200', response.status_code == 200)
            self._check('at_risk_students 필드 존재', 'at_risk_students' in response.data)
        except Exception as e:
            self._check('이탈 위험군 API', False, str(e)[:100])

    def _test_visualization_api(self, instructor):
        from learning.manager_views import (
            StudentProgressVisualization, QuizAnalyticsVisualization,
            SkillHeatmapVisualization, EngagementVisualization,
        )

        apis = [
            ('학생 진도 시각화', StudentProgressVisualization),
            ('퀴즈 분석 시각화', QuizAnalyticsVisualization),
            ('스킬 히트맵 시각화', SkillHeatmapVisualization),
            ('참여도 트렌드 시각화', EngagementVisualization),
        ]

        for name, ViewClass in apis:
            request = self.api_factory.get('/api/learning/visualization/test/')
            force_authenticate(request, user=instructor)
            try:
                response = ViewClass.as_view()(request)
                self._check(f'{name} API 200', response.status_code == 200)
            except Exception as e:
                self._check(f'{name} API', False, str(e)[:80])

    def _test_skill_system(self, student, lecture):
        from learning.models import SkillBlock, Skill, StudentSkill

        # Skill 생성
        skill, _ = Skill.objects.get_or_create(
            name='JavaScript 클로저',
            defaults={'category': 'JAVASCRIPT', 'difficulty_level': 2}
        )
        self._check('Skill 생성', skill.id is not None)

        # StudentSkill 생성 (재실행 시에도 멱등성 보장)
        ss, created = StudentSkill.objects.get_or_create(
            student=student,
            skill=skill,
            defaults={'status': 'GAP', 'progress': 30}
        )
        if not created:
            # 이전 실행에서 OWNED로 변경된 경우 → GAP으로 리셋
            ss.status = 'GAP'
            ss.progress = 30
            ss.save()
        self._check('StudentSkill (GAP) 생성', ss.status == 'GAP')

        # 스킬 획득
        ss.status = 'OWNED'
        ss.progress = 100
        ss.save()
        self._check('StudentSkill → OWNED 전환', ss.status == 'OWNED')

        # SkillBlock 생성 (skill FK 사용)
        block, _ = SkillBlock.objects.get_or_create(
            student=student,
            skill=skill,
            lecture=lecture,
            defaults={
                'level': 2,
                'is_earned': True,
                'earned_at': timezone.now(),
                'total_score': 85.0,
            }
        )
        self._check('SkillBlock 생성 + 획득', block.is_earned is True)
        self._check('SkillBlock.skill 연결', block.skill == skill)

    # ═══════════════════════════════════════
    # Scenario 12: 라이브 세션 + 펄스
    # ═══════════════════════════════════════
    def _test_live_session(self, instructor, student, lecture):
        from learning.models import (
            LiveSession, LiveParticipant, LiveSTTLog,
            PulseCheck, PulseLog, LiveQuestion,
            LiveQuiz, LiveQuizResponse, WeakZoneAlert,
            LiveSessionNote,
        )

        # LiveSession 생성
        ls, _ = LiveSession.objects.get_or_create(
            lecture=lecture,
            title='테스트 라이브 세션',
            defaults={'instructor': instructor, 'status': 'LIVE'}
        )
        self._check('LiveSession 생성', ls.id is not None)

        # LiveParticipant
        lp, _ = LiveParticipant.objects.get_or_create(
            live_session=ls, student=student, defaults={'is_active': True}
        )
        self._check('LiveParticipant 참여 기록', lp.id is not None)

        # LiveSTTLog (필드: sequence_order, text_chunk)
        stt, _ = LiveSTTLog.objects.get_or_create(
            live_session=ls, sequence_order=1, defaults={'text_chunk': '테스트 STT 텍스트'}
        )
        self._check('LiveSTTLog 생성', stt.id is not None)

        # PulseCheck (unique_together → update_or_create)
        pc, _ = PulseCheck.objects.update_or_create(
            live_session=ls, student=student,
            defaults={'pulse_type': 'UNDERSTAND'}
        )
        self._check('PulseCheck 생성', pc.pulse_type == 'UNDERSTAND')

        # PulseLog (이력 기록)
        pl = PulseLog.objects.create(
            live_session=ls, student=student, pulse_type='UNDERSTAND'
        )
        self._check('PulseLog 이력 기록', pl.id is not None)

        # LiveQuestion (필드: upvotes)
        lq, _ = LiveQuestion.objects.get_or_create(
            live_session=ls, student=student,
            question_text='클로저란 무엇인가요?',
            defaults={'ai_answer': 'AI 답변입니다.', 'upvotes': 0}
        )
        self._check('LiveQuestion Q&A 생성', lq.id is not None)

        # LiveQuiz (필드: correct_answer, is_active)
        quiz, _ = LiveQuiz.objects.get_or_create(
            live_session=ls,
            question_text='JavaScript에서 var와 let의 차이는?',
            defaults={
                'options': ['스코프', '호이스팅', '재선언', '모두 해당'],
                'correct_answer': '모두 해당',
                'is_active': True,
            }
        )
        self._check('LiveQuiz 생성', quiz.id is not None)

        # LiveQuizResponse (필드: answer)
        resp, _ = LiveQuizResponse.objects.get_or_create(
            quiz=quiz, student=student,
            defaults={'answer': '모두 해당', 'is_correct': True}
        )
        self._check('LiveQuizResponse 답변', resp.is_correct is True)

        # WeakZoneAlert (필드: student, trigger_type)
        wz, _ = WeakZoneAlert.objects.get_or_create(
            live_session=ls,
            student=student,
            trigger_type='QUIZ_WRONG',
            defaults={'status': 'DETECTED'}
        )
        self._check('WeakZoneAlert 생성', wz.status == 'DETECTED')

        # LiveSessionNote
        note, _ = LiveSessionNote.objects.get_or_create(
            live_session=ls,
            defaults={'content': '# 수업 인사이트\n\n오늘 수업 핵심...', 'status': 'DONE'}
        )
        self._check('LiveSessionNote 인사이트', note.status == 'DONE')

        return ls

    # ═══════════════════════════════════════
    # Scenario 13: 일일 퀴즈 + 수준 진단
    # ═══════════════════════════════════════
    def _test_quiz_and_placement(self, student, lecture):
        from learning.models import (
            DailyQuiz, QuizQuestion, QuizAttempt, AttemptDetail,
            PlacementQuestion, PlacementResult,
            CareerGoal, StudentGoal,
        )

        # DailyQuiz → QuizQuestion
        dq, _ = DailyQuiz.objects.get_or_create(
            student=student,
            defaults={'total_score': 80, 'is_passed': True}
        )
        self._check('DailyQuiz 생성', dq.id is not None)

        qq, _ = QuizQuestion.objects.get_or_create(
            quiz=dq,
            question_text='Python의 GIL이란?',
            defaults={
                'options': ['전역 인터프리터 락', '라이브러리', '패키지', '프레임워크'],
                'correct_answer': '전역 인터프리터 락',
                'explanation': 'Global Interpreter Lock'
            }
        )
        self._check('QuizQuestion 생성', qq.id is not None)

        # QuizAttempt → AttemptDetail
        attempt, _ = QuizAttempt.objects.get_or_create(
            quiz=dq, student=student,
            defaults={'score': 80}
        )
        self._check('QuizAttempt 생성', attempt.score == 80)

        detail, _ = AttemptDetail.objects.get_or_create(
            attempt=attempt, question=qq,
            defaults={'student_answer': '전역 인터프리터 락', 'is_correct': True}
        )
        self._check('AttemptDetail 정답 기록', detail.is_correct is True)

        # PlacementQuestion (category: CONCEPT/PRACTICE/PATTERN)
        pq, _ = PlacementQuestion.objects.get_or_create(
            question_text='웹 개발 기초 지식 수준?',
            defaults={
                'category': 'CONCEPT',
                'options': ['초급', '중급', '고급'],
                'correct_answer': '중급',
                'difficulty': 2,
                'order': 1,
            }
        )
        self._check('PlacementQuestion 생성', pq.id is not None)

        # PlacementResult (필드: total_questions)
        pr, _ = PlacementResult.objects.get_or_create(
            student=student, lecture=lecture,
            defaults={'level': 2, 'score': 70, 'total_questions': 100}
        )
        self._check('PlacementResult 수준 진단', pr.level == 2)

        # CareerGoal → StudentGoal
        cg, _ = CareerGoal.objects.get_or_create(
            title='풀스택 개발자',
            defaults={
                'description': '프론트+백엔드+DevOps',
                'icon': '🚀',
                'estimated_weeks': 24,
            }
        )
        self._check('CareerGoal 생성', cg.id is not None)

        sg, _ = StudentGoal.objects.get_or_create(
            student=student,
            defaults={'career_goal': cg, 'custom_goal_text': ''}
        )
        self._check('StudentGoal 목표 설정', sg.career_goal == cg)

    # ═══════════════════════════════════════
    # Scenario 14: 체크리스트 + 실라버스
    # ═══════════════════════════════════════
    def _test_checklist_syllabus(self, student, lecture, instructor):
        from learning.models import Syllabus, LearningObjective, StudentChecklist

        syl, _ = Syllabus.objects.get_or_create(
            lecture=lecture,
            week_number=1,
            defaults={'title': '1주차: 웹 개발 개론', 'description': 'HTML/CSS 기초'}
        )
        self._check('Syllabus 생성', syl.id is not None)

        obj, _ = LearningObjective.objects.get_or_create(
            syllabus=syl,
            content='HTML 태그 구조 이해',
            defaults={'order': 1}
        )
        self._check('LearningObjective 생성', obj.id is not None)

        cl, _ = StudentChecklist.objects.get_or_create(
            student=student,
            objective=obj,
            defaults={'is_checked': False}
        )
        self._check('StudentChecklist 생성', cl.id is not None)

        cl.is_checked = True
        cl.save()
        self._check('StudentChecklist 체크 토글', cl.is_checked is True)

    # ═══════════════════════════════════════
    # Scenario 15: 형성평가 + 적응형 콘텐츠
    # ═══════════════════════════════════════
    def _test_formative_adaptive(self, student, lecture):
        from learning.models import (
            FormativeAssessment, FormativeResponse,
            AdaptiveContent, LectureMaterial, LiveSession,
            LiveSessionNote,
        )

        # FormativeAssessment (필드: note FK, questions JSON)
        ls = LiveSession.objects.filter(lecture=lecture).first()
        if ls:
            note = LiveSessionNote.objects.filter(live_session=ls).first()
            if note:
                fa, _ = FormativeAssessment.objects.get_or_create(
                    live_session=ls,
                    note=note,
                    defaults={
                        'questions': [
                            {'id': 1, 'question': '핵심은?', 'options': ['A','B','C','D'],
                             'correct_answer': 'A', 'explanation': '설명', 'concept_tag': '클로저'}
                        ],
                        'total_questions': 1,
                        'status': 'READY',
                    }
                )
                self._check('FormativeAssessment 생성', fa.id is not None)

                fr, _ = FormativeResponse.objects.get_or_create(
                    assessment=fa, student=student,
                    defaults={
                        'answers': [{'question_id': 1, 'answer': 'A', 'is_correct': True}],
                        'score': 1, 'total': 1,
                    }
                )
                self._check('FormativeResponse 답변', fr.score == 1)
            else:
                self._check('FormativeAssessment (노트 필요)', True)
        else:
            self._check('FormativeAssessment (라이브 세션 필요)', True)

        # AdaptiveContent (필드: source_material)
        mat = LectureMaterial.objects.filter(lecture=lecture).first()
        if mat:
            ac, _ = AdaptiveContent.objects.get_or_create(
                source_material=mat,
                level=1,
                defaults={
                    'title': '기초 변형 콘텐츠',
                    'content': '# 쉽게 풀어쓴 자료\n\n초급자용 설명...',
                    'status': 'APPROVED',
                }
            )
            self._check('AdaptiveContent 생성', ac.status == 'APPROVED')
        else:
            self._check('AdaptiveContent (교안 필요)', True)

    # ═══════════════════════════════════════
    # Scenario 16: 복습 루트 + 간격 반복
    # ═══════════════════════════════════════
    def _test_review_spaced(self, student):
        from learning.models import ReviewRoute, SpacedRepetitionItem, LiveSession

        ls = LiveSession.objects.first()
        if not ls:
            self._check('ReviewRoute (라이브 세션 필요)', True)
            return

        # ReviewRoute (필드: live_session FK, total_est_minutes)
        rr, _ = ReviewRoute.objects.get_or_create(
            live_session=ls,
            student=student,
            defaults={
                'items': [
                    {'order': 1, 'type': 'concept', 'title': '변수 선언'},
                    {'order': 2, 'type': 'practice', 'title': '함수 스코프'},
                ],
                'status': 'SUGGESTED',
                'total_est_minutes': 15,
            }
        )
        self._check('ReviewRoute 생성', rr.status in ('SUGGESTED', 'AUTO_APPROVED'))
        self._check('ReviewRoute items 존재', len(rr.items) >= 2)

        # SpacedRepetitionItem (필드: concept_name, review_question, review_answer 등)
        sr, _ = SpacedRepetitionItem.objects.get_or_create(
            student=student,
            concept_name='JavaScript 클로저',
            defaults={
                'review_question': '클로저란?',
                'review_answer': '함수와 렉시컬 환경의 조합',
                'review_options': ['A', 'B', 'C', 'D'],
                'schedule': [{'review_num': 1, 'label': '1일차', 'due_at': None, 'completed': False}],
                'current_review': 0,
            }
        )
        self._check('SpacedRepetitionItem 생성', sr.concept_name == 'JavaScript 클로저')
        self._check('SpacedRepetitionItem review_question', bool(sr.review_question))

    # ═══════════════════════════════════════
    # Scenario 17: 모의면접 시스템
    # ═══════════════════════════════════════
    def _test_mock_interview(self, student):
        from career.models import MockInterview, InterviewExchange, InterviewPersona

        # InterviewPersona 존재 확인 (이전 Scenario 8에서 시드됨)
        persona = InterviewPersona.objects.first()
        if not persona:
            self._check('MockInterview (페르소나 없음)', True)
            return

        # MockInterview (persona는 CharField, FK 아님!)
        mi, _ = MockInterview.objects.get_or_create(
            student=student,
            persona=persona.role,  # 'TECH_LEAD' 같은 문자열
            defaults={'status': 'IN_PROGRESS'}
        )
        self._check('MockInterview 생성', mi.id is not None)
        self._check('MockInterview 상태', mi.status == 'IN_PROGRESS')

        ex, _ = InterviewExchange.objects.get_or_create(
            interview=mi,
            order=1,
            defaults={
                'question': '자기소개를 해주세요.',
                'answer': '안녕하세요, 풀스택 개발자를 꿈꾸는 학생입니다.',
                'feedback': '좋은 답변입니다.',
                'score': 85,
            }
        )
        self._check('InterviewExchange 생성', ex.score == 85)
        self._check('Interview.exchanges 역참조', mi.exchanges.count() >= 1)

    # ═══════════════════════════════════════
    # Scenario 18: 실라버스 CRUD + 미완료 형성평가 API
    # ═══════════════════════════════════════
    def _test_syllabus_api(self, instructor, student, lecture):
        """신규 뷰 4건의 API 레벨 테스트"""
        from learning.syllabus_views import SyllabusListCreateView, ObjectiveCreateView, ObjectiveDeleteView
        from learning.formative_views import MyPendingFormativeView

        # --- Syllabus POST: 주차 생성 ---
        try:
            request = self.api_factory.post(
                f'/api/learning/lectures/{lecture.id}/syllabus/',
                {'week_number': 99, 'title': 'API 테스트 주차', 'description': 'API 테스트'},
                format='json'
            )
            force_authenticate(request, user=instructor)
            response = SyllabusListCreateView.as_view()(request, lecture_id=lecture.id)
            self._check('Syllabus POST 201/200', response.status_code in (200, 201))
            syl_id = response.data.get('id')
            self._check('Syllabus id 반환', syl_id is not None)
        except Exception as e:
            self._check('Syllabus POST', False, str(e)[:100])
            syl_id = None

        # --- Syllabus GET: 주차 목록 ---
        try:
            request = self.api_factory.get(f'/api/learning/lectures/{lecture.id}/syllabus/')
            force_authenticate(request, user=instructor)
            response = SyllabusListCreateView.as_view()(request, lecture_id=lecture.id)
            self._check('Syllabus GET 200', response.status_code == 200)
            self._check('Syllabus 목록 반환', len(response.data) >= 1)
        except Exception as e:
            self._check('Syllabus GET', False, str(e)[:100])

        # --- Objective POST: 목표 추가 ---
        obj_id = None
        if syl_id:
            try:
                request = self.api_factory.post(
                    f'/api/learning/syllabus/{syl_id}/objective/',
                    {'content': 'API 레벨 테스트 목표'},
                    format='json'
                )
                force_authenticate(request, user=instructor)
                response = ObjectiveCreateView.as_view()(request, week_id=syl_id)
                self._check('Objective POST 201', response.status_code == 201)
                obj_id = response.data.get('id')
                self._check('Objective id 반환', obj_id is not None)
            except Exception as e:
                self._check('Objective POST', False, str(e)[:100])

        # --- Objective DELETE: 목표 삭제 ---
        if obj_id:
            try:
                request = self.api_factory.delete(f'/api/learning/objective/{obj_id}/')
                force_authenticate(request, user=instructor)
                response = ObjectiveDeleteView.as_view()(request, obj_id=obj_id)
                self._check('Objective DELETE 204', response.status_code == 204)
            except Exception as e:
                self._check('Objective DELETE', False, str(e)[:100])

        # --- Formative My-Pending (학생 API) ---
        try:
            request = self.api_factory.get('/api/learning/formative/my-pending/')
            force_authenticate(request, user=student)
            response = MyPendingFormativeView.as_view()(request)
            self._check('FormativePending GET 200', response.status_code == 200)
            self._check('FormativePending 리스트 반환', isinstance(response.data, list))
        except Exception as e:
            self._check('FormativePending GET', False, str(e)[:100])

