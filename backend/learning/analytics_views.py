"""
Phase 3: 교수자 대시보드 분석 API Views
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg, F
from django.utils import timezone
from collections import defaultdict

from .models import (
    Lecture, LiveSession, LiveParticipant, LiveQuizResponse,
    PulseLog, PlacementResult, StudentChecklist, LearningObjective,
    Syllabus, FormativeResponse, FormativeAssessment, LiveSessionNote,
    NoteViewLog, WeakZoneAlert, ReviewRoute, AdaptiveContent,
    GroupMessage, StudentSkill, LiveQuiz,
)


# ══════════════════════════════════════════════════════════
# Phase 3-1: 학습자 수준 현황판
# ══════════════════════════════════════════════════════════

class AnalyticsOverviewView(APIView):
    """GET /api/learning/professor/{lecture_id}/analytics/overview/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)
        students = lecture.students.all()
        total_students = students.count()

        if total_students == 0:
            return Response({
                'message': '아직 등록된 수강생이 없습니다.',
                'total_students': 0,
            })

        # 종료된 세션만 분석
        ended_sessions = LiveSession.objects.filter(
            lecture=lecture, status='ENDED'
        ).order_by('created_at')
        session_count = ended_sessions.count()

        if session_count == 0:
            # 레벨 분포만 반환
            level_dist = self._get_level_distribution(lecture, students)
            return Response({
                'message': '아직 종료된 강의가 없습니다.',
                'total_students': total_students,
                'session_count': 0,
                'level_distribution': level_dist,
                'students': [
                    {'id': s.id, 'username': s.username, 'level': self._get_level(s, lecture)}
                    for s in students
                ],
            })

        # ── 데이터 집계 ──
        level_dist = self._get_level_distribution(lecture, students)
        student_data = []
        at_risk = []

        for student in students:
            # 출석률
            attended = LiveParticipant.objects.filter(
                student=student,
                live_session__in=ended_sessions,
            ).values_list('live_session_id', flat=True)

            # 수강등록 이후 세션만 카운트 (date_joined 비교)
            eligible_sessions = ended_sessions.filter(created_at__gte=student.date_joined)
            eligible_count = eligible_sessions.count()
            attendance_rate = (len(attended) / eligible_count * 100) if eligible_count > 0 else 100

            # 퀴즈 정답률
            quiz_responses = LiveQuizResponse.objects.filter(
                student=student,
                quiz__live_session__in=ended_sessions,
            )
            quiz_total = quiz_responses.count()
            quiz_correct = quiz_responses.filter(is_correct=True).count()
            quiz_accuracy = (quiz_correct / quiz_total * 100) if quiz_total > 0 else None

            # 펄스 혼란 비율
            pulses = PulseLog.objects.filter(
                student=student,
                live_session__in=ended_sessions,
            )
            pulse_total = pulses.count()
            pulse_confused = pulses.filter(pulse_type='CONFUSED').count()
            confused_rate = (pulse_confused / pulse_total * 100) if pulse_total > 0 else 0

            # 진도율 (체크리스트)
            objectives = LearningObjective.objects.filter(syllabus__lecture=lecture)
            obj_total = objectives.count()
            obj_checked = StudentChecklist.objects.filter(
                student=student, objective__in=objectives, is_checked=True
            ).count()
            progress_rate = (obj_checked / obj_total * 100) if obj_total > 0 else 0

            # 형성평가 평균 점수
            fa_responses = FormativeResponse.objects.filter(
                student=student,
                assessment__live_session__in=ended_sessions,
            )
            fa_avg = None
            if fa_responses.exists():
                fa_avg_data = fa_responses.aggregate(avg=Avg('score'))
                fa_avg = round(fa_avg_data['avg'] or 0, 1)

            # 결석 노트 열람 수
            note_views = NoteViewLog.objects.filter(
                student=student,
                note__live_session__in=ended_sessions,
            ).count()

            # 레벨
            level = self._get_level(student, lecture)

            s_data = {
                'id': student.id,
                'username': student.username,
                'level': level,
                'attendance_rate': round(attendance_rate, 1),
                'quiz_accuracy': round(quiz_accuracy, 1) if quiz_accuracy is not None else None,
                'progress_rate': round(progress_rate, 1),
                'confused_pulse_rate': round(confused_rate, 1),
                'formative_avg_score': fa_avg,
                'note_view_count': note_views,
            }
            student_data.append(s_data)

            # ── 위험군 판별 ──
            risk_reasons = []

            # 1. 연속 2회 이상 결석
            consecutive_absent = self._check_consecutive_absent(student, eligible_sessions)
            if consecutive_absent >= 2:
                risk_reasons.append(f'연속 {consecutive_absent}회 결석')

            # 2. 퀴즈 정답률 50% 미만
            if quiz_accuracy is not None and quiz_accuracy < 50:
                risk_reasons.append(f'퀴즈 정답률 {round(quiz_accuracy)}%')

            # 3. 펄스 혼란 60% 이상
            if confused_rate >= 60:
                risk_reasons.append(f'혼란 비율 {round(confused_rate)}%')

            # 4. 형성평가 미완료
            total_fas = FormativeAssessment.objects.filter(
                live_session__in=ended_sessions, status='DRAFT'
            ).count()
            completed_fas = fa_responses.count()
            if total_fas > 0 and completed_fas == 0:
                risk_reasons.append('형성평가 미완료')

            # 5. 진도율 40% 미만
            if obj_total > 0 and progress_rate < 40:
                risk_reasons.append(f'진도율 {round(progress_rate)}%')

            if risk_reasons:
                # 결석생 보충 학습 확인
                absent_sessions = eligible_sessions.exclude(id__in=attended)
                absent_note_viewed = False
                formative_completed = False
                for sess in absent_sessions:
                    try:
                        note = sess.note
                        if NoteViewLog.objects.filter(note=note, student=student).exists():
                            absent_note_viewed = True
                    except LiveSessionNote.DoesNotExist:
                        pass
                    if FormativeResponse.objects.filter(
                        student=student, assessment__live_session=sess
                    ).exists():
                        formative_completed = True

                at_risk.append({
                    **s_data,
                    'risk_reasons': risk_reasons,
                    'absent_note_viewed': absent_note_viewed,
                    'formative_completed': formative_completed,
                })

        # 평균 계산
        rates = [s['attendance_rate'] for s in student_data]
        quiz_rates = [s['quiz_accuracy'] for s in student_data if s['quiz_accuracy'] is not None]
        progress_rates = [s['progress_rate'] for s in student_data]

        return Response({
            'total_students': total_students,
            'session_count': session_count,
            'level_distribution': level_dist,
            'avg_attendance_rate': round(sum(rates) / len(rates), 1) if rates else 0,
            'avg_quiz_accuracy': round(sum(quiz_rates) / len(quiz_rates), 1) if quiz_rates else 0,
            'avg_progress_rate': round(sum(progress_rates) / len(progress_rates), 1) if progress_rates else 0,
            'at_risk_students': at_risk,
            'students': student_data,
        })

    def _get_level_distribution(self, lecture, students):
        dist = {'BEGINNER': 0, 'INTERMEDIATE': 0, 'ADVANCED': 0}
        for student in students:
            level = self._get_level(student, lecture)
            if level in dist:
                dist[level] += 1
        return dist

    def _get_level(self, student, lecture):
        pr = PlacementResult.objects.filter(
            student=student, lecture=lecture
        ).order_by('-created_at').first()
        return pr.level if pr else 'INTERMEDIATE'

    def _check_consecutive_absent(self, student, sessions):
        """최근부터 역순으로 연속 결석 수 계산"""
        max_consec = 0
        current = 0
        for session in sessions.order_by('-created_at'):
            participated = LiveParticipant.objects.filter(
                student=student, live_session=session
            ).exists()
            if not participated:
                current += 1
                max_consec = max(max_consec, current)
            else:
                current = 0
        return max_consec


class SendMessageView(APIView):
    """POST /api/learning/professor/{lecture_id}/send-message/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)

        student_ids = request.data.get('student_ids', [])
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        message_type = request.data.get('message_type', 'NOTICE')

        if not student_ids or not title or not content:
            return Response({'error': '필수 항목 누락'}, status=status.HTTP_400_BAD_REQUEST)

        msg = GroupMessage.objects.create(
            lecture=lecture,
            sender=request.user,
            target_level=0,
            target_students=student_ids,
            title=title,
            content=content,
            message_type=message_type,
        )
        return Response({'ok': True, 'message_id': msg.id}, status=status.HTTP_201_CREATED)


# ══════════════════════════════════════════════════════════
# Phase 3-2: 취약 구간 인사이트
# ══════════════════════════════════════════════════════════

class WeakInsightsView(APIView):
    """GET /api/learning/professor/{lecture_id}/analytics/weak-insights/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)
        ended_sessions = LiveSession.objects.filter(lecture=lecture, status='ENDED').order_by('created_at')
        total_students = lecture.students.count()

        if not ended_sessions.exists():
            return Response({'message': '아직 종료된 강의가 없습니다.', 'insights': [], 'session_comparison': []})

        # 1. 퀴즈 오답 집계 (question_text 기반)
        concept_wrong = defaultdict(lambda: {'quiz': 0, 'formative': 0, 'students': set(), 'session': '', 'wz': 0})

        quiz_wrongs = LiveQuizResponse.objects.filter(
            quiz__live_session__in=ended_sessions, is_correct=False
        ).select_related('quiz', 'quiz__live_session')

        for qr in quiz_wrongs:
            key = qr.quiz.question_text[:50]
            concept_wrong[key]['quiz'] += 1
            concept_wrong[key]['students'].add(qr.student_id)
            concept_wrong[key]['session'] = qr.quiz.live_session.title or ''

        # 2. 형성평가 오답 (concept_tag 기반)
        for fa in FormativeAssessment.objects.filter(live_session__in=ended_sessions):
            responses = FormativeResponse.objects.filter(assessment=fa)
            if not fa.questions:
                continue
            for resp in responses:
                if not resp.answers:
                    continue
                for i, q in enumerate(fa.questions):
                    q_num = str(i + 1)
                    student_ans = resp.answers.get(q_num, '')
                    correct_ans = q.get('correct_answer', '')
                    if student_ans and student_ans != correct_ans:
                        tag = q.get('concept_tag', q.get('question', '')[:50])
                        concept_wrong[tag]['formative'] += 1
                        concept_wrong[tag]['students'].add(resp.student_id)
                        concept_wrong[tag]['session'] = fa.live_session.title or ''

        # 3. WeakZone 빈도 반영
        for wz in WeakZoneAlert.objects.filter(live_session__in=ended_sessions):
            detail = (wz.trigger_detail or '')[:50]
            if detail:
                concept_wrong[detail]['wz'] += 1

        # 정렬 (오답 학생 수 기준)
        insights = []
        for concept, data in sorted(concept_wrong.items(), key=lambda x: len(x[1]['students']), reverse=True):
            wrong_rate = (len(data['students']) / total_students * 100) if total_students > 0 else 0
            insights.append({
                'concept': concept,
                'session_title': data['session'],
                'wrong_rate': round(wrong_rate, 1),
                'source': ('QUIZ+FORMATIVE' if data['quiz'] > 0 and data['formative'] > 0
                          else 'QUIZ' if data['quiz'] > 0 else 'FORMATIVE'),
                'quiz_wrong_count': data['quiz'],
                'formative_wrong_count': data['formative'],
                'affected_count': len(data['students']),
                'total_students': total_students,
                'weak_zone_count': data['wz'],
            })

        # 랭크 부여
        for i, ins in enumerate(insights[:20]):
            ins['rank'] = i + 1

        # 차시별 비교
        session_comparison = []
        for sess in ended_sessions:
            participants = LiveParticipant.objects.filter(live_session=sess)
            p_count = participants.count()

            # 이해율 (펄스)
            pulses = PulseLog.objects.filter(live_session=sess)
            p_total = pulses.count()
            p_understand = pulses.filter(pulse_type='UNDERSTAND').count()
            understand_rate = (p_understand / p_total * 100) if p_total > 0 else 0

            # 퀴즈 정답률
            qr = LiveQuizResponse.objects.filter(quiz__live_session=sess)
            qr_total = qr.count()
            qr_correct = qr.filter(is_correct=True).count()
            quiz_acc = (qr_correct / qr_total * 100) if qr_total > 0 else 0

            # 형성평가 평균
            fa_resps = FormativeResponse.objects.filter(assessment__live_session=sess)
            fa_avg = 0
            if fa_resps.exists():
                agg = fa_resps.aggregate(avg=Avg('score'))
                fa_avg = round(agg['avg'] or 0, 1)

            session_comparison.append({
                'session_id': sess.id,
                'session_title': sess.title or f'{sess.id}강',
                'date': str(sess.started_at.date()) if sess.started_at else '',
                'understand_rate': round(understand_rate, 1),
                'quiz_accuracy': round(quiz_acc, 1),
                'formative_avg': fa_avg,
                'participants': p_count,
            })

        return Response({
            'insights': insights[:20],
            'session_comparison': session_comparison,
        })


# ══════════════════════════════════════════════════════════
# Phase 3-3: AI 제안 승인 흐름
# ══════════════════════════════════════════════════════════

class AISuggestionsView(APIView):
    """GET /api/learning/professor/{lecture_id}/analytics/ai-suggestions/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)
        ended_sessions = LiveSession.objects.filter(lecture=lecture, status='ENDED')

        pending = []

        # ReviewRoute SUGGESTED
        for rr in ReviewRoute.objects.filter(
            live_session__in=ended_sessions, status='SUGGESTED'
        ).select_related('student', 'live_session'):
            pending.append({
                'type': 'REVIEW_ROUTE',
                'id': rr.id,
                'student_name': rr.student.username,
                'detail': f"{rr.live_session.title or ''} 복습 루트 ({rr.total_est_minutes}분)",
                'created_at': rr.created_at,
            })

        # WeakZoneAlert DETECTED
        for wz in WeakZoneAlert.objects.filter(
            live_session__in=ended_sessions, status='DETECTED'
        ).select_related('student', 'live_session'):
            pending.append({
                'type': 'WEAK_ZONE',
                'id': wz.id,
                'student_name': wz.student.username,
                'detail': (wz.ai_suggested_content or '')[:100],
                'created_at': wz.created_at,
            })

        # AdaptiveContent DRAFT
        for ac in AdaptiveContent.objects.filter(
            source_material__lecture=lecture, status='DRAFT'
        ).select_related('source_material'):
            pending.append({
                'type': 'ADAPTIVE_CONTENT',
                'id': ac.id,
                'student_name': '',
                'detail': f"{ac.source_material.title} Level {ac.level} 변형 초안",
                'created_at': ac.created_at,
            })

        # 시간순 정렬
        pending.sort(key=lambda x: x['created_at'], reverse=True)

        # 최근 판단 이력 (승인/거부된 것들)
        recent_decisions = []
        for rr in ReviewRoute.objects.filter(
            live_session__in=ended_sessions,
            status__in=['APPROVED', 'MODIFIED', 'REJECTED']
        ).order_by('-created_at')[:10]:
            recent_decisions.append({
                'type': 'REVIEW_ROUTE', 'action': rr.status,
                'detail': f"{rr.student.username} 복습 루트",
                'decided_at': rr.created_at,
            })

        return Response({
            'pending_suggestions': pending,
            'pending_count': len(pending),
            'recent_decisions': recent_decisions,
        })


class SuggestionActionView(APIView):
    """POST /api/learning/professor/suggestion-action/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        suggestion_type = request.data.get('type')
        suggestion_id = request.data.get('id')
        action = request.data.get('action')  # APPROVE, REJECT, MODIFY

        if suggestion_type == 'REVIEW_ROUTE':
            obj = get_object_or_404(ReviewRoute, id=suggestion_id)
            if action == 'APPROVE':
                obj.status = 'APPROVED'
            elif action == 'REJECT':
                obj.status = 'REJECTED'
            elif action == 'MODIFY':
                obj.status = 'MODIFIED'
                if 'items' in request.data:
                    obj.items = request.data['items']
            obj.save()

        elif suggestion_type == 'WEAK_ZONE':
            obj = get_object_or_404(WeakZoneAlert, id=suggestion_id)
            if action == 'APPROVE':
                obj.status = 'PUSHED'
            elif action == 'REJECT':
                obj.status = 'DISMISSED'
            obj.save()

        elif suggestion_type == 'ADAPTIVE_CONTENT':
            obj = get_object_or_404(AdaptiveContent, id=suggestion_id)
            if action == 'APPROVE':
                obj.status = 'APPROVED'
                obj.approved_at = timezone.now()
            elif action == 'REJECT':
                obj.status = 'REJECTED'
            obj.save()

        else:
            return Response({'error': '알 수 없는 제안 유형'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'ok': True, 'action': action})


# ══════════════════════════════════════════════════════════
# Phase 3-4: 그룹별 개입 + 강의 품질 리포트
# ══════════════════════════════════════════════════════════

class SendGroupMessageView(APIView):
    """POST /api/learning/professor/{lecture_id}/send-group-message/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)

        target_level = request.data.get('target_level', 0)
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        message_type = request.data.get('message_type', 'NOTICE')

        if not title or not content:
            return Response({'error': '제목과 내용은 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        msg = GroupMessage.objects.create(
            lecture=lecture,
            sender=request.user,
            target_level=target_level,
            title=title,
            content=content,
            message_type=message_type,
        )
        return Response({'ok': True, 'message_id': msg.id}, status=status.HTTP_201_CREATED)


class QualityReportView(APIView):
    """GET /api/learning/professor/{lecture_id}/analytics/quality-report/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)
        ended_sessions = LiveSession.objects.filter(lecture=lecture, status='ENDED').order_by('created_at')

        if not ended_sessions.exists():
            return Response({'message': '아직 종료된 강의가 없습니다.', 'sessions': [], 'trends': {}, 'level_redistribution': {}})

        sessions_data = []
        trends = {'understand_rate': [], 'quiz_accuracy': [], 'formative_completion': [], 'labels': []}

        for sess in ended_sessions:
            p_count = LiveParticipant.objects.filter(live_session=sess).count()

            # 이해율
            pulses = PulseLog.objects.filter(live_session=sess)
            pt = pulses.count()
            pu = pulses.filter(pulse_type='UNDERSTAND').count()
            understand = (pu / pt * 100) if pt > 0 else 0

            # 참여율
            total_s = lecture.students.count()
            participation = (p_count / total_s * 100) if total_s > 0 else 0

            # 퀴즈 정답률
            qr = LiveQuizResponse.objects.filter(quiz__live_session=sess)
            qt = qr.count()
            qc = qr.filter(is_correct=True).count()
            quiz_acc = (qc / qt * 100) if qt > 0 else 0

            # 체크포인트 통과율
            quizzes = LiveQuiz.objects.filter(live_session=sess)
            if quizzes.exists() and p_count > 0:
                students_passed = LiveQuizResponse.objects.filter(
                    quiz__in=quizzes, is_correct=True
                ).values('student').distinct().count()
                checkpoint = (students_passed / p_count * 100)
            else:
                checkpoint = 0

            # 형성평가 완료율
            fa_total = FormativeAssessment.objects.filter(live_session=sess).count()
            fa_completed = FormativeResponse.objects.filter(assessment__live_session=sess).count()
            fa_rate = (fa_completed / (fa_total * p_count) * 100) if fa_total > 0 and p_count > 0 else 0

            # WeakZone 수
            wz_count = WeakZoneAlert.objects.filter(live_session=sess).count()

            # 평균 혼란률
            confused = pulses.filter(pulse_type='CONFUSED').count()
            avg_confused = (confused / pt * 100) if pt > 0 else 0

            metrics = {
                'understand_rate': round(understand, 1),
                'participation_rate': round(participation, 1),
                'quiz_accuracy': round(quiz_acc, 1),
                'checkpoint_pass_rate': round(checkpoint, 1),
                'formative_completion_rate': round(fa_rate, 1),
                'weak_zone_count': wz_count,
                'avg_pulse_confused': round(avg_confused, 1),
            }

            sessions_data.append({
                'id': sess.id,
                'title': sess.title or f'{sess.id}강',
                'date': str(sess.started_at.date()) if sess.started_at else '',
                'participants': p_count,
                'metrics': metrics,
            })

            # 추이 데이터
            trends['understand_rate'].append(round(understand, 1))
            trends['quiz_accuracy'].append(round(quiz_acc, 1))
            trends['formative_completion'].append(round(fa_rate, 1))
            trends['labels'].append(sess.title or f'{sess.id}강')

        # 레벨 재분류 제안
        redistribution = self._suggest_redistribution(lecture, ended_sessions)

        return Response({
            'sessions': sessions_data,
            'trends': trends,
            'level_redistribution': redistribution,
        })

    def _suggest_redistribution(self, lecture, ended_sessions):
        """학생 레벨 재분류 제안"""
        students = lecture.students.all()
        level_map = {'BEGINNER': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
        reverse_map = {1: 'BEGINNER', 2: 'INTERMEDIATE', 3: 'ADVANCED'}

        current = {'BEGINNER': 0, 'INTERMEDIATE': 0, 'ADVANCED': 0}
        changes = []

        recent_sessions = ended_sessions.order_by('-created_at')[:3]

        for student in students:
            pr = PlacementResult.objects.filter(
                student=student, lecture=lecture
            ).order_by('-created_at').first()
            cur_level = pr.level if pr else 'INTERMEDIATE'
            current[cur_level] = current.get(cur_level, 0) + 1
            cur_num = level_map.get(cur_level, 2)

            # 최근 3세션 퀴즈 정답률
            qr = LiveQuizResponse.objects.filter(
                student=student, quiz__live_session__in=recent_sessions
            )
            qt = qr.count()
            qc = qr.filter(is_correct=True).count()
            recent_accuracy = (qc / qt * 100) if qt > 0 else 50

            # 형성평가 점수
            fa = FormativeResponse.objects.filter(
                student=student, assessment__live_session__in=recent_sessions
            )
            fa_avg = 50
            if fa.exists():
                agg = fa.aggregate(avg=Avg('score'))
                fa_avg = agg['avg'] or 50

            # WeakZone 건수
            wz = WeakZoneAlert.objects.filter(
                student=student, live_session__in=recent_sessions
            ).count()

            # 승급 판단
            new_level = cur_num
            reason = ''
            if recent_accuracy >= 80 and cur_num < 3:
                new_level = cur_num + 1
                reason = f'최근 퀴즈 정답률 {round(recent_accuracy)}%'
            elif fa_avg >= 80 and cur_num < 3:
                new_level = cur_num + 1
                reason = f'형성평가 평균 {round(fa_avg)}점'
            # 강등 판단
            elif recent_accuracy <= 40 and cur_num > 1:
                new_level = cur_num - 1
                reason = f'최근 퀴즈 정답률 {round(recent_accuracy)}%'
            elif fa_avg <= 40 and cur_num > 1:
                new_level = cur_num - 1
                reason = f'형성평가 평균 {round(fa_avg)}점'
            elif wz >= 3 and cur_num > 1:
                new_level = cur_num - 1
                reason = f'WeakZone {wz}건'

            if new_level != cur_num:
                changes.append({
                    'student_id': student.id,
                    'student_name': student.username,
                    'from': cur_level,
                    'to': reverse_map[new_level],
                    'reason': reason,
                })

        # 제안 분포 계산
        suggested = dict(current)
        for c in changes:
            suggested[c['from']] = suggested.get(c['from'], 0) - 1
            suggested[c['to']] = suggested.get(c['to'], 0) + 1

        return {
            'current': current,
            'suggested': suggested,
            'changes': changes,
        }


class ApplyRedistributionView(APIView):
    """POST /api/learning/professor/{lecture_id}/apply-redistribution/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, lecture_id):
        lecture = get_object_or_404(Lecture, id=lecture_id, instructor=request.user)
        changes = request.data.get('changes', [])

        applied = 0
        for change in changes:
            student_id = change.get('student_id')
            new_level = change.get('to')
            if student_id and new_level:
                PlacementResult.objects.create(
                    student_id=student_id,
                    lecture=lecture,
                    level=new_level,
                    score=0,
                    total_questions=0,
                    answers={},
                    category_scores={},
                )
                applied += 1

        return Response({'ok': True, 'applied': applied})


class MyMessagesView(APIView):
    """GET /api/learning/messages/my/ — 학습자 메시지 조회"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 내가 속한 강의의 메시지 중 (전체 대상 or 내 ID가 포함된 메시지)
        my_lectures = Lecture.objects.filter(students=user)

        messages = GroupMessage.objects.filter(
            lecture__in=my_lectures
        ).filter(
            Q(target_level=0, target_students=[]) |     # 전체 대상 (레벨 0 + 특정 학생 미지정)
            Q(target_students__contains=[user.id]) |    # 내 ID가 포함된 메시지
            Q(target_level__gt=0)                       # 레벨 기반 (아래에서 2차 필터링)
        ).order_by('-created_at')[:20]

        # 레벨 기반 필터 추가
        result = []
        for msg in messages:
            if msg.target_level > 0:
                # 레벨 기반이면 학생 레벨 확인
                pr = PlacementResult.objects.filter(
                    student=user, lecture=msg.lecture
                ).order_by('-created_at').first()
                level_map = {'BEGINNER': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
                student_level = level_map.get(pr.level, 2) if pr else 2
                if student_level != msg.target_level:
                    continue

            result.append({
                'id': msg.id,
                'title': msg.title,
                'content': msg.content,
                'message_type': msg.message_type,
                'sender': msg.sender.username,
                'lecture_title': msg.lecture.title,
                'created_at': msg.created_at,
                'is_read': user.id in msg.read_by,
            })

        unread_count = sum(1 for m in result if not m['is_read'])
        return Response({'messages': result, 'unread_count': unread_count})

    def post(self, request):
        """POST — 읽음 처리"""
        message_id = request.data.get('message_id')
        msg = get_object_or_404(GroupMessage, id=message_id)

        if request.user.id not in msg.read_by:
            msg.read_by = msg.read_by + [request.user.id]
            msg.save()

        return Response({'ok': True})
