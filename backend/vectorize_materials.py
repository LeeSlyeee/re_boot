"""
Phase 2: RAG 벡터화 파이프라인
================================
LectureMaterial의 MARKDOWN 콘텐츠를 청크 분할 → OpenAI 임베딩 → VectorStore 저장

동작:
1. LectureMaterial에서 source_type='material'로 아직 벡터화되지 않은 MARKDOWN 레코드 조회
2. 1,000자 단위로 텍스트 청크 분할 (오버랩 200자)
3. OpenAI text-embedding-3-small로 벡터 변환 (1536 dim)
4. VectorStore 테이블에 저장

실행: PYTHONUNBUFFERED=1 python vectorize_materials.py
"""
import os, sys, time, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

import openai
from django.conf import settings
from learning.models import VectorStore, LectureMaterial

# ═══════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════
CHUNK_SIZE = 1000       # 청크 크기 (문자 단위)
CHUNK_OVERLAP = 200     # 청크 간 오버랩 (문맥 유지)
BATCH_SIZE = 20         # OpenAI API 배치 크기 (한 번에 임베딩할 텍스트 수)
EMBEDDING_MODEL = "text-embedding-3-small"
DELAY_BETWEEN_BATCHES = 0.3  # API rate limit 방지

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)


# ═══════════════════════════════════════════════
# 텍스트 청크 분할
# ═══════════════════════════════════════════════
def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    텍스트를 chunk_size 단위로 분할.
    - 문단(\\n\\n) 경계를 우선적으로 분할 지점으로 사용
    - overlap으로 이전 청크의 끝부분을 다음 청크 시작에 포함 (문맥 유지)
    """
    if not text or len(text.strip()) < 50:
        return []

    chunks = []
    # 먼저 \n\n으로 문단 분리
    paragraphs = text.split('\n\n')

    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 현재 청크에 문단을 추가해도 chunk_size 이내면 합침
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += ("\n\n" + para) if current_chunk else para
        else:
            # 현재 청크가 유효하면 저장
            if len(current_chunk.strip()) >= 50:
                chunks.append(current_chunk.strip())

            # 오버랩: 이전 청크의 마지막 overlap 문자를 가져옴
            if overlap > 0 and current_chunk:
                overlap_text = current_chunk[-overlap:]
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk = para

            # 단일 문단이 chunk_size보다 큰 경우 강제 분할
            while len(current_chunk) > chunk_size:
                split_point = current_chunk.rfind('. ', 0, chunk_size)
                if split_point < chunk_size // 2:
                    split_point = chunk_size
                chunk = current_chunk[:split_point + 1].strip()
                if len(chunk) >= 50:
                    chunks.append(chunk)
                current_chunk = current_chunk[split_point + 1:].strip()

    # 마지막 남은 청크
    if len(current_chunk.strip()) >= 50:
        chunks.append(current_chunk.strip())

    return chunks


def get_embeddings_batch(texts):
    """OpenAI API로 텍스트 배치의 임베딩을 한 번에 가져옴"""
    cleaned = [t.replace("\n", " ")[:8000] for t in texts]  # 토큰 제한 방지
    try:
        response = client.embeddings.create(
            input=cleaned,
            model=EMBEDDING_MODEL
        )
        return [d.embedding for d in response.data]
    except Exception as e:
        print(f"    ❌ 임베딩 API 오류: {e}")
        return None


# ═══════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 60)
    print(" Phase 2: RAG 벡터화 파이프라인")
    print("=" * 60)

    # 이미 벡터화된 material ID 조회
    already_vectorized_content = set(
        VectorStore.objects.filter(source_type='material')
        .values_list('content', flat=True)
    )
    print(f"[INFO] 이미 벡터화된 청크: {len(already_vectorized_content)}개")

    # 벡터화 대상 MARKDOWN 레코드 조회
    materials = LectureMaterial.objects.filter(
        content_type='MARKDOWN'
    ).order_by('id')
    total_materials = materials.count()
    print(f"[INFO] 벡터화 대상 MARKDOWN 레코드: {total_materials}건")

    total_chunks = 0
    total_vectors = 0
    total_skipped = 0
    errors = 0

    for idx, mat in enumerate(materials, 1):
        # 청크 분할
        chunks = chunk_text(mat.content_data)
        if not chunks:
            continue

        # 새로운 청크만 필터링 (이미 벡터화된 것 제외)
        new_chunks = [c for c in chunks if c not in already_vectorized_content]
        if not new_chunks:
            total_skipped += len(chunks)
            if idx % 100 == 0:
                print(f"  [{idx:04d}/{total_materials}] ⏭️  이미 벡터화됨: {mat.title[:50]}...")
            continue

        total_chunks += len(new_chunks)

        # 배치 단위로 임베딩
        for batch_start in range(0, len(new_chunks), BATCH_SIZE):
            batch = new_chunks[batch_start:batch_start + BATCH_SIZE]
            embeddings = get_embeddings_batch(batch)

            if embeddings is None:
                errors += len(batch)
                continue

            # VectorStore에 저장
            vectors_to_create = []
            for chunk_text_item, embedding in zip(batch, embeddings):
                vectors_to_create.append(VectorStore(
                    content=chunk_text_item,
                    embedding=embedding,
                    session=None,
                    lecture=None,  # 공통 기초 자료 (강의 비종속)
                    source_type='material',
                ))

            VectorStore.objects.bulk_create(vectors_to_create)
            total_vectors += len(vectors_to_create)
            time.sleep(DELAY_BETWEEN_BATCHES)

        if idx % 50 == 0 or idx <= 5:
            print(f"  [{idx:04d}/{total_materials}] ✅ {mat.title[:45]}... → {len(new_chunks)}청크")

    print(f"\n{'='*60}")
    print(f" 📊 RAG 벡터화 완료 보고")
    print(f"{'='*60}")
    print(f"  처리한 MARKDOWN 레코드: {total_materials}건")
    print(f"  생성된 텍스트 청크: {total_chunks}개")
    print(f"  저장된 벡터(VectorStore): {total_vectors}개")
    print(f"  건너뜀 (이미 벡터화): {total_skipped}개")
    print(f"  오류: {errors}개")
    print(f"  총 VectorStore 레코드: {VectorStore.objects.count()}개")
    mat_vectors = VectorStore.objects.filter(source_type='material').count()
    print(f"  (source_type='material'): {mat_vectors}개")
    print(f"{'='*60}")
