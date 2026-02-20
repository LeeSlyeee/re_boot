"""
Phase 2-1: Weak Zone 감지 + AI 보충 설명 헬퍼 함수
LiveSessionViewSet의 @action에서 호출됨 (View 아님)
"""
from datetime import timedelta
from django.utils import timezone
from .models import WeakZoneAlert, PulseLog, LiveQuizResponse


def check_quiz_weak_zone(session, student, current_quiz_response):
    """
    퀴즈 오답 후 호출: 최근 2개 연속 오답 시 WeakZoneAlert 생성
    """
    if current_quiz_response.is_correct:
        return None

    # 최근 2개 응답 확인 (방금 것 포함)
    recent_responses = LiveQuizResponse.objects.filter(
        quiz__live_session=session,
        student=student,
    ).order_by('-responded_at')[:2]

    if len(recent_responses) < 2:
        return None

    # 2개 모두 오답?
    if all(not r.is_correct for r in recent_responses):
        # 5분 내 동일 트리거 중복 방지
        five_min_ago = timezone.now() - timedelta(minutes=5)
        if WeakZoneAlert.objects.filter(
            live_session=session,
            student=student,
            trigger_type='QUIZ_WRONG',
            created_at__gte=five_min_ago,
        ).exists():
            return None

        # 최근 퀴즈 주제 추출
        recent_topic = recent_responses[0].quiz.question_text[:50]

        alert = WeakZoneAlert.objects.create(
            live_session=session,
            student=student,
            trigger_type='QUIZ_WRONG',
            trigger_detail={
                'quiz_ids': [r.quiz.id for r in recent_responses],
                'recent_topic': recent_topic,
            },
        )
        # AI 보충 설명 비동기 생성 (간단하면 동기도 가능)
        _generate_ai_supplement(alert)
        return alert

    return None


def check_pulse_weak_zone(session, student):
    """
    펄스 CONFUSED 후 호출: 3분 내 CONFUSED 2회 이상 시 WeakZoneAlert 생성
    """
    three_min_ago = timezone.now() - timedelta(minutes=3)

    confused_count = PulseLog.objects.filter(
        live_session=session,
        student=student,
        pulse_type='CONFUSED',
        created_at__gte=three_min_ago,
    ).count()

    if confused_count < 2:
        return None

    # 5분 내 중복 방지
    five_min_ago = timezone.now() - timedelta(minutes=5)
    if WeakZoneAlert.objects.filter(
        live_session=session,
        student=student,
        trigger_type__in=['PULSE_CONFUSED', 'COMBINED'],
        created_at__gte=five_min_ago,
    ).exists():
        return None

    # 퀴즈 오답도 있으면 COMBINED
    recent_wrong = LiveQuizResponse.objects.filter(
        quiz__live_session=session,
        student=student,
        is_correct=False,
        responded_at__gte=three_min_ago,
    ).exists()

    trigger_type = 'COMBINED' if recent_wrong else 'PULSE_CONFUSED'

    # 최근 STT에서 주제 추출 시도
    from .models import LiveSTTLog
    recent_stt = LiveSTTLog.objects.filter(
        live_session=session,
    ).order_by('-created_at').first()
    recent_topic = recent_stt.text_chunk[:50] if recent_stt else '현재 수업 내용'

    alert = WeakZoneAlert.objects.create(
        live_session=session,
        student=student,
        trigger_type=trigger_type,
        trigger_detail={
            'confused_count': confused_count,
            'recent_topic': recent_topic,
        },
    )
    _generate_ai_supplement(alert)
    return alert


def _generate_ai_supplement(alert):
    """AI 보충 설명 생성 (GPT-4o-mini)"""
    try:
        import openai
        topic = alert.trigger_detail.get('recent_topic', '현재 수업 내용')

        response = openai.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': '당신은 친절한 교육 보조 AI입니다. 학생이 어려워하는 개념을 쉽게 설명해주세요.'},
                {'role': 'user', 'content': f"""학생이 '{topic}' 부분에서 어려움을 겪고 있습니다.

다음 형식으로 200자 이내의 보충 설명을 작성하세요:
1. 핵심 개념 한 줄 정리
2. 쉬운 비유 또는 예시 1개
3. "이것만 기억하세요" 한 줄"""},
            ],
            max_tokens=300,
            temperature=0.7,
        )

        alert.ai_suggested_content = response.choices[0].message.content.strip()
        alert.save()
    except Exception as e:
        print(f"⚠️ [WeakZone] AI 보충 생성 실패: {e}")
        alert.ai_suggested_content = f"📌 '{alert.trigger_detail.get('recent_topic', '')}' 부분을 다시 한번 살펴보세요."
        alert.save()
