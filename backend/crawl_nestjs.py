"""
NestJS 공식 문서 크롤러 — GitHub 소스 직접 다운로드 방식
NestJS docs는 SPA라 HTML 크롤링 불가 → GitHub repo에서 마크다운 원본을 직접 가져옴
"""
import os, sys, time, django, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

import requests
from learning.models import LectureMaterial
from users.models import User

GITHUB_API = "https://api.github.com/repos/nestjs/docs.nestjs.com/contents/content"
RAW_BASE = "https://raw.githubusercontent.com/nestjs/docs.nestjs.com/master/content"
HEADERS = {'Accept': 'application/vnd.github.v3+json'}
DELAY = 0.5

uploader = User.objects.filter(role='INSTRUCTOR').first() or User.objects.filter(username='admin').first()
if not uploader:
    print("ERROR: 등록자 없음")
    sys.exit(1)


def list_md_files(api_url):
    """GitHub API로 디렉토리 내 모든 .md 파일을 재귀적으로 탐색"""
    files = []
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        items = resp.json()
    except Exception as e:
        print(f"  ❌ API 실패: {api_url} → {e}")
        return files

    for item in items:
        if item['type'] == 'file' and item['name'].endswith('.md'):
            files.append({
                'name': item['name'],
                'path': item['path'],
                'download_url': item['download_url'],
                'size': item['size'],
            })
        elif item['type'] == 'dir':
            # 하위 디렉토리도 재귀 탐색
            time.sleep(DELAY)
            sub_files = list_md_files(item['url'])
            files.extend(sub_files)

    return files


def download_md(url):
    """마크다운 파일 다운로드"""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except:
        return None


print("=" * 60)
print(" NestJS 공식 문서 크롤러 (GitHub 소스 직접 다운로드)")
print("=" * 60)

# 1. 모든 .md 파일 목록 수집
print("\n[1단계] GitHub repo에서 마크다운 파일 목록 수집 중...")
all_files = list_md_files(GITHUB_API)
print(f"  → 총 {len(all_files)}개 마크다운 파일 발견")

# 2. 각 파일 다운로드 및 DB 저장
print(f"\n[2단계] 마크다운 파일 다운로드 및 DB 저장 중...")
created = 0
skipped = 0

for idx, finfo in enumerate(all_files, 1):
    # 경로에서 제목 생성
    path_slug = finfo['path'].replace('content/', '').replace('.md', '')
    title = f"[백엔드] NestJS — {path_slug}"[:200]

    if LectureMaterial.objects.filter(title=title).exists():
        skipped += 1
        print(f"  [{idx:02d}/{len(all_files)}] ⏭️  이미 존재: {title}")
        continue

    md_content = download_md(finfo['download_url'])
    if not md_content or len(md_content) < 100:
        print(f"  [{idx:02d}/{len(all_files)}] ⚠️  내용 부족: {finfo['name']}")
        continue

    full_content = f"# 출처: https://docs.nestjs.com/{path_slug}\n# 기술: NestJS (백엔드)\n# GitHub: {finfo['download_url']}\n\n---\n\n{md_content}"

    LectureMaterial.objects.create(
        lecture=None,
        title=title,
        content_type='MARKDOWN',
        content_data=full_content,
        file_type='MD',
        uploaded_by=uploader,
    )
    created += 1
    print(f"  [{idx:02d}/{len(all_files)}] ✅ {path_slug} ({finfo['size']/1024:.1f}KB)")
    time.sleep(DELAY)

print(f"\n{'='*60}")
print(f" [결과] 신규 생성: {created}건 / 건너뜀: {skipped}건")
print(f" [결과] 총 LectureMaterial: {LectureMaterial.objects.count()}건")
total_size = sum(len(m.content_data.encode('utf-8')) for m in LectureMaterial.objects.filter(content_type='MARKDOWN'))
print(f" [결과] MARKDOWN 총 용량: {total_size/1024/1024:.1f}MB")
print(f"{'='*60}")
