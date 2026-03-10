from .utils_text import check_answer_match
"""
Phase 2-4: 사후 형성평가 API Views
"""
import json
import os
from datetime import timedelta

import openai
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    FormativeAssessment, FormativeResponse,
    LiveSession, LiveSessionNote, SpacedRepetitionItem,
    StudentSkill, Skill, LiveParticipant,
)


class MyPendingFormativeView(APIView):
    """GET /api/learning/formative/my-pending/ — 미완료 형성평가 목록 (학생)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 내가 참여한 세션의 READY 형성평가 중, 아직 안 푼 것
        my_sessions = LiveParticipant.objects.filter(
            student=request.user
        ).values_list('live_session_id', flat=True)

        ready_fas = FormativeAssessment.objects.filter(
            live_session_id__in=my_sessions,
            status='READY',
        ).exclude(
            responses__student=request.user,
        ).select_related('live_session')

        data = []
        for fa in ready_fas:
            data.append({
                'assessment_id': fa.id,
                'session_id': fa.live_session_id,
                'session_title': getattr(fa.live_session, 'title', ''),
                'total_questions': fa.total_questions,
                'created_at': fa.created_at.isoformat(),
            })

        return Response(data)


class GenerateFormativeView(APIView):
    """POST /api/learning/formative/{session_id}/generate/ — 교수자가 형성평가 생성 트리거"""
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id, instructor=request.user)
        note = LiveSessionNote.objects.filter(live_session=session, status='DONE').first()
        if not note:
            return Response({'error': '완료된 통합 노트가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 이미 생성된 평가가 있으면 반환
        existing = FormativeAssessment.objects.filter(live_session=session).first()
        if existing and existing.status == 'READY':
            return Response({
                'id': existing.id,
                'status': existing.status,
                'total_questions': existing.total_questions,
            })

        # AI 문항 생성
        fa = FormativeAssessment.objects.create(
            live_session=session,
            note=note,
            status='GENERATING',
        )

        try:
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            note_content = note.content[:3000]  # 토큰 절약

            # [RAG] 공식 문서에서 관련 컨텍스트 검색
            rag_context = ""
            try:
                from .rag import RAGService
                rag = RAGService()
                lecture_id = session.lecture_id if session.lecture else None
                related_docs = rag.search(query=note_content[:500], top_k=3, lecture_id=lecture_id)
                if related_docs:
                    rag_context = "\n".join([f"- {doc.content[:300]}" for doc in related_docs])
                    print(f"✅ [RAG] 형성평가 문항 생성에 공식 문서 {len(related_docs)}건 참조")
            except Exception as rag_err:
                print(f"⚠️ [RAG] 형성평가 검색 실패: {rag_err}")

            user_content = f'아래 수업 노트를 기반으로 형성평가 5문항을 생성하세요:\n\n{note_content}'
            if rag_context:
                user_content += f'\n\n[공식 문서 참조 (정확한 정의 및 예시)]:\n{rag_context}'

            response = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': (
                        '당신은 교육 평가 전문가입니다.\n'
                        '주어진 수업 노트를 기반으로 형성평가 문항을 5개 생성하세요.\n'
                        '[공식 문서 참조]가 있으면, 전문 용어의 정확한 정의에 기반한 문항을 포함하세요.\n\n'
                        '반드시 아래 JSON 형식으로 응답하세요:\n'
                        '{"questions": [{"id": 1, "question": "질문", "options": ["A) 보기1", "B) 보기2", "C) 보기3", "D) 보기4"], '
                        '"correct_answer": "A) 보기1", "explanation": "해설", '
                        '"related_note_section": "관련 섹션", "concept_tag": "개념명"}]}\n\n'
                        '규칙:\n'
                        '1. 4지선다 객관식만\n'
                        '2. correct_answer는 options 중 하나와 정확히 일치\n'
                        '3. concept_tag는 2-4자 핵심 개념명 (예: 클로저, DOM, 비동기)\n'
                        '4. 난이도: 이해력 확인 수준 (암기 X)'
                    )},
                    {'role': 'user', 'content': user_content}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={'type': 'json_object'},
            )

            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            questions = parsed.get('questions', parsed) if isinstance(parsed, dict) else parsed
            if isinstance(questions, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        questions = v
                        break

            fa.questions = questions
            fa.total_questions = len(questions)
            fa.status = 'READY'
            fa.save()

            return Response({
                'id': fa.id,
                'status': 'READY',
                'total_questions': fa.total_questions,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            fa.status = 'FAILED'
            fa.save()
            print(f"❌ [Formative] 문항 생성 실패: {e}")
            return Response({'error': f'문항 생성 실패: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetFormativeView(APIView):
    """GET /api/learning/formative/{session_id}/ — 형성평가 문항 조회 (학생용)"""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        fa = FormativeAssessment.objects.filter(live_session=session, status='READY').first()
        if not fa:
            return Response({'available': False})

        # 이미 제출했는지 확인
        existing_response = FormativeResponse.objects.filter(assessment=fa, student=request.user).first()

        # 학생에게는 정답/해설 제거
        questions_for_student = []
        for q in (fa.questions or []):
            questions_for_student.append({
                'id': q.get('id'),
                'question': q.get('question'),
                'options': q.get('options'),
            })

        return Response({
            'available': True,
            'assessment_id': fa.id,
            'total_questions': fa.total_questions,
            'questions': questions_for_student,
            'already_submitted': existing_response is not None,
            'score': existing_response.score if existing_response else None,
            'total': existing_response.total if existing_response else None,
        })


class SubmitFormativeView(APIView):
    """POST /api/learning/formative/{fa_id}/submit/ — 형성평가 제출"""
    permission_classes = [IsAuthenticated]

    def post(self, request, fa_id):
        fa = get_object_or_404(FormativeAssessment, id=fa_id, status='READY')

        # 중복 제출 방지
        if FormativeResponse.objects.filter(assessment=fa, student=request.user).exists():
            return Response({'error': '이미 제출한 평가입니다.'}, status=status.HTTP_409_CONFLICT)

        user_answers = request.data.get('answers', [])  # [{ question_id, answer }]
        if not user_answers:
            return Response({'error': 'answers는 필수입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 채점
        questions_map = {q['id']: q for q in (fa.questions or [])}
        results = []
        score = 0
        wrong_concepts = []

        for ua in user_answers:
            qid = ua.get('question_id')
            user_ans = ua.get('answer', '').strip()
            q = questions_map.get(qid)
            if not q:
                continue

            is_correct = check_answer_match(user_ans, q.get('correct_answer', ''))
            if is_correct:
                score += 1
            else:
                wrong_concepts.append({
                    'concept_tag': q.get('concept_tag', ''),
                    'question': q.get('question', ''),
                    'correct_answer': q.get('correct_answer', ''),
                    'explanation': q.get('explanation', ''),
                    'options': q.get('options', []),
                })

            results.append({
                'question_id': qid,
                'answer': user_ans,
                'is_correct': is_correct,
                'correct_answer': q.get('correct_answer', ''),
                'explanation': q.get('explanation', ''),
            })

        total = len(results)

        fr = FormativeResponse.objects.create(
            assessment=fa,
            student=request.user,
            answers=results,
            score=score,
            total=total,
        )

        # 오답 → SR 자동 등록 + 갭 맵 업데이트
        if wrong_concepts:
            self._create_sr_from_wrong(request.user, fa, wrong_concepts)
            self._update_gap_map(request.user, wrong_concepts)
            fr.sr_items_created = True
            fr.save()

        return Response({
            'score': score,
            'total': total,
            'results': results,
            'sr_items_created': len(wrong_concepts),
        })

    def _create_sr_from_wrong(self, student, fa, wrong_concepts):
        """오답 개념→SR 자동 등록"""
        now = timezone.now()
        for wc in wrong_concepts:
            concept = wc['concept_tag'] or wc['question'][:60]

            if SpacedRepetitionItem.objects.filter(
                student=student,
                concept_name=concept[:200],
            ).exists():
                continue

            schedule = [
                {'review_num': 1, 'label': '10분 후', 'due_at': (now + timedelta(minutes=10)).isoformat(), 'completed': False},
                {'review_num': 2, 'label': '1일 후', 'due_at': (now + timedelta(days=1)).isoformat(), 'completed': False},
                {'review_num': 3, 'label': '1주일 후', 'due_at': (now + timedelta(weeks=1)).isoformat(), 'completed': False},
                {'review_num': 4, 'label': '1개월 후', 'due_at': (now + timedelta(days=30)).isoformat(), 'completed': False},
                {'review_num': 5, 'label': '6개월 후', 'due_at': (now + timedelta(days=180)).isoformat(), 'completed': False},
            ]

            SpacedRepetitionItem.objects.create(
                student=student,
                concept_name=concept[:200],
                source_session=fa.live_session,
                review_question=wc['question'],
                review_answer=wc['correct_answer'],
                review_options=wc.get('options', []),
                schedule=schedule,
            )

    def _update_gap_map(self, student, wrong_concepts):
        """오답 concept_tag → StudentSkill 업데이트 (부분 일치 + 로깅)"""
        for wc in wrong_concepts:
            tag = wc.get('concept_tag', '')
            if not tag:
                continue

            # 부분 일치 검색
            skill = Skill.objects.filter(name__icontains=tag).first()
            if not skill:
                print(f"⚠️ [GapMap] concept_tag '{tag}' → Skill 매칭 실패 (AI Fallback 필요)")
                continue

            student_skill, _ = StudentSkill.objects.update_or_create(
                student=student,
                skill=skill,
                defaults={
                    'status': 'WEAK',
                    'progress': max(0, (StudentSkill.objects.filter(student=student, skill=skill).first() or type('', (), {'progress': 50})).progress - 10),
                }
            )
            print(f"📊 [GapMap] {student.username}: {skill.name} → WEAK (progress -= 10)")
