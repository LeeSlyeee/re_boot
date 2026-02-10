# 📊 학습 성취도 분석 및 취약점 파악 시스템 (Analytics & Alerts)

## 1. 개요

강사가 학생들의 학습 진행 상황을 정량적으로 파악하고, 클래스 전체의 취약점을 발견하여 보충 교육을 할 수 있도록 지원하는 기능을 추가합니다.
`향후계획.txt`에 명시된 "학생 개별 체크리스트 확인"과 "클래스 공통 취약점 로직"을 구현합니다.

## 2. 목표 (Objectives)

### Objetivo 1: 학생별 학업 성취도 상세 파악

- **Feature**: 강사가 학생 목록에서 특정 학생을 선택하면, 해당 학생의 주차별/학습목표별 체크리스트 달성 현황을 상세히 조회.
- **Value**: 성취도가 낮은 학생에게 맞춤형 피드백이나 상담을 제공할 수 있는 근거 데이터 확보.

### Objetivo 2: 클래스 공통 취약점 자동 분석

- **Feature**: 클래스 전체 학생의 체크리스트 데이터를 분석하여, 성취율이 특정 임계값(예: 50%) 미만인 학습 목표를 자동으로 식별.
- **Value**: "이해도가 낮은 구간"을 파악하여 다음 수업 시 보충 강의를 하거나 추가 자료를 배포할 수 있음.

---

## 3. 기술적 구현 계획 (Technical Implementation)

### A. Backend (Django API)

#### 1. Analytics ViewSet 구현 (`backend/learning/views_analytics.py`)

새로운 뷰셋을 생성하여 통계 및 분석 로직을 분리합니다.

- `GET /api/learning/lectures/{id}/analytics/overview/`
  - **기능**: 클래스 전체의 주차별/목표별 평균 성취율 계산.
  - **로직**:
    1. 해당 강의의 모든 `Syllabus` 및 `LearningObjective` 조회.
    2. 각 Objective별로 `StudentChecklist`에서 `is_checked=True`인 학생 수 카운트.
    3. `(체크한 학생 수 / 전체 수강생 수) * 100` 계산.
    4. 성취율이 50% 미만인 항목은 `is_weak_point: true` 플래그 설정.

- `GET /api/learning/lectures/{id}/analytics/student/{student_id}/`
  - **기능**: 특정 학생의 체크리스트 현황 조회.
  - **로직**: 해당 학생이 체크한 항목과 체크하지 않은 항목을 구분하여 반환 (시각화 용이한 구조).

### B. Frontend (Professor Dashboard)

#### 1. 클래스 분석 대시보드 (`LectureAnalytics.vue`)

- **위치**: 강의 상세 페이지(`LectureDetailView`)에 새로운 탭 "📊 성취도 분석" 추가.
- **구성 요소**:
  - **취약점 알림판**: "🚨 이번 주 보충 필요: [React Hooks 심화] (성취율 30%)" 형태의 알림 배너.
  - **주차별 성취도 차트**: 주차별 평균 성취율을 막대 그래프로 표시.
  - **히트맵(Heatmap)**: 주차별 x 학습목표별 성취도를 색상으로 표시 (초록색=높음, 빨간색=낮음).

#### 2. 학생 상세 모달 (`StudentDetailModal.vue`)

- **동작**: 학생 리스트 테이블에서 학생 이름 클릭 시 모달 오픈.
- **구성 요소**:
  - **개인 학습 맵**: 전체 커리큘럼 중 도달한 부분과 빈 부분을 시각적으로 표시.
  - **미달성 리스트**: 아직 체크하지 않은 핵심 학습 목표 목록 표시.

---

## 4. 진행 순서 (Timeline)

1.  **Backend**: `StudentChecklist` 집계 쿼리 작성 및 API 엔드포인트 구현 (30분)
2.  **Frontend**: 강사 대시보드에 분석 컴포넌트 추가 및 차트 라이브러리(선택사항) 통합 (40분)
3.  **Integration**: API 연동 및 취약점 알림 로직 테스트 (20분)
