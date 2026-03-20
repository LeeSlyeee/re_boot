"""
분석/메시징 모델: NoteViewLog, GroupMessage
"""
from django.db import models
from django.conf import settings
from .base import Lecture


# ══════════════════════════════════════════════════════════
# Phase 3: 교수자 대시보드 분석
# ══════════════════════════════════════════════════════════

class NoteViewLog(models.Model):
    """결석 노트 열람 추적"""
    note = models.ForeignKey('LiveSessionNote', on_delete=models.CASCADE, related_name='view_logs')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='note_views')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        unique_together = ['note', 'student']

    def __str__(self):
        return f"[NoteView] {self.student.username} → {self.note_id}"


class GroupMessage(models.Model):
    """그룹별 타겟 메시지"""
    LEVEL_CHOICES = ((0, '전체'), (1, 'Level 1'), (2, 'Level 2'), (3, 'Level 3'))
    TYPE_CHOICES = (
        ('NOTICE', '공지'),
        ('TASK', '추가 과제'),
        ('FEEDBACK', '1:1 피드백 요청'),
        ('SUPPLEMENT', '보충 자료'),
    )

    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='group_messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    target_level = models.IntegerField(choices=LEVEL_CHOICES, default=0)
    target_students = models.JSONField(default=list, help_text="특정 학생 ID 목록 (빈 리스트면 레벨 기준)")
    title = models.CharField(max_length=200)
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='NOTICE')
    read_by = models.JSONField(default=list, help_text="읽은 학생 ID 목록")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'learning'
        ordering = ['-created_at']

    def __str__(self):
        return f"[Msg] {self.title} → L{self.target_level}"
