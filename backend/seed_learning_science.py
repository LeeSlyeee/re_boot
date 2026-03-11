"""
Re:Boot Learning Science & Instructional Design 심화 자료 시드
================================================================
교육공학 기본 자료(seed_edtech_materials.py)에 추가하여,
'학습과학(Learning Science)'과 '교수설계(Instructional Design)' 분야를
더 깊이 있게 보충하는 스크립트.

한국어 + 영어 자료 포함.

실행: PYTHONUNBUFFERED=1 python seed_learning_science.py
"""
import os, sys, time, re, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

import requests
import html2text
from bs4 import BeautifulSoup
from learning.models import LectureMaterial
from users.models import User

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}
REQUEST_TIMEOUT = 20
DELAY = 1.2

converter = html2text.HTML2Text()
converter.ignore_links = False
converter.ignore_images = True
converter.body_width = 0
converter.ignore_emphasis = False


def fetch_page_as_markdown(url: str) -> tuple:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style', 'aside', 'noscript', 'iframe', 'svg']):
            tag.decompose()
        main = soup.find('main') or soup.find('article') or soup.find('[role="main"]')
        if main is None:
            main = soup.find('div', class_=re.compile(r'content|docs|main|article|mw-body', re.I))
        if main is None:
            main = soup.find('body') or soup
        markdown = converter.handle(str(main)).strip()
        markdown = re.sub(r'\n{4,}', '\n\n\n', markdown)
        if len(markdown) < 100:
            return f"[크롤링 내용 부족]\n원본 URL: {url}", False
        markdown = f"# 출처: {url}\n# 분야: 학습과학 & 교수설계 (Learning Science & Instructional Design)\n\n---\n\n{markdown}"
        return markdown, True
    except Exception as e:
        return f"[크롤링 실패: {str(e)}]\n원본 URL: {url}", False


MATERIALS = [
    # ══════════════════════════════════════════
    # PART A: Learning Science (학습과학) 심화
    # ══════════════════════════════════════════

    # ── 인지과학 기반 ──
    ("🧠 [학습과학] Learning Science 개요 (Wikipedia EN)", "https://en.wikipedia.org/wiki/Learning_science"),
    ("🧠 [학습과학] Science of Learning 개요 (Wikipedia EN)", "https://en.wikipedia.org/wiki/Science_of_learning"),
    ("🧠 [학습과학] 메타인지 (Metacognition)", "https://en.wikipedia.org/wiki/Metacognition"),
    ("🧠 [학습과학] 작업기억 (Working Memory)", "https://en.wikipedia.org/wiki/Working_memory"),
    ("🧠 [학습과학] 장기기억 (Long-term Memory)", "https://en.wikipedia.org/wiki/Long-term_memory"),
    ("🧠 [학습과학] 인지심리학 (Cognitive Psychology)", "https://en.wikipedia.org/wiki/Cognitive_psychology"),
    ("🧠 [학습과학] 스키마 이론 (Schema Theory)", "https://en.wikipedia.org/wiki/Schema_(psychology)"),
    ("🧠 [학습과학] 전이 (Transfer of Learning)", "https://en.wikipedia.org/wiki/Transfer_of_learning"),
    ("🧠 [학습과학] 분산 인지 (Distributed Cognition)", "https://en.wikipedia.org/wiki/Distributed_cognition"),

    # ── 학습 메커니즘 ──
    ("🔬 [학습과학] 정교화 (Elaboration in Learning)", "https://en.wikipedia.org/wiki/Elaborative_interrogation"),
    ("🔬 [학습과학] 인출 연습 (Retrieval Practice)", "https://en.wikipedia.org/wiki/Testing_effect"),
    ("🔬 [학습과학] 교차 연습 (Interleaving)", "https://en.wikipedia.org/wiki/Interleaving_(studying)"),
    ("🔬 [학습과학] 망각 곡선 (Forgetting Curve - Ebbinghaus)", "https://en.wikipedia.org/wiki/Forgetting_curve"),
    ("🔬 [학습과학] 기억 궁전 (Method of Loci)", "https://en.wikipedia.org/wiki/Method_of_loci"),
    ("🔬 [학습과학] 자기설명 효과 (Self-explanation)", "https://en.wikipedia.org/wiki/Self-explanation"),
    ("🔬 [학습과학] 학습 곡선 (Learning Curve)", "https://en.wikipedia.org/wiki/Learning_curve"),
    ("🔬 [학습과학] 의도적 연습 (Deliberate Practice)", "https://en.wikipedia.org/wiki/Practice_(learning_method)#Deliberate_practice"),

    # ── 동기 · 정서 ──
    ("💡 [학습과학] 자기결정이론 SDT (Self-determination Theory)", "https://en.wikipedia.org/wiki/Self-determination_theory"),
    ("💡 [학습과학] 내재적/외재적 동기 (Intrinsic Motivation)", "https://en.wikipedia.org/wiki/Intrinsic_motivation"),  
    ("💡 [학습과학] 자기효능감 (Self-efficacy - Bandura)", "https://en.wikipedia.org/wiki/Self-efficacy"),
    ("💡 [학습과학] 성장 마인드셋 (Growth Mindset - Dweck)", "https://en.wikipedia.org/wiki/Mindset#Fixed_and_growth_mindset"),
    ("💡 [학습과학] 몰입 이론 (Flow - Csikszentmihalyi)", "https://en.wikipedia.org/wiki/Flow_(psychology)"),
    ("💡 [학습과학] 귀인 이론 (Attribution Theory)", "https://en.wikipedia.org/wiki/Attribution_(psychology)"),
    ("💡 [학습과학] 기대-가치 이론 (Expectancy-value Theory)", "https://en.wikipedia.org/wiki/Expectancy-value_theory"),

    # ── 사회적 학습 ──
    ("👥 [학습과학] 사회학습이론 (Social Learning - Bandura)", "https://en.wikipedia.org/wiki/Social_learning_theory"),
    ("👥 [학습과학] 상황학습 (Situated Learning - Lave & Wenger)", "https://en.wikipedia.org/wiki/Situated_learning"),
    ("👥 [학습과학] 실천공동체 (Community of Practice)", "https://en.wikipedia.org/wiki/Community_of_practice"),
    ("👥 [학습과학] 활동이론 (Activity Theory)", "https://en.wikipedia.org/wiki/Activity_theory"),
    ("👥 [학습과학] 인지적 도제 (Cognitive Apprenticeship)", "https://en.wikipedia.org/wiki/Cognitive_apprenticeship"),

    # ── 신경과학 기반 ──
    ("🧬 [학습과학] 신경가소성 (Neuroplasticity)", "https://en.wikipedia.org/wiki/Neuroplasticity"),
    ("🧬 [학습과학] 교육신경과학 (Educational Neuroscience)", "https://en.wikipedia.org/wiki/Educational_neuroscience"),
    ("🧬 [학습과학] 수면과 학습 (Sleep and Learning)", "https://en.wikipedia.org/wiki/Sleep_and_learning"),

    # ══════════════════════════════════════════
    # PART B: Instructional Design (교수설계) 심화
    # ══════════════════════════════════════════

    # ── 교수설계 이론가 & 모델 ──
    ("📐 [교수설계] 딕앤케리 모델 (Dick and Carey)", "https://en.wikipedia.org/wiki/Dick_and_Carey_instructional_design_model"),
    ("📐 [교수설계] 메릴의 교수 원리 (Merrill's First Principles)", "https://en.wikipedia.org/wiki/First_principles_of_instruction"),
    ("📐 [교수설계] 켈러 ARCS 동기 모델", "https://en.wikipedia.org/wiki/ARCS_model"),
    ("📐 [교수설계] 라이겔루스 정교화 이론 (Elaboration Theory)", "https://en.wikipedia.org/wiki/Elaboration_theory"),
    ("📐 [교수설계] 래피드 프로토타이핑 ID (Rapid Prototyping)", "https://en.wikipedia.org/wiki/Rapid_prototyping"),
    ("📐 [교수설계] 커리큘럼 설계 (Curriculum Design)", "https://en.wikipedia.org/wiki/Curriculum"),
    ("📐 [교수설계] 학습목표 작성법 (Learning Objective)", "https://en.wikipedia.org/wiki/Learning_objective"),
    ("📐 [교수설계] 과제 분석 (Task Analysis)", "https://en.wikipedia.org/wiki/Task_analysis"),
    ("📐 [교수설계] 교수 매체 선택 (Instructional Media)", "https://en.wikipedia.org/wiki/Instructional_media"),

    # ── 수업 전략 ──
    ("📋 [교수설계] 직접 교수법 (Direct Instruction)", "https://en.wikipedia.org/wiki/Direct_instruction"),
    ("📋 [교수설계] 발견학습 (Discovery Learning - Bruner)", "https://en.wikipedia.org/wiki/Discovery_learning"),
    ("📋 [교수설계] 앵커드 수업 (Anchored Instruction)", "https://en.wikipedia.org/wiki/Anchored_instruction"),
    ("📋 [교수설계] 사례기반학습 (Case-based Learning)", "https://en.wikipedia.org/wiki/Case-based_reasoning"),
    ("📋 [교수설계] 개인화 학습 (Personalized Learning)", "https://en.wikipedia.org/wiki/Personalized_learning"),
    ("📋 [교수설계] 역량기반교육 (Competency-based Education)", "https://en.wikipedia.org/wiki/Competency-based_learning"),
    ("📋 [교수설계] 마스터리 러닝 (Mastery Learning - Bloom)", "https://en.wikipedia.org/wiki/Mastery_learning"),
    ("📋 [교수설계] 증거기반교수법 (Evidence-based Education)", "https://en.wikipedia.org/wiki/Evidence-based_education"),

    # ── 온라인/디지털 교수설계 ──
    ("🌐 [교수설계] 온라인 교수설계 (Online Course Design)", "https://en.wikipedia.org/wiki/Online_learning_in_higher_education"),
    ("🌐 [교수설계] 탐구공동체 모델 (Community of Inquiry)", "https://en.wikipedia.org/wiki/Community_of_inquiry"),
    ("🌐 [교수설계] 교수적 실재감 (Teaching Presence)", "https://en.wikipedia.org/wiki/Community_of_inquiry#Teaching_presence"),
    ("🌐 [교수설계] 학습경험설계 LXD (Learning Experience Design)", "https://en.wikipedia.org/wiki/Learning_experience_design"),
    ("🌐 [교수설계] 거꾸로 설계 + 평가 정렬 (Constructive Alignment)", "https://en.wikipedia.org/wiki/Constructive_alignment"),

    # ── 평가 및 피드백 설계 ──
    ("✏️ [교수설계] 피드백 이론 (Feedback in Education)", "https://en.wikipedia.org/wiki/Feedback"),
    ("✏️ [교수설계] 교육과정 평가 (Program Evaluation)", "https://en.wikipedia.org/wiki/Program_evaluation"),
    ("✏️ [교수설계] 커크패트릭 평가 모델 (Kirkpatrick Model)", "https://en.wikipedia.org/wiki/Kirkpatrick%27s_four_levels_of_training_evaluation"),

    # ══════════════════════════════════════════
    # PART C: 한국어 자료 (학습과학 + 교수설계)
    # ══════════════════════════════════════════
    ("🇰🇷 [학습과학] 인지심리학 (한국어)", "https://ko.wikipedia.org/wiki/%EC%9D%B8%EC%A7%80%EC%8B%AC%EB%A6%AC%ED%95%99"),
    ("🇰🇷 [학습과학] 메타인지 (한국어)", "https://ko.wikipedia.org/wiki/%EB%A9%94%ED%83%80%EC%9D%B8%EC%A7%80"),
    ("🇰🇷 [학습과학] 작업기억 (한국어)", "https://ko.wikipedia.org/wiki/%EC%9E%91%EC%97%85_%EA%B8%B0%EC%96%B5"),
    ("🇰🇷 [학습과학] 자기효능감 (한국어)", "https://ko.wikipedia.org/wiki/%EC%9E%90%EA%B8%B0%ED%9A%A8%EB%8A%A5%EA%B0%90"),
    ("🇰🇷 [학습과학] 몰입 이론 (한국어)", "https://ko.wikipedia.org/wiki/%EB%AA%B0%EC%9E%85"),
    ("🇰🇷 [학습과학] 비고츠키 (한국어)", "https://ko.wikipedia.org/wiki/%EB%A0%88%ED%94%84_%EB%B9%84%EA%B3%A0%EC%B8%A0%ED%82%A4"),
    ("🇰🇷 [학습과학] 신경가소성 (한국어)", "https://ko.wikipedia.org/wiki/%EC%8B%A0%EA%B2%BD%EA%B0%80%EC%86%8C%EC%84%B1"),
    ("🇰🇷 [학습과학] 장기기억 (한국어)", "https://ko.wikipedia.org/wiki/%EC%9E%A5%EA%B8%B0_%EA%B8%B0%EC%96%B5"),
    ("🇰🇷 [교수설계] 교수 설계 (한국어)", "https://ko.wikipedia.org/wiki/%EA%B5%90%EC%88%98_%EC%84%A4%EA%B3%84"),
    ("🇰🇷 [교수설계] 교육과정 (한국어)", "https://ko.wikipedia.org/wiki/%EA%B5%90%EC%9C%A1%EA%B3%BC%EC%A0%95"),
    ("🇰🇷 [교수설계] 자기주도학습 (한국어)", "https://ko.wikipedia.org/wiki/%EC%9E%90%EA%B8%B0%EC%A3%BC%EB%8F%84%ED%95%99%EC%8A%B5"),
    ("🇰🇷 [교수설계] 문제중심학습 PBL (한국어)", "https://ko.wikipedia.org/wiki/%EB%AC%B8%EC%A0%9C_%EC%A4%91%EC%8B%AC_%ED%95%99%EC%8A%B5"),
    ("🇰🇷 [교수설계] 역량기반교육 (한국어)", "https://ko.wikipedia.org/wiki/%EC%97%AD%EB%9F%89%EA%B8%B0%EB%B0%98%EA%B5%90%EC%9C%A1"),
    ("🇰🇷 [교수설계] 사회적 학습이론 (한국어)", "https://ko.wikipedia.org/wiki/%EC%82%AC%ED%9A%8C%EC%A0%81_%ED%95%99%EC%8A%B5_%EC%9D%B4%EB%A1%A0"),
]


if __name__ == '__main__':
    uploader = User.objects.filter(role='INSTRUCTOR').first() or User.objects.filter(username='admin').first()
    if not uploader:
        print("ERROR: 등록자(INSTRUCTOR 또는 admin) 계정이 DB에 없습니다.")
        sys.exit(1)
    print(f"[INFO] 등록자: {uploader.username} (id={uploader.id})")

    created_count = 0
    skipped_count = 0
    failed_count = 0

    print(f"\n{'='*60}")
    print(f" 🧠 Learning Science & Instructional Design 심화 시드")
    print(f" 총 {len(MATERIALS)}개 자료 크롤링 및 DB 삽입 시작")
    print(f"{'='*60}\n")

    for idx, (title, url) in enumerate(MATERIALS, 1):
        if LectureMaterial.objects.filter(title=title).exists():
            skipped_count += 1
            print(f"  [{idx:02d}/{len(MATERIALS)}] ⏭️  이미 존재: {title}")
            continue

        print(f"  [{idx:02d}/{len(MATERIALS)}] 🌐 크롤링 중: {title} ...", end=" ", flush=True)
        content, success = fetch_page_as_markdown(url)

        content_type = "MARKDOWN" if success else "LINK"
        content_data = content if success else url
        status_icon = "✅" if success else "⚠️"

        try:
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
            print(f"{status_icon} ({content_type}, {size_kb:.1f}KB)")
        except Exception as e:
            print(f"❌ DB 저장 실패: {e}")

        time.sleep(DELAY)

    print(f"\n{'='*60}")
    print(f" 📊 Learning Science & ID 시드 결과 보고")
    print(f"{'='*60}")
    print(f"  신규 생성: {created_count}건")
    print(f"  이미 존재(건너뜀): {skipped_count}건")
    print(f"  크롤링 실패(LINK 대체): {failed_count}건")
    print(f"  총 LectureMaterial 수: {LectureMaterial.objects.count()}건")
    print(f"{'='*60}")
    print(f"\n⚠️  벡터화가 필요합니다:")
    print(f"  PYTHONUNBUFFERED=1 python vectorize_materials.py")
