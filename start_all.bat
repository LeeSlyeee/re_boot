@echo off
start "Backend" cmd /k "cd backend && venv\Scripts\python manage.py runserver"
start "Frontend" cmd /k "cd frontend && npm run dev"
start "Dashboard" cmd /k "cd Professor_dashboard && npm run dev"
echo All services started!
