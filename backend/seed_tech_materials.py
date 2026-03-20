"""
웹 개발 핵심 기술 스택 공식 문서를 크롤링하여 LectureMaterial 테이블에 시드(Seed)하는 스크립트.
- 각 URL의 전체 페이지 내용을 크롤링 → 마크다운(MARKDOWN)으로 변환하여 content_data에 저장
- lecture_id = NULL (강의 비종속 공통 기초 자료)
- 크롤링 실패 시 LINK 타입으로 대체 저장 (Fallback)
"""
import os
import sys
import time
import django

# Django 설정 로드
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

import requests
import html2text
from bs4 import BeautifulSoup
from learning.models import LectureMaterial
from users.models import User

# ─────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}
REQUEST_TIMEOUT = 15  # seconds
DELAY_BETWEEN_REQUESTS = 1  # 서버 부하 방지용 딜레이 (초)

# html2text 변환기 설정
converter = html2text.HTML2Text()
converter.ignore_links = False    # 링크 유지
converter.ignore_images = True    # 이미지 무시 (텍스트 학습용)
converter.body_width = 0          # 줄바꿈 없이 전체 텍스트 유지
converter.ignore_emphasis = False # 강조(Bold/Italic) 유지


def fetch_page_as_markdown(url: str) -> tuple[str, bool]:
    """
    URL의 전체 페이지를 가져와 마크다운으로 변환.
    Returns: (markdown_text, success_flag)
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        # BeautifulSoup으로 본문(body)만 추출, 불필요한 태그 제거
        soup = BeautifulSoup(resp.text, 'html.parser')

        # nav, footer, header, script, style, aside 등 탐색용/장식용 태그 제거
        for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style', 'aside', 'noscript', 'iframe']):
            tag.decompose()

        # main 또는 article 태그가 있으면 그것만 사용 (본문 집중)
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content is None:
            main_content = soup

        html_str = str(main_content)
        markdown = converter.handle(html_str)

        # 과도한 빈 줄 정리
        lines = markdown.split('\n')
        cleaned_lines = []
        empty_count = 0
        for line in lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    cleaned_lines.append('')
            else:
                empty_count = 0
                cleaned_lines.append(line)
        markdown = '\n'.join(cleaned_lines).strip()

        if len(markdown) < 100:
            return f"[크롤링 내용 부족 - 원본 URL 참조]\n{url}", False

        # 출처 URL을 상단에 명시
        markdown = f"# 출처: {url}\n\n---\n\n{markdown}"

        return markdown, True

    except requests.exceptions.RequestException as e:
        return f"[크롤링 실패: {str(e)}]\n원본 URL: {url}", False


# ─────────────────────────────────────────────────
# 등록자 확인
# ─────────────────────────────────────────────────
uploader = User.objects.filter(role='INSTRUCTOR').first() or User.objects.filter(username='admin').first()
if not uploader:
    print("ERROR: 등록자(INSTRUCTOR 또는 admin) 계정이 DB에 없습니다.")
    sys.exit(1)
print(f"[INFO] 등록자: {uploader.username} (id={uploader.id})")

# ─────────────────────────────────────────────────
# 공식 문서 URL 목록 (카테고리별)
# ─────────────────────────────────────────────────
MATERIALS = [
    # ── 1. 프론트엔드 ──
    ("[프론트엔드] HTML/CSS/JS - MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web"),
    ("[프론트엔드] TypeScript 공식 문서", "https://www.typescriptlang.org/docs/"),
    ("[프론트엔드] React.js 공식 문서", "https://react.dev/"),
    ("[프론트엔드] Vue.js 공식 가이드", "https://vuejs.org/guide/introduction.html"),
    ("[프론트엔드] Svelte 공식 문서", "https://svelte.dev/docs"),
    ("[프론트엔드] Next.js 공식 문서", "https://nextjs.org/docs"),
    ("[프론트엔드] Nuxt.js 공식 문서", "https://nuxt.com/docs"),
    ("[프론트엔드] Redux 공식 문서", "https://redux.js.org/"),
    ("[프론트엔드] Zustand 상태관리 라이브러리", "https://github.com/pmndrs/zustand"),
    ("[프론트엔드] TanStack Query (React Query)", "https://tanstack.com/query/latest/docs/react/overview"),
    ("[프론트엔드] Tailwind CSS 공식 문서", "https://tailwindcss.com/docs"),

    # ── 2. 백엔드 ──
    ("[백엔드] Node.js 공식 문서", "https://nodejs.org/en/docs/"),
    ("[백엔드] Express.js 공식 문서", "https://expressjs.com/"),
    ("[백엔드] NestJS 공식 문서", "https://docs.nestjs.com/"),
    ("[백엔드] Django 공식 문서", "https://docs.djangoproject.com/"),
    ("[백엔드] FastAPI 공식 문서", "https://fastapi.tiangolo.com/"),
    ("[백엔드] Spring Boot 공식 문서", "https://spring.io/projects/spring-boot"),
    ("[백엔드] Go (Golang) 공식 문서", "https://go.dev/doc/"),
    ("[백엔드] GraphQL 공식 학습 가이드", "https://graphql.org/learn/"),
    ("[백엔드] gRPC 공식 문서", "https://grpc.io/docs/"),

    # ── 3. 데이터베이스 & 캐싱 ──
    ("[DB] PostgreSQL 공식 문서", "https://www.postgresql.org/docs/"),
    ("[DB] MySQL 공식 문서", "https://dev.mysql.com/doc/"),
    ("[DB] MongoDB 공식 문서", "https://www.mongodb.com/docs/"),
    ("[캐시] Redis 공식 문서", "https://redis.io/docs/"),

    # ── 4. 인프라 & DevOps ──
    ("[클라우드] AWS 공식 문서", "https://docs.aws.amazon.com/"),
    ("[CI/CD] GitHub Actions 공식 문서", "https://docs.github.com/en/actions"),
    ("[컨테이너] Docker 공식 문서", "https://docs.docker.com/"),
    ("[오케스트레이션] Kubernetes (K8s) 공식 문서", "https://kubernetes.io/docs/home/"),
    ("[웹서버] Nginx 공식 문서", "https://nginx.org/en/docs/"),

    # ── 5. 보안 & 인증 ──
    ("[보안] JWT (JSON Web Token) 소개", "https://jwt.io/introduction"),
    ("[보안] OAuth 2.0 표준 프로토콜", "https://oauth.net/2/"),
    ("[보안] MDN 웹 보안 가이드", "https://developer.mozilla.org/en-US/docs/Web/Security"),
]

# ─────────────────────────────────────────────────
# 크롤링 + DB 삽입
# ─────────────────────────────────────────────────
created_count = 0
skipped_count = 0
failed_count = 0

print(f"\n{'='*60}")
print(f" 총 {len(MATERIALS)}개 공식 문서 크롤링 및 DB 삽입 시작")
print(f"{'='*60}\n")

for idx, (title, url) in enumerate(MATERIALS, 1):
    # 중복 체크
    if LectureMaterial.objects.filter(title=title).exists():
        skipped_count += 1
        print(f"  [{idx:02d}/{len(MATERIALS)}] ⏭️  이미 존재: {title}")
        continue

    print(f"  [{idx:02d}/{len(MATERIALS)}] 🌐 크롤링 중: {url} ...", end=" ", flush=True)
    content, success = fetch_page_as_markdown(url)

    content_type = "MARKDOWN" if success else "LINK"
    content_data = content if success else url
    status_icon = "✅" if success else "⚠️"

    LectureMaterial.objects.create(
        lecture=None,
        title=title,
        content_type=content_type,
        content_data=content_data,
        file_type="MD" if success else "OTHER",
        uploaded_by=uploader,
    )
    created_count += 1
    if not success:
        failed_count += 1
    size_kb = len(content_data.encode('utf-8')) / 1024
    print(f"{status_icon} 저장 완료 ({content_type}, {size_kb:.1f}KB)")

    time.sleep(DELAY_BETWEEN_REQUESTS)

# ── 추가: 기술 스택 종합 마크다운 원본 파일 ──
md_title = "[종합] 주요 웹 개발 IT 기술 스택 공식 문서 링크 모음"
if not LectureMaterial.objects.filter(title=md_title).exists():
    md_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web_development_tech_stack_docs.md')
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        LectureMaterial.objects.create(
            lecture=None,
            title=md_title,
            content_type="MARKDOWN",
            content_data=md_content,
            file_type="MD",
            uploaded_by=uploader,
        )
        created_count += 1
        print(f"  [종합] ✅ 마크다운 원본 저장 완료 ({len(md_content)/1024:.1f}KB)")

print(f"\n{'='*60}")
print(f" [결과] 신규 생성: {created_count}건")
print(f" [결과] 이미 존재(건너뜀): {skipped_count}건")
print(f" [결과] 크롤링 실패(LINK 대체): {failed_count}건")
print(f" [결과] 총 LectureMaterial 레코드 수: {LectureMaterial.objects.count()}건")
print(f"{'='*60}")
