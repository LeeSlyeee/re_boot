# Re:Boot 프로젝트 실행 가이드

## 1. 사전 요구 사항 (Prerequisites)

- **Python** 3.10 이상
- **Node.js** 18.0 이상
- **MariaDB** (로컬 설치 및 실행 필요)

---

## 2. 백엔드 실행 (Backend)

### 2.1 가상환경 활성화 및 패키지 설치

터미널을 열고 프로젝트 루트(`re_boot`)에서 다음 명령어를 순서대로 입력합니다.

```bash
# 가상환경 활성화
source venv/bin/activate

# 필수 패키지 설치
pip install django djangorestframework django-cors-headers mysqlclient python-dotenv openai djangorestframework-simplejwt
```

### 2.2 데이터베이스 연결 설정

- `backend/reboot_api/settings.py` 파일의 `DATABASES` 항목이 로컬 MariaDB 설정과 맞는지 확인합니다.
- 기본 설정:
  - **User**: root
  - **Password**: 1q2w3e4r
  - **Port**: 3306

### 2.3 마이그레이션 및 관리자 계정 생성

```bash
cd backend

# DB 마이그레이션 (테이블 생성)
python manage.py makemigrations
python manage.py migrate

# 슈퍼유저(관리자) 생성 (선택)
python manage.py createsuperuser
```

### 2.4 서버 실행

```bash
python manage.py runserver
# 실행 주소: http://localhost:8000
```

---

## 3. 프론트엔드 실행 (Frontend)

### 3.1 패키지 설치 및 실행

새로운 터미널 탭을 열고 `re_boot/frontend` 폴더로 이동합니다.

```bash
cd frontend

# 의존성 패키지 설치
npm install

# 개발 서버 실행
npm run dev
# 실행 주소: http://localhost:5173
```

---

## 4. 테스트 계정 정보

원활한 테스트를 위해 이미 생성된 테스트 계정을 사용할 수 있습니다.

- **ID**: `testuser`
- **PW**: `testpass123`

## 5. 주요 기능 테스트 흐름

1.  **로그인**: `http://localhost:5173` 접속 후 우측 상단 '로그인' 버튼 클릭 -> 위 테스트 계정으로 로그인.
2.  **학습 시작**: 상단 '학습하기' 메뉴 -> '학습 시작' 버튼 클릭 (마이크 권한 허용 필요).
3.  **실시간 자막**: 가상의 AI가 생성하는 실시간 자막이 올라오는지 확인.
4.  **퀴즈 풀이**: '수업 완료' 버튼 클릭 -> 일일 퀴즈 생성 및 풀이.
