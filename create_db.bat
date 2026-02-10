@echo off
set PGPASSWORD=postgres
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -h 127.0.0.1 -U postgres -c "CREATE USER slyeee WITH PASSWORD 'password';"
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -h 127.0.0.1 -U postgres -c "CREATE DATABASE reboot_db OWNER slyeee;"
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -h 127.0.0.1 -U postgres -c "ALTER USER slyeee CREATEDB;"
