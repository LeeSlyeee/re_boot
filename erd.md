# Re:Boot 서비스 ERD (Entity Relationship Diagram)

이 문서는 Re:Boot 서비스의 데이터베이스 스키마 구조를 정의합니다.
**MariaDB**를 기준으로 설계되었으며, 사용자의 학습 흐름(세션 -> 요약 -> 퀴즈 -> 평가)을 중심으로 관계가 형성되어 있습니다.

## 1. Mermaid ER Diagram

```mermaid
erDiagram
    %% 사용자 및 그룹 관리 %%
    USER {
        bigint id PK
        string username
        string email
        string password
        enum role "STUDENT, INSTRUCTOR, MANAGER"
        datetime created_at
    }

    CLASS_GROUP {
        bigint id PK
        string name "반 이름 (예: 풀스택 3기 A반)"
        bigint manager_id FK "Users.id (Manager)"
        datetime start_date
        datetime end_date
    }

    ENROLLMENT {
        bigint id PK
        bigint student_id FK "Users.id (Student)"
        bigint class_id FK "ClassGroup.id"
        datetime joined_at
    }

    %% 커리큘럼 및 학습 세션 관리 %%
    COURSE_SECTION {
        bigint id PK
        string title "수업 주제"
        int day_sequence "1일차, 2일차..."
        text description
    }

    LEARNING_SESSION {
        bigint id PK
        bigint student_id FK "Users.id"
        bigint section_id FK "CourseSection.id"
        date session_date
        int session_order "1교시, 2교시..."
        boolean is_completed
        timestamp start_time
        timestamp end_time
    }

    %% AI 요약 및 데이터 자산 %%
    SESSION_SUMMARY {
        bigint id PK
        bigint session_id FK "LearningSession.id"
        text content_summary "AI 요약 텍스트"
        text raw_stt_path "STT 원본 파일 경로"
        datetime created_at
    }

    %% 퀴즈 및 평가 %%
    DAILY_QUIZ {
        bigint id PK
        bigint student_id FK "Users.id"
        bigint section_id FK "CourseSection.id"
        date quiz_date
        int total_score
        boolean is_passed
        datetime created_at
    }

    QUIZ_QUESTION {
        bigint id PK
        bigint quiz_id FK "DailyQuiz.id"
        text question_text
        json options "보기 목록 (JSON)"
        string correct_answer
        text explanation
    }

    QUIZ_ATTEMPT {
        bigint id PK
        bigint quiz_id FK "DailyQuiz.id"
        bigint student_id FK "Users.id"
        int score
        datetime submitted_at
    }

    ATTEMPT_DETAIL {
        bigint id PK
        bigint attempt_id FK "QuizAttempt.id"
        bigint question_id FK "QuizQuestion.id"
        string student_answer
        boolean is_correct
    }

    %% 관계 정의 %%
    USER ||--o{ ENROLLMENT : "enrolls in"
    CLASS_GROUP ||--o{ ENROLLMENT : "has students"
    USER ||--o{ CLASS_GROUP : "manages (Manager)"

    USER ||--o{ LEARNING_SESSION : "takes"
    COURSE_SECTION ||--o{ LEARNING_SESSION : "defines"
    LEARNING_SESSION ||--o| SESSION_SUMMARY : "generates"

    USER ||--o{ DAILY_QUIZ : "assigned"
    DAILY_QUIZ ||--o{ QUIZ_QUESTION : "contains"

    USER ||--o{ QUIZ_ATTEMPT : "solves"
    DAILY_QUIZ ||--o{ QUIZ_ATTEMPT : "records"
    QUIZ_ATTEMPT ||--o{ ATTEMPT_DETAIL : "details"
    QUIZ_QUESTION ||--o{ ATTEMPT_DETAIL : "references"
```

## 2. 테이블 상세 설명

### A. 회원 및 조직 (User & Organization)

| Table           | 설명                                  | 비고                           |
| :-------------- | :------------------------------------ | :----------------------------- |
| **USER**        | 모든 사용자 정보 (학생, 강사, 매니저) | `role` 필드로 권한 구분        |
| **CLASS_GROUP** | 반(Class) 정보                        | 매니저 1명이 담당              |
| **ENROLLMENT**  | 학생과 반의 N:M 관계 매핑             | 학생이 어느 반에 속했는지 기록 |

### B. 학습 흐름 (Learning Flow)

| Table                | 설명                                         | 비고                       |
| :------------------- | :------------------------------------------- | :------------------------- |
| **COURSE_SECTION**   | 정규 커리큘럼의 하루 단위 수업 정보          | 예: "Python 기초 (1일차)"  |
| **LEARNING_SESSION** | 학생별 실제 학습 기록 (교시 단위)            | 실시간 STT가 발생하는 단위 |
| **SESSION_SUMMARY**  | **[핵심]** 매 교시 쉬는 시간 생성되는 요약본 | 퀴즈 생성의 Source Data    |

### C. 평가 시스템 (Assessment System)

| Table              | 설명                                 | 비고                                    |
| :----------------- | :----------------------------------- | :-------------------------------------- |
| **DAILY_QUIZ**     | 하루 수업 종료 후 생성되는 퀴즈 세트 | `SessionSummary` 데이터를 기반으로 생성 |
| **QUIZ_QUESTION**  | 개별 문제 (5문제)                    | 객관식 보기 및 정답 포함                |
| **QUIZ_ATTEMPT**   | 학생의 퀴즈 응시 결과 헤더           | 총점 저장                               |
| **ATTEMPT_DETAIL** | 문항별 정답/오답 상세 기록           | 오답 노트 및 취약점 분석용              |
