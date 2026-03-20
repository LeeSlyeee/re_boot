"""
Django Management Command: update_tech_docs
=============================================
공식 문서 자동 최신화 커맨드.
- 기존 크롤링된 페이지를 재크롤링하여 변경분 감지
- 변경된 페이지만 LectureMaterial + VectorStore 업데이트
- 새로 발견된 페이지도 추가 크롤링

사용법:
  python manage.py update_tech_docs                # 전체 기술 업데이트
  python manage.py update_tech_docs --tech React   # 특정 기술만 업데이트
  python manage.py update_tech_docs --dry-run      # 변경분만 확인 (실제 업데이트 안함)
  python manage.py update_tech_docs --stats        # 현재 상태 통계만 출력

cron 등록 예시 (매주 일요일 새벽 3시):
  0 3 * * 0 cd /path/to/backend && /path/to/venv/bin/python manage.py update_tech_docs >> /var/log/reboot_docs_update.log 2>&1
"""
import os, sys, time, re, hashlib
from datetime import timedelta
from urllib.parse import urljoin, urlparse
from collections import deque

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Sum

import requests
import html2text
import openai
from bs4 import BeautifulSoup
from django.conf import settings

from learning.models import VectorStore, LectureMaterial
from users.models import User


# ═══════════════════════════════════════════════
# 공통 설정
# ═══════════════════════════════════════════════
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36',
}
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/nestjs/docs.nestjs.com/master/content"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 20

h2t = html2text.HTML2Text()
h2t.ignore_links = False
h2t.ignore_images = True
h2t.body_width = 0


class Command(BaseCommand):
    help = '공식 문서 자동 최신화 (크롤링 + 벡터 재색인)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tech', type=str, default=None,
            help='특정 기술만 업데이트 (예: React, Django, FastAPI)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='변경분만 확인, 실제 업데이트 안함'
        )
        parser.add_argument(
            '--stats', action='store_true',
            help='현재 상태 통계만 출력'
        )
        parser.add_argument(
            '--force', action='store_true',
            help='변경 여부와 관계없이 전체 재크롤링'
        )
        parser.add_argument(
            '--max-age-days', type=int, default=7,
            help='이 일수보다 오래된 문서만 업데이트 체크 (기본: 7일)'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.force = options['force']
        self.tech_filter = options['tech']
        self.max_age_days = options['max_age_days']

        if options['stats']:
            self._print_stats()
            return

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(' Re:Boot 공식 문서 자동 최신화'))
        self.stdout.write(self.style.SUCCESS(f' 시각: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'))
        if self.dry_run:
            self.stdout.write(self.style.WARNING(' [DRY RUN] 변경분 확인만 수행'))
        if self.tech_filter:
            self.stdout.write(self.style.WARNING(f' [FILTER] {self.tech_filter}만 업데이트'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 업로더 계정
        self.uploader = (
            User.objects.filter(role='INSTRUCTOR').first()
            or User.objects.filter(username='admin').first()
        )
        if not self.uploader:
            raise CommandError("등록자(INSTRUCTOR/admin) 계정이 없습니다.")

        # OpenAI 클라이언트
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

        # 업데이트 대상 레코드 조회
        qs = LectureMaterial.objects.filter(content_type='MARKDOWN', lecture__isnull=True)
        if self.tech_filter:
            qs = qs.filter(title__icontains=self.tech_filter)

        if not self.force:
            # max_age_days보다 오래된 것만 체크
            cutoff = timezone.now() - timedelta(days=self.max_age_days)
            qs = qs.filter(uploaded_at__lt=cutoff)

        materials = list(qs.order_by('id'))
        self.stdout.write(f"\n[대상] 업데이트 체크 대상: {len(materials)}건")

        updated = 0
        unchanged = 0
        failed = 0
        vectors_added = 0

        for idx, mat in enumerate(materials, 1):
            # 출처 URL 추출
            url = self._extract_source_url(mat.content_data)
            if not url:
                continue

            # 재크롤링
            new_content = self._fetch_content(url, mat.title)
            if not new_content:
                failed += 1
                continue

            # 변경 감지 (해시 비교)
            old_hash = hashlib.md5(mat.content_data.encode()).hexdigest()
            new_hash = hashlib.md5(new_content.encode()).hexdigest()

            if old_hash == new_hash and not self.force:
                unchanged += 1
                continue

            self.stdout.write(
                f"  [{idx:04d}] 🔄 변경 감지: {mat.title[:50]}..."
            )

            if not self.dry_run:
                # LectureMaterial 업데이트
                mat.content_data = new_content
                mat.uploaded_at = timezone.now()
                mat.save(update_fields=['content_data', 'uploaded_at'])

                # 기존 벡터 삭제 후 재생성
                old_vectors = VectorStore.objects.filter(
                    source_type='material',
                    content__startswith=mat.content_data[:50]
                )
                # 더 정확한 매칭을 위해 출처 URL 기반으로 삭제
                if url:
                    old_vectors = VectorStore.objects.filter(
                        source_type='material',
                        content__contains=url[:80]
                    )
                old_count = old_vectors.count()
                old_vectors.delete()

                # 새 청크 생성 및 벡터화
                chunks = self._chunk_text(new_content)
                if chunks:
                    new_vectors = self._vectorize_chunks(chunks)
                    vectors_added += new_vectors
                    self.stdout.write(
                        f"           → 기존 {old_count}벡터 삭제, {new_vectors}벡터 신규 생성"
                    )

                updated += 1

            time.sleep(0.5)

        # 결과 보고
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS(' 📊 최신화 결과'))
        self.stdout.write(self.style.SUCCESS(f"{'='*60}"))
        self.stdout.write(f"  체크 대상: {len(materials)}건")
        self.stdout.write(f"  업데이트: {updated}건")
        self.stdout.write(f"  변경 없음: {unchanged}건")
        self.stdout.write(f"  실패: {failed}건")
        self.stdout.write(f"  벡터 신규 생성: {vectors_added}개")
        self.stdout.write(self.style.SUCCESS(f"{'='*60}"))

        # 업데이트 로그 기록
        self._log_update(len(materials), updated, unchanged, failed, vectors_added)

    def _extract_source_url(self, content_data):
        """content_data 첫 줄에서 출처 URL 추출"""
        if not content_data:
            return None
        first_line = content_data.split('\n')[0]
        match = re.match(r'^# 출처:\s*(https?://\S+)', first_line)
        return match.group(1) if match else None

    def _fetch_content(self, url, title):
        """URL에서 최신 콘텐츠를 가져옴"""
        try:
            # NestJS GitHub 소스인 경우
            if 'docs.nestjs.com' in url:
                path = url.replace('https://docs.nestjs.com/', '').strip('/')
                github_url = f"{GITHUB_RAW_BASE}/{path}.md"
                resp = requests.get(github_url, timeout=15)
                if resp.status_code == 200:
                    md_content = resp.text
                    return f"# 출처: {url}\n# 기술: NestJS (백엔드)\n\n---\n\n{md_content}"
                return None

            # 일반 HTML 크롤링
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style',
                                       'aside', 'noscript', 'iframe', 'svg']):
                tag.decompose()

            main = soup.find('main') or soup.find('article') or soup.find('body') or soup
            md = h2t.handle(str(main)).strip()
            md = re.sub(r'\n{4,}', '\n\n\n', md)

            if len(md) < 100:
                return None

            # 기술명 추출
            tech_match = re.search(r'\[(.+?)\]\s+(.+?)\s+—', title)
            tech_info = f"# 기술: {tech_match.group(2)} ({tech_match.group(1)})" if tech_match else ""

            return f"# 출처: {url}\n{tech_info}\n\n---\n\n{md}"

        except Exception:
            return None

    def _chunk_text(self, text):
        """텍스트를 청크로 분할"""
        if not text or len(text.strip()) < 50:
            return []

        chunks = []
        paragraphs = text.split('\n\n')
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) + 2 <= CHUNK_SIZE:
                current += ("\n\n" + para) if current else para
            else:
                if len(current.strip()) >= 50:
                    chunks.append(current.strip())
                if CHUNK_OVERLAP > 0 and current:
                    current = current[-CHUNK_OVERLAP:] + "\n\n" + para
                else:
                    current = para
                while len(current) > CHUNK_SIZE:
                    sp = current.rfind('. ', 0, CHUNK_SIZE)
                    if sp < CHUNK_SIZE // 2:
                        sp = CHUNK_SIZE
                    c = current[:sp + 1].strip()
                    if len(c) >= 50:
                        chunks.append(c)
                    current = current[sp + 1:].strip()

        if len(current.strip()) >= 50:
            chunks.append(current.strip())
        return chunks

    def _vectorize_chunks(self, chunks):
        """청크를 벡터화하여 VectorStore에 저장"""
        total = 0
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            cleaned = [t.replace("\n", " ")[:8000] for t in batch]
            try:
                resp = self.openai_client.embeddings.create(
                    input=cleaned, model=EMBEDDING_MODEL
                )
                embeddings = [d.embedding for d in resp.data]
                objs = [
                    VectorStore(
                        content=chunk,
                        embedding=emb,
                        session=None,
                        lecture=None,
                        source_type='material',
                    )
                    for chunk, emb in zip(batch, embeddings)
                ]
                VectorStore.objects.bulk_create(objs)
                total += len(objs)
                time.sleep(0.3)
            except Exception as e:
                self.stderr.write(f"    ❌ 벡터화 오류: {e}")
        return total

    def _print_stats(self):
        """현재 시스템 상태 통계 출력"""
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(' 📊 Re:Boot 공식 문서 RAG 현황'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        total_mat = LectureMaterial.objects.filter(lecture__isnull=True).count()
        md_mat = LectureMaterial.objects.filter(content_type='MARKDOWN', lecture__isnull=True).count()
        total_vec = VectorStore.objects.count()
        mat_vec = VectorStore.objects.filter(source_type='material').count()

        # 기술별 통계
        from django.db.models import Count
        tech_stats = {}
        for mat in LectureMaterial.objects.filter(content_type='MARKDOWN', lecture__isnull=True):
            match = re.match(r'\[(.+?)\]\s+(.+?)[\s—]', mat.title)
            if match:
                tech = match.group(2).strip()
                tech_stats[tech] = tech_stats.get(tech, 0) + 1

        self.stdout.write(f"\n  총 LectureMaterial (공통): {total_mat}건")
        self.stdout.write(f"  MARKDOWN 레코드: {md_mat}건")
        self.stdout.write(f"  총 VectorStore: {total_vec}개")
        self.stdout.write(f"  공식문서 벡터 (material): {mat_vec}개")

        self.stdout.write(f"\n  {'─'*40}")
        self.stdout.write(f"  기술별 문서 수:")
        for tech, count in sorted(tech_stats.items(), key=lambda x: -x[1]):
            self.stdout.write(f"    {tech:25s}: {count:4d}건")

        self.stdout.write(self.style.SUCCESS(f"{'='*60}"))

    def _log_update(self, total, updated, unchanged, failed, vectors):
        """업데이트 로그를 파일에 기록"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'docs_update.log')

        with open(log_file, 'a') as f:
            f.write(
                f"[{timezone.now().isoformat()}] "
                f"체크={total} 업데이트={updated} 변경없음={unchanged} "
                f"실패={failed} 벡터생성={vectors}\n"
            )
