"""
Re:Boot Deep Crawler v3 — 미수록 웹 개발 공식문서 추가
======================================================
기존에 없는 기술 공식문서를 크롤링하여 LectureMaterial에 저장.
저장 후 vectorize_materials.py로 벡터화 필요.

추가 대상:
  - Vite (빌드 도구)
  - Angular (프레임워크)
  - Remix (React 프레임워크)
  - Astro (정적 사이트)
  - Prisma (ORM)
  - Drizzle ORM
  - tRPC (타입세이프 API)
  - Deno (런타임)
  - Bun (런타임)
  - Jest (테스팅)
  - Vitest (테스팅)
  - Playwright (E2E 테스팅)
  - Webpack (번들러)
  - Supabase (BaaS)
  - Sass/SCSS (CSS 전처리기)
  - Pinia (Vue 상태관리)

실행: PYTHONUNBUFFERED=1 python deep_crawl_v3.py
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
# 설정 (deep_crawl_v2와 동일)
# ═══════════════════════════════════════════════
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
REQUEST_TIMEOUT = 20
DELAY = 0.8
MAX_PAGES_PER_SITE = 80
MIN_CONTENT_LENGTH = 200

h2t = html2text.HTML2Text()
h2t.ignore_links = False
h2t.ignore_images = True
h2t.body_width = 0

def load_crawled_urls():
    urls = set()
    for mat in LectureMaterial.objects.filter(content_type='MARKDOWN').only('content_data'):
        first_line = mat.content_data.split('\n')[0] if mat.content_data else ''
        match = re.match(r'^# 출처:\s*(https?://\S+)', first_line)
        if match:
            urls.add(normalize_url(match.group(1)))
    return urls

def normalize_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def url_to_slug(url, category, name):
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip('/').split('/') if p]
    slug = '/'.join(parts[-3:]) if len(parts) > 3 else '/'.join(parts) if parts else 'index'
    slug = re.sub(r'\.(html|htm|md|mdx)$', '', slug)
    return f"[{category}] {name} — {slug}"[:200]

def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.url
    except:
        return None, url

def html_to_markdown(html_str):
    soup = BeautifulSoup(html_str, 'html.parser')
    for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style', 'aside', 'noscript', 'iframe', 'svg']):
        tag.decompose()
    main = soup.find('main') or soup.find('article') or soup.find('[role="main"]')
    if main is None:
        main = soup.find('div', class_=re.compile(r'content|docs|main|article', re.I))
    if main is None:
        main = soup.find('body') or soup
    markdown = h2t.handle(str(main)).strip()
    return re.sub(r'\n{4,}', '\n\n\n', markdown)

def discover_links(html_str, base_url, allowed_prefix, url_filters):
    soup = BeautifulSoup(html_str, 'html.parser')
    links = set()
    skip_exts = ['.png', '.jpg', '.gif', '.svg', '.pdf', '.zip', '.tar', '.ico', '.css', '.js', '.xml', '.json']
    for a_tag in soup.find_all('a', href=True):
        full_url = normalize_url(urljoin(base_url, a_tag['href']))
        if not full_url.startswith(allowed_prefix):
            continue
        if any(urlparse(full_url).path.endswith(ext) for ext in skip_exts):
            continue
        if url_filters and not any(f in full_url for f in url_filters):
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

        if url in crawled_urls:
            html_str, final_url = fetch_page(url)
            if html_str:
                for link in discover_links(html_str, final_url, allowed_prefix, url_filters):
                    if link not in visited:
                        queue.append(link)
            time.sleep(DELAY * 0.5)
            continue

        html_str, final_url = fetch_page(url)
        if not html_str:
            continue

        markdown = html_to_markdown(html_str)
        if len(markdown) < MIN_CONTENT_LENGTH:
            if html_str:
                for link in discover_links(html_str, final_url, allowed_prefix, url_filters):
                    if link not in visited:
                        queue.append(link)
            continue

        title = url_to_slug(url, category, name)
        if LectureMaterial.objects.filter(title=title).exists():
            url_hash = hashlib.md5(url.encode()).hexdigest()[:6]
            title = f"{title[:193]}_{url_hash}"

        results.append({
            'title': title,
            'url': url,
            'content': f"# 출처: {url}\n# 기술: {name} ({category})\n\n---\n\n{markdown}",
        })
        crawled_urls.add(url)
        print(f"    ✅ [{len(results):02d}] ...{url[-55:]} ({len(markdown)/1024:.1f}KB)")

        for link in discover_links(html_str, final_url, allowed_prefix, url_filters):
            if link not in visited:
                queue.append(link)
        time.sleep(DELAY)

    print(f"  📊 [{name}] 완료: {len(results)}페이지 크롤링 / {len(visited)}페이지 방문")
    return results


# ═══════════════════════════════════════════════
# 신규 추가 대상 사이트
# ═══════════════════════════════════════════════
SITES = [
    # ── 빌드 도구 ──
    {
        "category": "빌드도구",
        "name": "Vite",
        "seed_urls": [
            "https://vite.dev/guide/",
            "https://vite.dev/guide/features",
            "https://vite.dev/guide/cli",
            "https://vite.dev/guide/using-plugins",
            "https://vite.dev/guide/dep-pre-bundling",
            "https://vite.dev/guide/build",
            "https://vite.dev/guide/static-deploy",
            "https://vite.dev/guide/env-and-mode",
            "https://vite.dev/guide/ssr",
            "https://vite.dev/config/",
        ],
        "allowed_prefix": "https://vite.dev/",
        "url_must_contain": ["/guide", "/config"],
    },
    {
        "category": "빌드도구",
        "name": "Webpack",
        "seed_urls": [
            "https://webpack.js.org/concepts/",
            "https://webpack.js.org/concepts/entry-points/",
            "https://webpack.js.org/concepts/output/",
            "https://webpack.js.org/concepts/loaders/",
            "https://webpack.js.org/concepts/plugins/",
            "https://webpack.js.org/guides/getting-started/",
            "https://webpack.js.org/guides/asset-management/",
            "https://webpack.js.org/guides/code-splitting/",
            "https://webpack.js.org/guides/tree-shaking/",
            "https://webpack.js.org/guides/hot-module-replacement/",
        ],
        "allowed_prefix": "https://webpack.js.org/",
        "url_must_contain": ["/concepts", "/guides", "/configuration"],
    },
    # ── 프레임워크 ──
    {
        "category": "프론트엔드",
        "name": "Angular",
        "seed_urls": [
            "https://angular.dev/overview",
            "https://angular.dev/essentials",
            "https://angular.dev/guide/components",
            "https://angular.dev/guide/templates",
            "https://angular.dev/guide/signals",
            "https://angular.dev/guide/forms",
            "https://angular.dev/guide/http",
            "https://angular.dev/guide/routing",
            "https://angular.dev/guide/di",
            "https://angular.dev/guide/pipes",
        ],
        "allowed_prefix": "https://angular.dev/",
        "url_must_contain": ["/guide", "/essentials", "/overview"],
    },
    {
        "category": "프론트엔드",
        "name": "Astro",
        "seed_urls": [
            "https://docs.astro.build/en/getting-started/",
            "https://docs.astro.build/en/basics/project-structure/",
            "https://docs.astro.build/en/basics/astro-components/",
            "https://docs.astro.build/en/basics/astro-pages/",
            "https://docs.astro.build/en/basics/layouts/",
            "https://docs.astro.build/en/basics/rendering-modes/",
            "https://docs.astro.build/en/guides/routing/",
            "https://docs.astro.build/en/guides/content-collections/",
            "https://docs.astro.build/en/guides/styling/",
            "https://docs.astro.build/en/guides/deploy/",
        ],
        "allowed_prefix": "https://docs.astro.build/en/",
        "url_must_contain": ["/en/"],
    },
    # ── ORM / DB 도구 ──
    {
        "category": "ORM",
        "name": "Prisma",
        "seed_urls": [
            "https://www.prisma.io/docs/getting-started",
            "https://www.prisma.io/docs/concepts/components/prisma-schema",
            "https://www.prisma.io/docs/concepts/components/prisma-client",
            "https://www.prisma.io/docs/concepts/components/prisma-migrate",
            "https://www.prisma.io/docs/guides/database/developing-with-prisma-migrate",
        ],
        "allowed_prefix": "https://www.prisma.io/docs/",
        "url_must_contain": ["/docs/"],
    },
    # ── 런타임 ──
    {
        "category": "런타임",
        "name": "Deno",
        "seed_urls": [
            "https://docs.deno.com/runtime/",
            "https://docs.deno.com/runtime/fundamentals/",
            "https://docs.deno.com/runtime/fundamentals/typescript/",
            "https://docs.deno.com/runtime/fundamentals/modules/",
            "https://docs.deno.com/runtime/fundamentals/configuration/",
            "https://docs.deno.com/runtime/fundamentals/testing/",
            "https://docs.deno.com/runtime/fundamentals/linting_and_formatting/",
            "https://docs.deno.com/runtime/reference/cli/",
        ],
        "allowed_prefix": "https://docs.deno.com/runtime/",
        "url_must_contain": ["/runtime/"],
    },
    {
        "category": "런타임",
        "name": "Bun",
        "seed_urls": [
            "https://bun.sh/docs",
            "https://bun.sh/docs/installation",
            "https://bun.sh/docs/cli/run",
            "https://bun.sh/docs/cli/install",
            "https://bun.sh/docs/runtime/modules",
            "https://bun.sh/docs/runtime/typescript",
            "https://bun.sh/docs/bundler",
            "https://bun.sh/docs/test/writing",
            "https://bun.sh/docs/api/http",
            "https://bun.sh/docs/api/websockets",
        ],
        "allowed_prefix": "https://bun.sh/docs",
        "url_must_contain": ["/docs"],
    },
    # ── 테스팅 ──
    {
        "category": "테스팅",
        "name": "Jest",
        "seed_urls": [
            "https://jestjs.io/docs/getting-started",
            "https://jestjs.io/docs/using-matchers",
            "https://jestjs.io/docs/asynchronous",
            "https://jestjs.io/docs/setup-teardown",
            "https://jestjs.io/docs/mock-functions",
            "https://jestjs.io/docs/snapshot-testing",
            "https://jestjs.io/docs/timer-mocks",
            "https://jestjs.io/docs/configuration",
        ],
        "allowed_prefix": "https://jestjs.io/docs/",
        "url_must_contain": ["/docs/"],
    },
    {
        "category": "테스팅",
        "name": "Vitest",
        "seed_urls": [
            "https://vitest.dev/guide/",
            "https://vitest.dev/guide/features",
            "https://vitest.dev/guide/cli",
            "https://vitest.dev/guide/filtering",
            "https://vitest.dev/guide/snapshot",
            "https://vitest.dev/guide/mocking",
            "https://vitest.dev/guide/coverage",
            "https://vitest.dev/api/",
        ],
        "allowed_prefix": "https://vitest.dev/",
        "url_must_contain": ["/guide", "/api"],
    },
    {
        "category": "테스팅",
        "name": "Playwright",
        "seed_urls": [
            "https://playwright.dev/docs/intro",
            "https://playwright.dev/docs/writing-tests",
            "https://playwright.dev/docs/running-tests",
            "https://playwright.dev/docs/locators",
            "https://playwright.dev/docs/assertions",
            "https://playwright.dev/docs/pages",
            "https://playwright.dev/docs/navigations",
            "https://playwright.dev/docs/api-testing",
            "https://playwright.dev/docs/test-configuration",
        ],
        "allowed_prefix": "https://playwright.dev/docs/",
        "url_must_contain": ["/docs/"],
    },
    # ── BaaS ──
    {
        "category": "BaaS",
        "name": "Supabase",
        "seed_urls": [
            "https://supabase.com/docs/guides/getting-started",
            "https://supabase.com/docs/guides/database/overview",
            "https://supabase.com/docs/guides/auth",
            "https://supabase.com/docs/guides/storage",
            "https://supabase.com/docs/guides/realtime",
            "https://supabase.com/docs/guides/functions",
            "https://supabase.com/docs/guides/api",
        ],
        "allowed_prefix": "https://supabase.com/docs/",
        "url_must_contain": ["/docs/"],
    },
    # ── 상태관리 ──
    {
        "category": "프론트엔드",
        "name": "Pinia",
        "seed_urls": [
            "https://pinia.vuejs.org/introduction.html",
            "https://pinia.vuejs.org/getting-started.html",
            "https://pinia.vuejs.org/core-concepts/",
            "https://pinia.vuejs.org/core-concepts/state.html",
            "https://pinia.vuejs.org/core-concepts/getters.html",
            "https://pinia.vuejs.org/core-concepts/actions.html",
            "https://pinia.vuejs.org/core-concepts/plugins.html",
        ],
        "allowed_prefix": "https://pinia.vuejs.org/",
        "url_must_contain": [],
    },
    # ── CSS ──
    {
        "category": "CSS",
        "name": "Sass/SCSS",
        "seed_urls": [
            "https://sass-lang.com/guide/",
            "https://sass-lang.com/documentation/syntax/",
            "https://sass-lang.com/documentation/variables/",
            "https://sass-lang.com/documentation/interpolation/",
            "https://sass-lang.com/documentation/at-rules/mixin/",
            "https://sass-lang.com/documentation/at-rules/function/",
            "https://sass-lang.com/documentation/at-rules/control/if/",
            "https://sass-lang.com/documentation/at-rules/control/each/",
            "https://sass-lang.com/documentation/modules/",
        ],
        "allowed_prefix": "https://sass-lang.com/",
        "url_must_contain": ["/documentation", "/guide"],
    },
]


if __name__ == '__main__':
    uploader = User.objects.filter(role='INSTRUCTOR').first() or User.objects.filter(username='admin').first()
    if not uploader:
        print("ERROR: 등록자 계정이 없습니다.")
        sys.exit(1)

    crawled_urls = load_crawled_urls()
    print(f"[INFO] DB에 이미 {len(crawled_urls)}개 URL이 크롤링되어 있음")

    print("=" * 60)
    print(f" Re:Boot Deep Crawler v3 — 미수록 웹 개발 문서 추가")
    print(f" 대상: {len(SITES)}개 기술 사이트")
    print(f" 사이트당 최대: {MAX_PAGES_PER_SITE}페이지")
    print("=" * 60)

    total_created = 0
    site_stats = []

    for site in SITES:
        pages = crawl_site(site, crawled_urls)
        created = 0
        for page in pages:
            title = page['title']
            if LectureMaterial.objects.filter(title=title).exists():
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
    print(" 📊 Deep Crawler v3 최종 보고")
    print("=" * 60)
    for name, created, crawled in site_stats:
        print(f"  {name:20s}: {created:3d}건 저장 / {crawled:3d}페이지 크롤링")
    print("-" * 60)
    print(f"  신규 생성: {total_created}건")
    print(f"  총 LectureMaterial: {LectureMaterial.objects.count()}건")
    print("=" * 60)
    print("\n⚠️  벡터화가 필요합니다. 다음 명령어를 실행하세요:")
    print("  PYTHONUNBUFFERED=1 python vectorize_materials.py")
