---
description: 공식 문서 RAG 자동 최신화 스케줄러 설정 및 실행 방법
---

# 공식 문서 RAG 자동 최신화 워크플로우

## 시스템 구성

```
LectureMaterial (원본 문서 1,588건, 24.4MB)
       ↓ 청크 분할 (1,000자, 오버랩 200자)
VectorStore (35,300+ 벡터, text-embedding-3-small 1536 dim)
       ↓ RAG 검색
AI 튜터 (RAGService.search() → RAGService.generate_answer())
```

## 사용 가능한 명령어

### 1. 현재 상태 확인

// turbo

```bash
cd /Users/slyeee/Desktop/last_project/re_boot/backend
source ../venv/bin/activate
python manage.py update_tech_docs --stats
```

### 2. 변경분만 확인 (Dry Run)

```bash
python manage.py update_tech_docs --dry-run
```

### 3. 전체 문서 최신화 실행

```bash
python manage.py update_tech_docs
```

### 4. 특정 기술만 업데이트

```bash
python manage.py update_tech_docs --tech React
python manage.py update_tech_docs --tech Django
python manage.py update_tech_docs --tech NestJS
```

### 5. 강제 재크롤링 (변경 여부 무관)

```bash
python manage.py update_tech_docs --force
```

### 6. 오래된 문서만 업데이트 (기본 7일)

```bash
python manage.py update_tech_docs --max-age-days 14
```

## Cron 스케줄 설정

### macOS (launchd 대신 crontab 사용)

```bash
crontab -e
```

아래 줄 추가 (매주 일요일 새벽 3시 실행):

```cron
0 3 * * 0 cd /Users/slyeee/Desktop/last_project/re_boot/backend && /Users/slyeee/Desktop/last_project/re_boot/venv/bin/python manage.py update_tech_docs >> /Users/slyeee/Desktop/last_project/re_boot/backend/logs/docs_update.log 2>&1
```

### Linux 서버 (운영 환경)

```cron
# 매주 일요일 새벽 3시
0 3 * * 0 cd /home/deploy/re_boot/backend && /home/deploy/re_boot/venv/bin/python manage.py update_tech_docs >> /var/log/reboot_docs_update.log 2>&1

# 매일 새벽 4시 (더 빈번한 업데이트 원할 때)
0 4 * * * cd /home/deploy/re_boot/backend && /home/deploy/re_boot/venv/bin/python manage.py update_tech_docs --max-age-days 1 >> /var/log/reboot_docs_update.log 2>&1
```

## 관련 파일 위치

| 파일                                               | 용도                          |
| :------------------------------------------------- | :---------------------------- |
| `learning/management/commands/update_tech_docs.py` | 메인 관리 명령어              |
| `deep_crawl_docs.py`                               | 초기 대규모 크롤링 (Phase 1)  |
| `deep_crawl_v2.py`                                 | 보강 크롤링                   |
| `crawl_nestjs.py`                                  | NestJS GitHub 소스 크롤링     |
| `vectorize_materials.py`                           | 벡터화 파이프라인 (Phase 2)   |
| `seed_tech_materials.py`                           | 초기 시드 데이터              |
| `learning/rag.py`                                  | RAGService (검색 + 답변 생성) |
| `logs/docs_update.log`                             | 업데이트 이력 로그            |

## 지원 기술 스택 (20개+)

| 카테고리   | 기술                                                                                                 |
| :--------- | :--------------------------------------------------------------------------------------------------- |
| 프론트엔드 | React.js, Vue.js, Svelte, Next.js, Nuxt.js, TypeScript, Tailwind CSS, Redux, Zustand, TanStack Query |
| 백엔드     | Django, FastAPI, Flask, Express.js, NestJS, Node.js, Go, GraphQL, gRPC, Spring Boot                  |
| DB/캐시    | PostgreSQL, MongoDB, MySQL, Redis                                                                    |
| DevOps     | Docker, Kubernetes, Nginx, AWS, GitHub Actions                                                       |
| 보안       | JWT, OAuth 2.0, MDN Web Security                                                                     |
