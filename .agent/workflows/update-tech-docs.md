---
description: 공식 문서 RAG 자동 최신화 스케줄러 설정 및 실행 방법
---

# 공식 문서 RAG 최신화 워크플로우

## 현재 상태

- **서버**: OCI `144.24.81.132` (ubuntu)
- **SSH 키**: `/Users/slyeee/Desktop/last_project/re_boot/sshKey/ssh-key-2026-03-05.key`
- **프로젝트 경로**: `/home/ubuntu/re_boot/backend/`
- **Cron**: 매주 일요일 새벽 3시 자동 실행

## 수동 실행 방법

### 1. 상태 확인

// turbo

```bash
ssh -i /Users/slyeee/Desktop/last_project/re_boot/sshKey/ssh-key-2026-03-05.key -o StrictHostKeyChecking=no ubuntu@144.24.81.132 "cd /home/ubuntu/re_boot/backend && source ../venv/bin/activate && python manage.py update_tech_docs --stats"
```

### 2. 전체 업데이트 실행

```bash
ssh -i /Users/slyeee/Desktop/last_project/re_boot/sshKey/ssh-key-2026-03-05.key -o StrictHostKeyChecking=no ubuntu@144.24.81.132 "cd /home/ubuntu/re_boot/backend && source ../venv/bin/activate && nohup python manage.py update_tech_docs >> /home/ubuntu/re_boot/logs/docs_update.log 2>&1 &"
```

### 3. 특정 기술만 업데이트

```bash
ssh -i /Users/slyeee/Desktop/last_project/re_boot/sshKey/ssh-key-2026-03-05.key -o StrictHostKeyChecking=no ubuntu@144.24.81.132 "cd /home/ubuntu/re_boot/backend && source ../venv/bin/activate && python manage.py update_tech_docs --tech React"
```

### 4. 새 기술 추가 크롤링 (로컬)

```bash
cd /Users/slyeee/Desktop/last_project/re_boot/backend
source ../venv/bin/activate
# deep_crawl_v3.py의 SITES 목록에 새 기술 추가 후
PYTHONUNBUFFERED=1 python deep_crawl_v3.py
# 벡터화
PYTHONUNBUFFERED=1 python vectorize_materials.py
```

### 5. 로그 확인

// turbo

```bash
ssh -i /Users/slyeee/Desktop/last_project/re_boot/sshKey/ssh-key-2026-03-05.key -o StrictHostKeyChecking=no ubuntu@144.24.81.132 "tail -50 /home/ubuntu/re_boot/logs/docs_update.log"
```

## cron 설정 확인/변경

// turbo

```bash
ssh -i /Users/slyeee/Desktop/last_project/re_boot/sshKey/ssh-key-2026-03-05.key -o StrictHostKeyChecking=no ubuntu@144.24.81.132 "crontab -l"
```
