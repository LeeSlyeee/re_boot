# 🚀 Re:Boot 프로젝트 실행 매뉴얼

이 문서는 `start_all.bat` 스크립트를 사용하지 않고, 터미널에서 직접 각 서버를 실행하는 방법을 안내합니다.

## ✅ 사전 준비

- **Python 3.10+** (Backend)
- **Node.js 18+** (Frontend)
- **PostgreSQL 16+** (Database)

---

## 1️⃣ Backend (Django) 실행

백엔드는 `8000` 포트에서 실행됩니다. 가장 먼저 실행해주세요.

1. **새 터미널**을 엽니다.
2. `backend` 폴더로 이동합니다.
3. 가상환경을 활성화하고 서버를 실행합니다.

```cmd
cd backend
venv\Scripts\activate
python manage.py runserver
```

> **성공 확인**: 터미널에 `Starting development server at http://127.0.0.1:8000/` 메시지가 뜨면 성공입니다.
> - Admin 페이지: [http://localhost:8000/admin](http://localhost:8000/admin)

---

## 2️⃣ Frontend (수강생용) 실행

프론트엔드는 `5173` 포트에서 실행됩니다.

1. **새 터미널**을 엽니다. (백엔드 터미널은 켜둔 상태여야 합니다)
2. `frontend` 폴더로 이동합니다.
3. 개발 서버를 실행합니다.

```cmd
cd frontend
npm run dev
```

> **접속 주소**: [http://localhost:5173](http://localhost:5173)

---

## 3️⃣ Professor Dashboard (강사용) 실행

대시보드는 `5174` 포트에서 실행됩니다.

1. **새 터미널**을 엽니다.
2. `Professor_dashboard` 폴더로 이동합니다.
3. 개발 서버를 실행합니다.

```cmd
cd Professor_dashboard
npm run dev
```

> **접속 주소**: [http://localhost:5174](http://localhost:5174)

---

## 🔑 테스트 계정 정보

- **관리자 계정 (Superuser)**
  - ID: `admin`
  - PW: `password`

- **테스트 일반 유저 (학생용)**
  - ID: `testuser`
  - PW: `password123`

- **테스트 강사 유저 (대시보드)**
  - ID: `professor`
  - PW: `password123`

---

## 💡 개발 팁 (VS Code)

VS Code 하단 터미널 패널에서 `+` 버튼을 누르거나 `Ctrl + Shift + 5`를 눌러 터미널을 여러 개 띄울 수 있습니다.
각 터미널에 **Backend**, **Frontend**, **Dashboard**를 각각 실행해두고 로그를 확인하며 개발하는 것을 권장합니다.
