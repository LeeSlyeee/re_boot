"""
Learning 앱 모델 패키지
모든 모델을 re-export하여 기존 `from .models import ...` 구문과 100% 호환.
"""

# === 기본 모델 (강의, 실라버스, 학습 목표) ===
from .base import (
    VectorStore,
    Lecture,
    Syllabus,
    LearningObjective,
    StudentChecklist,
)

# === 학습 세션 모델 ===
from .session import (
    LearningSession,
    STTLog,
    SessionSummary,
    RecordingUpload,
)

# === 퀴즈 및 평가 모델 ===
from .quiz import (
    DailyQuiz,
    QuizQuestion,
    QuizAttempt,
    AttemptDetail,
)

# === 라이브 세션 모델 ===
from .live import (
    LiveSession,
    LiveParticipant,
    LectureMaterial,
    LiveSTTLog,
    PulseCheck,
    PulseLog,
    LiveQuiz,
    LiveQuizResponse,
    LiveQuestion,
    LiveSessionNote,
    WeakZoneAlert,
)

# === 적응형/복습/형성평가 모델 ===
from .adaptive import (
    AdaptiveContent,
    ReviewRoute,
    SpacedRepetitionItem,
    FormativeAssessment,
    FormativeResponse,
)

# === 분석/메시징 모델 ===
from .analytics import (
    NoteViewLog,
    GroupMessage,
)

# === 수준 진단 및 갭 맵 모델 ===
from .placement import (
    Skill,
    CareerGoal,
    PlacementQuestion,
    PlacementResult,
    StudentGoal,
    StudentSkill,
    SkillBlock,
)

__all__ = [
    # base
    'VectorStore', 'Lecture', 'Syllabus', 'LearningObjective', 'StudentChecklist',
    # session
    'LearningSession', 'STTLog', 'SessionSummary', 'RecordingUpload',
    # quiz
    'DailyQuiz', 'QuizQuestion', 'QuizAttempt', 'AttemptDetail',
    # live
    'LiveSession', 'LiveParticipant', 'LectureMaterial', 'LiveSTTLog',
    'PulseCheck', 'PulseLog', 'LiveQuiz', 'LiveQuizResponse',
    'LiveQuestion', 'LiveSessionNote', 'WeakZoneAlert',
    # adaptive
    'AdaptiveContent', 'ReviewRoute', 'SpacedRepetitionItem',
    'FormativeAssessment', 'FormativeResponse',
    # analytics
    'NoteViewLog', 'GroupMessage',
    # placement
    'Skill', 'CareerGoal', 'PlacementQuestion', 'PlacementResult',
    'StudentGoal', 'StudentSkill', 'SkillBlock',
]
