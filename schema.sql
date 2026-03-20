-- 📊 Re:Boot Database Schema (DDL)
-- Based on: erd_design.md

-- ==========================================
-- 1. Curriculum Structure (커리큘럼 구조)
-- ==========================================

-- [Lecture] 강의/클래스 정보
CREATE TABLE IF NOT EXISTS courses_lecture (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    instructor_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    access_code VARCHAR(6) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- [Syllabus] 주차별 실라버스
CREATE TABLE IF NOT EXISTS courses_syllabus (
    id SERIAL PRIMARY KEY,
    lecture_id INTEGER REFERENCES courses_lecture(id) ON DELETE CASCADE,
    week_number INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    UNIQUE(lecture_id, week_number)
);

-- [LearningObjective] 학습 목표 & 체크포인트
CREATE TABLE IF NOT EXISTS courses_learningobjective (
    id SERIAL PRIMARY KEY,
    syllabus_id INTEGER REFERENCES courses_syllabus(id) ON DELETE CASCADE,
    content VARCHAR(300) NOT NULL,
    "order" INTEGER DEFAULT 0,
    is_checkpoint BOOLEAN DEFAULT FALSE -- [New] 필수 통과 지점 여부
);


-- ==========================================
-- 2. Learning Activities (학습 활동)
-- ==========================================

-- [LearningSession] 개별 학습 세션
CREATE TABLE IF NOT EXISTS learning_learningsession (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    lecture_id INTEGER REFERENCES courses_lecture(id) ON DELETE SET NULL,
    section_id INTEGER REFERENCES courses_coursesection(id) ON DELETE CASCADE, -- (Legacy)
    session_order INTEGER NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    is_completed BOOLEAN DEFAULT FALSE,
    youtube_url VARCHAR(500),
    context_summary TEXT, -- [New] AI Tutor Context
    last_compressed_at TIMESTAMP WITH TIME ZONE
);

-- [STTLog] 실시간 자막 로그
CREATE TABLE IF NOT EXISTS learning_sttlog (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES learning_learningsession(id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL,
    text_chunk TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- [DailyQuiz] 일일 퀴즈
CREATE TABLE IF NOT EXISTS learning_dailyquiz (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    quiz_date DATE DEFAULT CURRENT_DATE,
    total_score INTEGER DEFAULT 0,
    is_passed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- [QuizQuestion] 퀴즈 문항
CREATE TABLE IF NOT EXISTS learning_quizquestion (
    id SERIAL PRIMARY KEY,
    quiz_id INTEGER REFERENCES learning_dailyquiz(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    options JSONB, -- PostgreSQL JSONB
    correct_answer VARCHAR(255),
    explanation TEXT
);

-- [QuizAttempt] 퀴즈 응시 기록
CREATE TABLE IF NOT EXISTS learning_quizattempt (
    id SERIAL PRIMARY KEY,
    quiz_id INTEGER REFERENCES learning_dailyquiz(id) ON DELETE CASCADE,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- ==========================================
-- 3. Assetization & Analytics (자산화)
-- ==========================================

-- [StudentChecklist] 개별 목표 달성 현황
CREATE TABLE IF NOT EXISTS learning_studentchecklist (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    objective_id INTEGER REFERENCES courses_learningobjective(id) ON DELETE CASCADE,
    is_checked BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, objective_id)
);

-- [SkillBlock] 획득 스킬 자산 (New)
CREATE TABLE IF NOT EXISTS career_skillblock (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL, -- ex: 'React Hooks'
    level INTEGER DEFAULT 1, -- 1~5
    acquired_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    source_lecture_id INTEGER REFERENCES courses_lecture(id) ON DELETE SET NULL
);

-- [StudentCurriculumState] 리라우팅 상태 (New)
CREATE TABLE IF NOT EXISTS analytics_studentcurriculumstate (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    current_week INTEGER DEFAULT 1,
    risk_level VARCHAR(20) DEFAULT 'SAFE', -- SAFE, WARNING, CRITICAL
    recommended_path JSONB, -- AI Re-routing Path
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- ==========================================
-- 4. Career Outputs (결과물)
-- ==========================================

-- [Portfolio] 생성된 포트폴리오
CREATE TABLE IF NOT EXISTS career_portfolio (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    portfolio_type VARCHAR(10) NOT NULL, -- JOB, STARTUP
    title VARCHAR(200),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- [MockInterview] AI 모의 면접 세션
CREATE TABLE IF NOT EXISTS career_mockinterview (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    portfolio_id INTEGER REFERENCES career_portfolio(id) ON DELETE SET NULL,
    persona VARCHAR(20) DEFAULT 'TECH_LEAD',
    status VARCHAR(20) DEFAULT 'IN_PROGRESS',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- [InterviewExchange] 문답 로그
CREATE TABLE IF NOT EXISTS career_interviewexchange (
    id SERIAL PRIMARY KEY,
    interview_id INTEGER REFERENCES career_mockinterview(id) ON DELETE CASCADE,
    question TEXT,
    answer TEXT,
    feedback TEXT,
    score INTEGER DEFAULT 0,
    "order" INTEGER DEFAULT 1
);
