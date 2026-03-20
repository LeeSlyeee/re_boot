"""
Re:Boot Deep Documentation Crawler
===================================
모든 공식 문서 사이트의 전체 하위 페이지를 자동 발견 → 크롤링 → 마크다운 변환 → DB 저장

실행: python deep_crawl_docs.py
백그라운드: nohup python deep_crawl_docs.py > crawl.log 2>&1 &
"""
import os, sys, time, re, django
from urllib.parse import urljoin, urlparse
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

import requests
import html2text
from bs4 import BeautifulSoup
from learning.models import LectureMaterial
from users.models import User

# ═══════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}
REQUEST_TIMEOUT = 20
DELAY = 0.8  # 요청 간 딜레이 (초) — 서버 부하 방지
MAX_PAGES_PER_SITE = 80  # 사이트당 최대 크롤링 페이지 수 (안전장치)
MIN_CONTENT_LENGTH = 200  # 최소 콘텐츠 길이 (바이트)

# html2text 설정
h2t = html2text.HTML2Text()
h2t.ignore_links = False
h2t.ignore_images = True
h2t.body_width = 0
h2t.ignore_emphasis = False
h2t.skip_internal_links = False

# ═══════════════════════════════════════════════
# 크롤링 대상 기술 사이트 정의
# 각 사이트별로 최적의 페이지 발견 전략을 지정
# ═══════════════════════════════════════════════
SITES = [
    {
        "category": "프론트엔드",
        "name": "React.js",
        "seed_urls": [
            "https://react.dev/learn",
            "https://react.dev/reference/react",
        ],
        "allowed_prefix": "https://react.dev/",
        "url_must_contain": ["/learn", "/reference"],
        "sitemap": None,
    },
    {
        "category": "프론트엔드",
        "name": "Vue.js",
        "seed_urls": [
            "https://vuejs.org/guide/introduction.html",
            "https://vuejs.org/api/",
        ],
        "allowed_prefix": "https://vuejs.org/",
        "url_must_contain": ["/guide/", "/api/", "/tutorial/"],
        "sitemap": None,
    },
    {
        "category": "프론트엔드",
        "name": "Svelte",
        "seed_urls": [
            "https://svelte.dev/docs/svelte/overview",
        ],
        "allowed_prefix": "https://svelte.dev/docs/",
        "url_must_contain": ["/docs/"],
        "sitemap": None,
    },
    {
        "category": "프론트엔드",
        "name": "Next.js",
        "seed_urls": [
            "https://nextjs.org/docs",
            "https://nextjs.org/docs/getting-started",
        ],
        "allowed_prefix": "https://nextjs.org/docs",
        "url_must_contain": ["/docs"],
        "sitemap": None,
    },
    {
        "category": "프론트엔드",
        "name": "TypeScript",
        "seed_urls": [
            "https://www.typescriptlang.org/docs/handbook/intro.html",
            "https://www.typescriptlang.org/docs/handbook/2/basic-types.html",
            "https://www.typescriptlang.org/docs/handbook/2/everyday-types.html",
            "https://www.typescriptlang.org/docs/handbook/2/narrowing.html",
            "https://www.typescriptlang.org/docs/handbook/2/functions.html",
            "https://www.typescriptlang.org/docs/handbook/2/objects.html",
            "https://www.typescriptlang.org/docs/handbook/2/generics.html",
            "https://www.typescriptlang.org/docs/handbook/2/classes.html",
            "https://www.typescriptlang.org/docs/handbook/2/modules.html",
            "https://www.typescriptlang.org/docs/handbook/2/types-from-types.html",
        ],
        "allowed_prefix": "https://www.typescriptlang.org/docs/",
        "url_must_contain": ["/docs/handbook/"],
        "sitemap": None,
    },
    {
        "category": "프론트엔드",
        "name": "Tailwind CSS",
        "seed_urls": [
            "https://tailwindcss.com/docs/installation",
        ],
        "allowed_prefix": "https://tailwindcss.com/docs/",
        "url_must_contain": ["/docs/"],
        "sitemap": None,
    },
    {
        "category": "백엔드",
        "name": "Django",
        "seed_urls": [
            "https://docs.djangoproject.com/en/5.1/intro/tutorial01/",
            "https://docs.djangoproject.com/en/5.1/topics/",
            "https://docs.djangoproject.com/en/5.1/ref/models/fields/",
        ],
        "allowed_prefix": "https://docs.djangoproject.com/en/5.1/",
        "url_must_contain": ["/en/5.1/"],
        "sitemap": None,
    },
    {
        "category": "백엔드",
        "name": "FastAPI",
        "seed_urls": [
            "https://fastapi.tiangolo.com/tutorial/",
            "https://fastapi.tiangolo.com/tutorial/first-steps/",
            "https://fastapi.tiangolo.com/tutorial/path-params/",
            "https://fastapi.tiangolo.com/tutorial/query-params/",
            "https://fastapi.tiangolo.com/tutorial/body/",
        ],
        "allowed_prefix": "https://fastapi.tiangolo.com/",
        "url_must_contain": ["/tutorial/", "/advanced/", "/reference/"],
        "sitemap": None,
    },
    {
        "category": "백엔드",
        "name": "Flask",
        "seed_urls": [
            "https://flask.palletsprojects.com/en/stable/quickstart/",
            "https://flask.palletsprojects.com/en/stable/tutorial/",
        ],
        "allowed_prefix": "https://flask.palletsprojects.com/en/stable/",
        "url_must_contain": ["/en/stable/"],
        "sitemap": None,
    },
    {
        "category": "백엔드",
        "name": "Express.js",
        "seed_urls": [
            "https://expressjs.com/en/starter/installing.html",
            "https://expressjs.com/en/guide/routing.html",
            "https://expressjs.com/en/guide/writing-middleware.html",
            "https://expressjs.com/en/guide/using-middleware.html",
            "https://expressjs.com/en/guide/error-handling.html",
            "https://expressjs.com/en/api.html",
        ],
        "allowed_prefix": "https://expressjs.com/en/",
        "url_must_contain": ["/en/"],
        "sitemap": None,
    },
    {
        "category": "백엔드",
        "name": "Node.js",
        "seed_urls": [
            "https://nodejs.org/en/learn/getting-started/introduction-to-nodejs",
        ],
        "allowed_prefix": "https://nodejs.org/en/learn/",
        "url_must_contain": ["/en/learn/"],
        "sitemap": None,
    },
    {
        "category": "백엔드",
        "name": "GraphQL",
        "seed_urls": [
            "https://graphql.org/learn/",
            "https://graphql.org/learn/queries/",
            "https://graphql.org/learn/schema/",
            "https://graphql.org/learn/validation/",
            "https://graphql.org/learn/execution/",
        ],
        "allowed_prefix": "https://graphql.org/learn/",
        "url_must_contain": ["/learn/"],
        "sitemap": None,
    },
    {
        "category": "DB",
        "name": "PostgreSQL",
        "seed_urls": [
            "https://www.postgresql.org/docs/current/tutorial.html",
            "https://www.postgresql.org/docs/current/sql.html",
        ],
        "allowed_prefix": "https://www.postgresql.org/docs/current/",
        "url_must_contain": ["/docs/current/"],
        "sitemap": None,
    },
    {
        "category": "DB",
        "name": "MongoDB",
        "seed_urls": [
            "https://www.mongodb.com/docs/manual/introduction/",
            "https://www.mongodb.com/docs/manual/crud/",
        ],
        "allowed_prefix": "https://www.mongodb.com/docs/manual/",
        "url_must_contain": ["/docs/manual/"],
        "sitemap": None,
    },
    {
        "category": "캐시",
        "name": "Redis",
        "seed_urls": [
            "https://redis.io/docs/latest/get-started/",
            "https://redis.io/docs/latest/develop/",
        ],
        "allowed_prefix": "https://redis.io/docs/",
        "url_must_contain": ["/docs/"],
        "sitemap": None,
    },
    {
        "category": "DevOps",
        "name": "Docker",
        "seed_urls": [
            "https://docs.docker.com/get-started/",
            "https://docs.docker.com/engine/",
            "https://docs.docker.com/compose/",
        ],
        "allowed_prefix": "https://docs.docker.com/",
        "url_must_contain": ["/docs.docker.com/"],
        "sitemap": None,
    },
    {
        "category": "DevOps",
        "name": "Kubernetes",
        "seed_urls": [
            "https://kubernetes.io/docs/concepts/",
            "https://kubernetes.io/docs/tutorials/",
        ],
        "allowed_prefix": "https://kubernetes.io/docs/",
        "url_must_contain": ["/docs/"],
        "sitemap": None,
    },
    {
        "category": "보안",
        "name": "JWT",
        "seed_urls": [
            "https://jwt.io/introduction",
        ],
        "allowed_prefix": "https://jwt.io/",
        "url_must_contain": [],
        "sitemap": None,
    },
]


# ═══════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════

def normalize_url(url):
    """URL 정규화 (fragment 제거, trailing slash 통일)"""
    parsed = urlparse(url)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if clean.endswith('/') and len(parsed.path) > 1:
        clean = clean  # trailing slash 유지
    return clean


def fetch_page(url):
    """HTML 페이지를 가져와 마크다운으로 변환"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.url
    except Exception as e:
        return None, url


def html_to_markdown(html_str):
    """HTML을 마크다운으로 변환 (불필요한 요소 제거)"""
    soup = BeautifulSoup(html_str, 'html.parser')
    
    # 불필요한 태그 제거
    for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style', 
                               'aside', 'noscript', 'iframe', 'svg']):
        tag.decompose()
    
    # 본문 추출
    main = soup.find('main') or soup.find('article') or soup.find('[role="main"]')
    if main is None:
        main = soup.find('div', class_=re.compile(r'content|docs|main|article', re.I))
    if main is None:
        main = soup.find('body') or soup
    
    markdown = h2t.handle(str(main)).strip()
    
    # 과도한 빈 줄 정리
    markdown = re.sub(r'\n{4,}', '\n\n\n', markdown)
    
    return markdown


def discover_links(html_str, base_url, allowed_prefix, url_filters):
    """페이지에서 크롤링 대상 링크를 추출"""
    soup = BeautifulSoup(html_str, 'html.parser')
    links = set()
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        
        # 상대 경로 → 절대 경로 변환
        full_url = urljoin(base_url, href)
        full_url = normalize_url(full_url)
        
        # 필터링
        if not full_url.startswith(allowed_prefix):
            continue
        
        # 확장자 필터 (이미지, 파일 등 제외)
        parsed_path = urlparse(full_url).path
        skip_exts = ['.png', '.jpg', '.gif', '.svg', '.pdf', '.zip', '.tar', '.ico', '.css', '.js', '.xml', '.json']
        if any(parsed_path.endswith(ext) for ext in skip_exts):
            continue
        
        # URL 패턴 필터 (url_must_contain이 비어있으면 모든 URL 허용)
        if url_filters:
            if not any(f in full_url for f in url_filters):
                continue
        
        links.add(full_url)
    
    return links


def crawl_site(site_config):
    """
    BFS(너비 우선 탐색)로 사이트의 모든 하위 페이지를 크롤링
    """
    name = site_config['name']
    category = site_config['category']
    allowed_prefix = site_config['allowed_prefix']
    url_filters = site_config.get('url_must_contain', [])
    max_pages = MAX_PAGES_PER_SITE
    
    # 시드 URL로 큐 초기화
    queue = deque(site_config['seed_urls'])
    visited = set()
    results = []
    
    print(f"\n  {'─'*50}")
    print(f"  📚 [{category}] {name} — 크롤링 시작 (시드: {len(queue)}개)")
    print(f"  {'─'*50}")
    
    while queue and len(results) < max_pages:
        url = normalize_url(queue.popleft())
        
        if url in visited:
            continue
        visited.add(url)
        
        # 이미 DB에 존재하는지 확인 (URL 기반 중복 방지)
        if LectureMaterial.objects.filter(content_data__contains=url, content_type='MARKDOWN').exists():
            # URL이 이미 content_data에 출처로 포함된 레코드가 있으면 건너뜀
            existing = LectureMaterial.objects.filter(content_data__contains=url, content_type='MARKDOWN').first()
            if existing and len(existing.content_data) > MIN_CONTENT_LENGTH:
                print(f"    ⏭️  이미 저장됨: ...{url[-60:]}")
                continue
        
        # 페이지 가져오기
        html_str, final_url = fetch_page(url)
        if not html_str:
            print(f"    ❌ 실패: ...{url[-60:]}")
            continue
        
        # 마크다운 변환
        markdown = html_to_markdown(html_str)
        
        if len(markdown) < MIN_CONTENT_LENGTH:
            print(f"    ⚠️  내용 부족 ({len(markdown)}B): ...{url[-60:]}")
            continue
        
        # 페이지 제목 추출
        soup = BeautifulSoup(html_str, 'html.parser')
        page_title = soup.find('title')
        page_title = page_title.get_text().strip() if page_title else url.split('/')[-1]
        # 제목에서 사이트명 부분 정리
        page_title = re.sub(r'\s*[\|–—·•]\s*.+$', '', page_title).strip()
        if not page_title:
            page_title = url.split('/')[-1].replace('-', ' ').replace('_', ' ').title()
        
        # 최종 콘텐츠 구성
        full_content = f"# 출처: {url}\n# 기술: {name} ({category})\n\n---\n\n{markdown}"
        
        results.append({
            'title': f"[{category}] {name} — {page_title}",
            'url': url,
            'content': full_content,
        })
        print(f"    ✅ [{len(results):02d}] {page_title[:50]}... ({len(full_content)/1024:.1f}KB)")
        
        # 이 페이지의 링크에서 새 URL 발견
        new_links = discover_links(html_str, final_url, allowed_prefix, url_filters)
        for link in new_links:
            if link not in visited:
                queue.append(link)
        
        time.sleep(DELAY)
    
    print(f"  📊 [{name}] 완료: {len(results)}페이지 크롤링 / {len(visited)}페이지 방문")
    return results


# ═══════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════
if __name__ == '__main__':
    uploader = User.objects.filter(role='INSTRUCTOR').first() or User.objects.filter(username='admin').first()
    if not uploader:
        print("ERROR: 등록자 계정이 없습니다.")
        sys.exit(1)
    
    print("=" * 60)
    print(f" Re:Boot Deep Documentation Crawler")
    print(f" 대상: {len(SITES)}개 기술 사이트")
    print(f" 사이트당 최대: {MAX_PAGES_PER_SITE}페이지")
    print(f" 등록자: {uploader.username}")
    print("=" * 60)
    
    total_created = 0
    total_skipped = 0
    total_failed = 0
    site_stats = []
    
    for site in SITES:
        pages = crawl_site(site)
        
        created = 0
        for page in pages:
            # 동일 title 중복 방지
            title = page['title'][:200]  # max_length=200 제한
            if LectureMaterial.objects.filter(title=title).exists():
                total_skipped += 1
                continue
            
            try:
                LectureMaterial.objects.create(
                    lecture=None,
                    title=title,
                    content_type='MARKDOWN',
                    content_data=page['content'],
                    file_type='MD',
                    uploaded_by=uploader,
                )
                created += 1
            except Exception as e:
                print(f"    ❌ DB 저장 실패: {e}")
                total_failed += 1
        
        total_created += created
        site_stats.append((site['name'], created, len(pages)))
    
    # ─── 최종 보고 ───
    print("\n" + "=" * 60)
    print(" 📊 Deep Crawler 최종 보고")
    print("=" * 60)
    for name, created, crawled in site_stats:
        print(f"  {name:20s}: {created:3d}건 저장 / {crawled:3d}페이지 크롤링")
    print("-" * 60)
    print(f"  신규 생성: {total_created}건")
    print(f"  건너뜀  : {total_skipped}건")
    print(f"  실패    : {total_failed}건")
    print(f"  총 LectureMaterial: {LectureMaterial.objects.count()}건")
    md_count = LectureMaterial.objects.filter(content_type='MARKDOWN').count()
    total_size = sum(len(m.content_data.encode('utf-8')) for m in LectureMaterial.objects.filter(content_type='MARKDOWN'))
    print(f"  MARKDOWN 콘텐츠 총 용량: {total_size/1024/1024:.1f}MB")
    print("=" * 60)
