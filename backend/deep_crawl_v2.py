"""
Re:Boot Deep Crawler v2 — 보강 크롤링
======================================
수정사항:
1. 중복 체크: title 기반 → URL 기반 (content_data 첫 줄에서 출처 URL 추출)
2. 제목 생성: URL 경로를 포함하여 고유 제목 보장 (Node.js 등 동일 title 문제 해결)
3. 대상: 이전 크롤링에서 0건이었거나 부족했던 기술들

실행: PYTHONUNBUFFERED=1 python deep_crawl_v2.py
"""
import os, sys, time, re, hashlib, django
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
DELAY = 0.8
MAX_PAGES_PER_SITE = 80
MIN_CONTENT_LENGTH = 200

h2t = html2text.HTML2Text()
h2t.ignore_links = False
h2t.ignore_images = True
h2t.body_width = 0
h2t.ignore_emphasis = False

# ═══════════════════════════════════════════════
# 이미 크롤링된 URL 목록을 DB에서 로드 (정확한 중복 방지)
# ═══════════════════════════════════════════════
def load_crawled_urls():
    """DB의 모든 LectureMaterial에서 '# 출처: URL' 패턴의 URL을 추출"""
    urls = set()
    for mat in LectureMaterial.objects.filter(content_type='MARKDOWN').only('content_data'):
        # content_data 첫 줄에서 '# 출처: https://...' 패턴 추출
        first_line = mat.content_data.split('\n')[0] if mat.content_data else ''
        match = re.match(r'^# 출처:\s*(https?://\S+)', first_line)
        if match:
            urls.add(normalize_url(match.group(1)))
    return urls


def normalize_url(url):
    parsed = urlparse(url)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean


def url_to_slug(url, category, name):
    """URL 경로에서 고유한 제목 생성"""
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    # 경로의 마지막 2~3 세그먼트를 제목에 활용
    parts = [p for p in path.split('/') if p]
    if len(parts) > 3:
        slug = '/'.join(parts[-3:])
    elif parts:
        slug = '/'.join(parts)
    else:
        slug = 'index'
    # 확장자 제거
    slug = re.sub(r'\.(html|htm|md|mdx)$', '', slug)
    # 제목 구성
    title = f"[{category}] {name} — {slug}"
    return title[:200]  # max_length=200


def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.url
    except:
        return None, url


def html_to_markdown(html_str):
    soup = BeautifulSoup(html_str, 'html.parser')
    for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style',
                               'aside', 'noscript', 'iframe', 'svg']):
        tag.decompose()
    main = soup.find('main') or soup.find('article') or soup.find('[role="main"]')
    if main is None:
        main = soup.find('div', class_=re.compile(r'content|docs|main|article', re.I))
    if main is None:
        main = soup.find('body') or soup
    markdown = h2t.handle(str(main)).strip()
    markdown = re.sub(r'\n{4,}', '\n\n\n', markdown)
    return markdown


def discover_links(html_str, base_url, allowed_prefix, url_filters):
    soup = BeautifulSoup(html_str, 'html.parser')
    links = set()
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        full_url = urljoin(base_url, href)
        full_url = normalize_url(full_url)
        if not full_url.startswith(allowed_prefix):
            continue
        parsed_path = urlparse(full_url).path
        skip_exts = ['.png', '.jpg', '.gif', '.svg', '.pdf', '.zip', '.tar', '.ico', '.css', '.js', '.xml', '.json']
        if any(parsed_path.endswith(ext) for ext in skip_exts):
            continue
        if url_filters:
            if not any(f in full_url for f in url_filters):
                continue
        links.add(full_url)
    return links


def crawl_site(site_config, crawled_urls):
    name = site_config['name']
    category = site_config['category']
    allowed_prefix = site_config['allowed_prefix']
    url_filters = site_config.get('url_must_contain', [])

    queue = deque(site_config['seed_urls'])
    visited = set()
    results = []

    print(f"\n  {'─'*50}")
    print(f"  📚 [{category}] {name} — 크롤링 시작 (시드: {len(queue)}개)")
    print(f"  {'─'*50}")

    while queue and len(results) < MAX_PAGES_PER_SITE:
        url = normalize_url(queue.popleft())

        if url in visited:
            continue
        visited.add(url)

        # URL 기반 중복 체크 (이미 DB에 저장된 URL이면 건너뜀)
        if url in crawled_urls:
            # 단, 링크만 발견하기 위해 페이지는 가져옴
            html_str, final_url = fetch_page(url)
            if html_str:
                new_links = discover_links(html_str, final_url, allowed_prefix, url_filters)
                for link in new_links:
                    if link not in visited:
                        queue.append(link)
            print(f"    ⏭️  이미 저장됨 (링크만 수집): ...{url[-55:]}")
            time.sleep(DELAY * 0.5)
            continue

        html_str, final_url = fetch_page(url)
        if not html_str:
            print(f"    ❌ 실패: ...{url[-55:]}")
            continue

        markdown = html_to_markdown(html_str)

        if len(markdown) < MIN_CONTENT_LENGTH:
            # 링크만 수집
            new_links = discover_links(html_str, final_url, allowed_prefix, url_filters)
            for link in new_links:
                if link not in visited:
                    queue.append(link)
            print(f"    ⚠️  내용 부족 ({len(markdown)}B), 링크만 수집: ...{url[-55:]}")
            continue

        # URL 기반 고유 제목 생성
        title = url_to_slug(url, category, name)
        
        # 혹시 title이 이미 있으면 URL 해시 추가
        if LectureMaterial.objects.filter(title=title).exists():
            url_hash = hashlib.md5(url.encode()).hexdigest()[:6]
            title = f"{title[:193]}_{url_hash}"

        full_content = f"# 출처: {url}\n# 기술: {name} ({category})\n\n---\n\n{markdown}"

        results.append({
            'title': title,
            'url': url,
            'content': full_content,
        })
        crawled_urls.add(url)  # 즉시 기록
        print(f"    ✅ [{len(results):02d}] {title[len(category)+3+len(name)+5:][:50]}... ({len(full_content)/1024:.1f}KB)")

        new_links = discover_links(html_str, final_url, allowed_prefix, url_filters)
        for link in new_links:
            if link not in visited:
                queue.append(link)

        time.sleep(DELAY)

    print(f"  📊 [{name}] 완료: {len(results)}페이지 크롤링 / {len(visited)}페이지 방문")
    return results


# ═══════════════════════════════════════════════
# 보강 대상 사이트 (이전 크롤링에서 0건/부족했던 기술들)
# ═══════════════════════════════════════════════
SITES = [
    # ── 이전 0건 ──
    {
        "category": "프론트엔드",
        "name": "React.js",
        "seed_urls": [
            "https://react.dev/learn",
            "https://react.dev/learn/tutorial-tic-tac-toe",
            "https://react.dev/learn/thinking-in-react",
            "https://react.dev/learn/describing-the-ui",
            "https://react.dev/learn/adding-interactivity",
            "https://react.dev/learn/managing-state",
            "https://react.dev/learn/escape-hatches",
            "https://react.dev/reference/react",
            "https://react.dev/reference/react/hooks",
        ],
        "allowed_prefix": "https://react.dev/",
        "url_must_contain": ["/learn", "/reference"],
    },
    {
        "category": "프론트엔드",
        "name": "Vue.js",
        "seed_urls": [
            "https://vuejs.org/guide/essentials/application.html",
            "https://vuejs.org/guide/essentials/template-syntax.html",
            "https://vuejs.org/guide/essentials/reactivity-fundamentals.html",
            "https://vuejs.org/guide/essentials/computed.html",
            "https://vuejs.org/guide/essentials/class-and-style.html",
            "https://vuejs.org/guide/essentials/conditional.html",
            "https://vuejs.org/guide/essentials/list.html",
            "https://vuejs.org/guide/essentials/event-handling.html",
            "https://vuejs.org/guide/essentials/forms.html",
            "https://vuejs.org/guide/essentials/lifecycle.html",
            "https://vuejs.org/guide/essentials/watchers.html",
            "https://vuejs.org/guide/essentials/component-basics.html",
            "https://vuejs.org/guide/components/registration.html",
            "https://vuejs.org/guide/components/props.html",
            "https://vuejs.org/guide/components/events.html",
            "https://vuejs.org/guide/components/slots.html",
            "https://vuejs.org/guide/reusability/composables.html",
            "https://vuejs.org/guide/scaling-up/routing.html",
            "https://vuejs.org/guide/scaling-up/state-management.html",
            "https://vuejs.org/api/application.html",
            "https://vuejs.org/api/composition-api-setup.html",
            "https://vuejs.org/api/reactivity-core.html",
        ],
        "allowed_prefix": "https://vuejs.org/",
        "url_must_contain": ["/guide/", "/api/"],
    },
    {
        "category": "프론트엔드",
        "name": "Svelte",
        "seed_urls": [
            "https://svelte.dev/docs/svelte/overview",
            "https://svelte.dev/docs/svelte/basic-markup",
            "https://svelte.dev/docs/svelte/$state",
            "https://svelte.dev/docs/svelte/$derived",
            "https://svelte.dev/docs/svelte/$effect",
            "https://svelte.dev/docs/svelte/$props",
            "https://svelte.dev/docs/svelte/$bindable",
            "https://svelte.dev/docs/svelte/if",
            "https://svelte.dev/docs/svelte/each",
            "https://svelte.dev/docs/svelte/await",
            "https://svelte.dev/docs/svelte/svelte",
            "https://svelte.dev/docs/svelte/stores",
            "https://svelte.dev/docs/svelte/svelte-action",
            "https://svelte.dev/docs/svelte/svelte-transition",
            "https://svelte.dev/docs/kit/introduction",
            "https://svelte.dev/docs/kit/routing",
            "https://svelte.dev/docs/kit/load",
            "https://svelte.dev/docs/kit/form-actions",
        ],
        "allowed_prefix": "https://svelte.dev/docs/",
        "url_must_contain": ["/docs/"],
    },
    {
        "category": "프론트엔드",
        "name": "Tailwind CSS",
        "seed_urls": [
            "https://tailwindcss.com/docs/installation",
            "https://tailwindcss.com/docs/utility-first",
            "https://tailwindcss.com/docs/responsive-design",
            "https://tailwindcss.com/docs/hover-focus-and-other-states",
            "https://tailwindcss.com/docs/dark-mode",
            "https://tailwindcss.com/docs/adding-custom-styles",
            "https://tailwindcss.com/docs/functions-and-directives",
            "https://tailwindcss.com/docs/padding",
            "https://tailwindcss.com/docs/margin",
            "https://tailwindcss.com/docs/flex",
            "https://tailwindcss.com/docs/grid-template-columns",
            "https://tailwindcss.com/docs/font-size",
            "https://tailwindcss.com/docs/text-color",
            "https://tailwindcss.com/docs/background-color",
            "https://tailwindcss.com/docs/border-radius",
            "https://tailwindcss.com/docs/box-shadow",
        ],
        "allowed_prefix": "https://tailwindcss.com/docs/",
        "url_must_contain": ["/docs/"],
    },
    # ── Node.js (제목 충돌로 1건만 저장됨 → 재크롤링) ──
    {
        "category": "백엔드",
        "name": "Node.js",
        "seed_urls": [
            "https://nodejs.org/en/learn/getting-started/introduction-to-nodejs",
            "https://nodejs.org/en/learn/getting-started/how-to-install-nodejs",
            "https://nodejs.org/en/learn/asynchronous-work/javascript-asynchronous-programming-and-callbacks",
            "https://nodejs.org/en/learn/modules/anatomy-of-an-http-transaction",
        ],
        "allowed_prefix": "https://nodejs.org/en/learn/",
        "url_must_contain": ["/en/learn/"],
    },
    # ── Kubernetes (이전 0건) ──
    {
        "category": "DevOps",
        "name": "Kubernetes",
        "seed_urls": [
            "https://kubernetes.io/docs/concepts/overview/",
            "https://kubernetes.io/docs/concepts/workloads/",
            "https://kubernetes.io/docs/concepts/services-networking/",
            "https://kubernetes.io/docs/concepts/storage/",
            "https://kubernetes.io/docs/concepts/configuration/",
            "https://kubernetes.io/docs/concepts/security/",
            "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
            "https://kubernetes.io/docs/tasks/tools/",
        ],
        "allowed_prefix": "https://kubernetes.io/docs/",
        "url_must_contain": ["/docs/"],
    },
    # ── 기타 부족했던 기술 ──
    {
        "category": "프론트엔드",
        "name": "Nuxt.js",
        "seed_urls": [
            "https://nuxt.com/docs/getting-started/introduction",
            "https://nuxt.com/docs/getting-started/installation",
            "https://nuxt.com/docs/getting-started/configuration",
            "https://nuxt.com/docs/getting-started/views",
            "https://nuxt.com/docs/getting-started/routing",
            "https://nuxt.com/docs/getting-started/data-fetching",
            "https://nuxt.com/docs/getting-started/state-management",
            "https://nuxt.com/docs/getting-started/error-handling",
            "https://nuxt.com/docs/getting-started/server",
            "https://nuxt.com/docs/getting-started/deployment",
        ],
        "allowed_prefix": "https://nuxt.com/docs/",
        "url_must_contain": ["/docs/"],
    },
    {
        "category": "백엔드",
        "name": "NestJS",
        "seed_urls": [
            "https://docs.nestjs.com/first-steps",
            "https://docs.nestjs.com/controllers",
            "https://docs.nestjs.com/providers",
            "https://docs.nestjs.com/modules",
            "https://docs.nestjs.com/middleware",
            "https://docs.nestjs.com/guards",
            "https://docs.nestjs.com/interceptors",
            "https://docs.nestjs.com/pipes",
            "https://docs.nestjs.com/exception-filters",
            "https://docs.nestjs.com/fundamentals/custom-providers",
            "https://docs.nestjs.com/techniques/database",
            "https://docs.nestjs.com/techniques/authentication",
            "https://docs.nestjs.com/techniques/validation",
            "https://docs.nestjs.com/websockets/gateways",
            "https://docs.nestjs.com/graphql/quick-start",
        ],
        "allowed_prefix": "https://docs.nestjs.com/",
        "url_must_contain": [],
    },
    {
        "category": "백엔드",
        "name": "Go",
        "seed_urls": [
            "https://go.dev/doc/tutorial/getting-started",
            "https://go.dev/doc/tutorial/create-module",
            "https://go.dev/doc/effective_go",
        ],
        "allowed_prefix": "https://go.dev/doc/",
        "url_must_contain": ["/doc/"],
    },
    {
        "category": "DB",
        "name": "MongoDB",
        "seed_urls": [
            "https://www.mongodb.com/docs/manual/tutorial/getting-started/",
            "https://www.mongodb.com/docs/manual/crud/",
            "https://www.mongodb.com/docs/manual/aggregation/",
            "https://www.mongodb.com/docs/manual/indexes/",
            "https://www.mongodb.com/docs/manual/data-modeling/",
            "https://www.mongodb.com/docs/manual/replication/",
            "https://www.mongodb.com/docs/manual/sharding/",
            "https://www.mongodb.com/docs/manual/administration/",
            "https://www.mongodb.com/docs/manual/security/",
        ],
        "allowed_prefix": "https://www.mongodb.com/docs/manual/",
        "url_must_contain": ["/docs/manual/"],
    },
]


if __name__ == '__main__':
    uploader = User.objects.filter(role='INSTRUCTOR').first() or User.objects.filter(username='admin').first()
    if not uploader:
        print("ERROR: 등록자 계정이 없습니다.")
        sys.exit(1)

    # 이미 크롤링된 URL 로드 (정확한 중복 방지)
    crawled_urls = load_crawled_urls()
    print(f"[INFO] DB에 이미 {len(crawled_urls)}개 URL이 크롤링되어 있음")

    print("=" * 60)
    print(f" Re:Boot Deep Crawler v2 — 보강 크롤링")
    print(f" 대상: {len(SITES)}개 기술 사이트")
    print(f" 사이트당 최대: {MAX_PAGES_PER_SITE}페이지")
    print("=" * 60)

    total_created = 0
    total_skipped = 0
    site_stats = []

    for site in SITES:
        pages = crawl_site(site, crawled_urls)

        created = 0
        for page in pages:
            title = page['title']
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

        total_created += created
        site_stats.append((site['name'], created, len(pages)))

    print("\n" + "=" * 60)
    print(" 📊 Deep Crawler v2 최종 보고")
    print("=" * 60)
    for name, created, crawled in site_stats:
        print(f"  {name:20s}: {created:3d}건 저장 / {crawled:3d}페이지 크롤링")
    print("-" * 60)
    print(f"  신규 생성: {total_created}건")
    print(f"  건너뜀  : {total_skipped}건")
    print(f"  총 LectureMaterial: {LectureMaterial.objects.count()}건")
    md_count = LectureMaterial.objects.filter(content_type='MARKDOWN').count()
    total_size = sum(len(m.content_data.encode('utf-8')) for m in LectureMaterial.objects.filter(content_type='MARKDOWN'))
    print(f"  MARKDOWN 콘텐츠 총 용량: {total_size/1024/1024:.1f}MB")
    print("=" * 60)
