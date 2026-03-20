"""
Re:Boot 교육공학(Educational Technology) 학습 자료 시드 스크립트
================================================================
교육공학 핵심 이론 및 실무 관련 공식문서/학술자료를 크롤링하여
LectureMaterial 테이블에 저장.

대상 (한국어 + 영어):
  - 교수설계(Instructional Design) — ADDIE, SAM, Backward Design
  - 학습이론(Learning Theories) — 행동주의, 인지주의, 구성주의, 커넥티비즘
  - 에듀테크(EdTech) — LMS, 블렌디드 러닝, 플립러닝, 적응형 학습
  - 교육평가(Assessment) — 형성평가, 총괄평가, 루브릭
  - UDL(보편적 학습 설계)
  - 학습분석(Learning Analytics)
  - OER(Open Educational Resources)
  - 게이미피케이션(Gamification in Education)
  - AI in Education

저장 후 vectorize_materials.py로 벡터화 필요.
실행: PYTHONUNBUFFERED=1 python seed_edtech_materials.py
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

# ─────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────
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
    """URL 페이지를 마크다운으로 변환. Returns: (markdown_text, success_flag)"""
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
        markdown = f"# 출처: {url}\n# 분야: 교육공학 (Educational Technology)\n\n---\n\n{markdown}"
        return markdown, True
    except Exception as e:
        return f"[크롤링 실패: {str(e)}]\n원본 URL: {url}", False


# ═══════════════════════════════════════════════════
# 교육공학 학습 자료 목록 (한국어 + 영어)
# ═══════════════════════════════════════════════════
MATERIALS = [
    # ── 1. 교수설계 (Instructional Design) ──
    ("🎓 [교육공학] ADDIE 모델 개요 (Wikipedia)", "https://en.wikipedia.org/wiki/ADDIE_Model"),
    ("🎓 [교육공학] Instructional Design 개요 (Wikipedia)", "https://en.wikipedia.org/wiki/Instructional_design"),
    ("🎓 [교육공학] Backward Design 이론 (Wikipedia)", "https://en.wikipedia.org/wiki/Backward_design"),
    ("🎓 [교육공학] SAM (Successive Approximation Model)", "https://en.wikipedia.org/wiki/Successive_approximation_model"),

    # ── 2. 학습이론 (Learning Theories) ──
    ("📚 [교육공학] 행동주의 학습이론 (Behaviorism)", "https://en.wikipedia.org/wiki/Behaviorism"),
    ("📚 [교육공학] 인지주의 학습이론 (Cognitivism)", "https://en.wikipedia.org/wiki/Cognitivism_(psychology)"),
    ("📚 [교육공학] 구성주의 학습이론 (Constructivism)", "https://en.wikipedia.org/wiki/Constructivism_(philosophy_of_education)"),
    ("📚 [교육공학] 커넥티비즘 (Connectivism)", "https://en.wikipedia.org/wiki/Connectivism"),
    ("📚 [교육공학] 사회적 구성주의 - 비고츠키 (ZPD)", "https://en.wikipedia.org/wiki/Zone_of_proximal_development"),
    ("📚 [교육공학] 블룸의 교육목표 분류학 (Bloom's Taxonomy)", "https://en.wikipedia.org/wiki/Bloom%27s_taxonomy"),
    ("📚 [교육공학] 가네의 9가지 수업사태 (Gagné's Nine Events)", "https://en.wikipedia.org/wiki/Robert_M._Gagn%C3%A9"),
    ("📚 [교육공학] 앤드라고지 - 성인학습이론 (Andragogy)", "https://en.wikipedia.org/wiki/Andragogy"),
    ("📚 [교육공학] 자기주도학습 (Self-directed Learning)", "https://en.wikipedia.org/wiki/Autodidacticism"),
    ("📚 [교육공학] 체험학습 - 콜브 (Experiential Learning)", "https://en.wikipedia.org/wiki/Experiential_learning"),
    ("📚 [교육공학] 다중지능이론 (Multiple Intelligences)", "https://en.wikipedia.org/wiki/Theory_of_multiple_intelligences"),

    # ── 3. 에듀테크 (EdTech) ──
    ("💻 [교육공학] Educational Technology 개요 (Wikipedia)", "https://en.wikipedia.org/wiki/Educational_technology"),
    ("💻 [교육공학] E-Learning 개요 (Wikipedia)", "https://en.wikipedia.org/wiki/E-learning_(theory)"),
    ("💻 [교육공학] 블렌디드 러닝 (Blended Learning)", "https://en.wikipedia.org/wiki/Blended_learning"),
    ("💻 [교육공학] 플립러닝 (Flipped Classroom)", "https://en.wikipedia.org/wiki/Flipped_classroom"),
    ("💻 [교육공학] MOOC (대규모 공개 온라인 강좌)", "https://en.wikipedia.org/wiki/Massive_open_online_course"),
    ("💻 [교육공학] 학습관리시스템 LMS (Wikipedia)", "https://en.wikipedia.org/wiki/Learning_management_system"),
    ("💻 [교육공학] 적응형 학습 (Adaptive Learning)", "https://en.wikipedia.org/wiki/Adaptive_learning"),
    ("💻 [교육공학] 마이크로러닝 (Microlearning)", "https://en.wikipedia.org/wiki/Microlearning"),
    ("💻 [교육공학] 모바일 러닝 (M-Learning)", "https://en.wikipedia.org/wiki/M-learning"),
    ("💻 [교육공학] xAPI / Tin Can API 표준", "https://en.wikipedia.org/wiki/Experience_API"),
    ("💻 [교육공학] SCORM 표준 (Wikipedia)", "https://en.wikipedia.org/wiki/Sharable_Content_Object_Reference_Model"),
    ("💻 [교육공학] IMS Learning Tools Interoperability (LTI)", "https://en.wikipedia.org/wiki/Learning_Tools_Interoperability"),

    # ── 4. 교육평가 (Assessment & Evaluation) ──
    ("📝 [교육공학] 형성평가 (Formative Assessment)", "https://en.wikipedia.org/wiki/Formative_assessment"),
    ("📝 [교육공학] 총괄평가 (Summative Assessment)", "https://en.wikipedia.org/wiki/Summative_assessment"),
    ("📝 [교육공학] 루브릭 (Rubric - 평가기준표)", "https://en.wikipedia.org/wiki/Rubric_(academic)"),
    ("📝 [교육공학] 수행평가 (Authentic Assessment)", "https://en.wikipedia.org/wiki/Authentic_assessment"),
    ("📝 [교육공학] 포트폴리오 평가 (Portfolio Assessment)", "https://en.wikipedia.org/wiki/Electronic_portfolio"),
    ("📝 [교육공학] 컴퓨터 기반 평가 (Computer-based Testing)", "https://en.wikipedia.org/wiki/Computer-based_testing"),

    # ── 5. UDL (보편적 학습 설계) ──
    ("♿ [교육공학] UDL 보편적 학습 설계 (Wikipedia)", "https://en.wikipedia.org/wiki/Universal_Design_for_Learning"),
    ("♿ [교육공학] UDL Guidelines 공식 가이드", "https://udlguidelines.cast.org/"),

    # ── 6. 학습분석 (Learning Analytics) ──
    ("📊 [교육공학] Learning Analytics 개요 (Wikipedia)", "https://en.wikipedia.org/wiki/Learning_analytics"),
    ("📊 [교육공학] Educational Data Mining (Wikipedia)", "https://en.wikipedia.org/wiki/Educational_data_mining"),

    # ── 7. 게이미피케이션 (Gamification) ──
    ("🎮 [교육공학] 게이미피케이션 (Gamification)", "https://en.wikipedia.org/wiki/Gamification_of_learning"),
    ("🎮 [교육공학] 게임 기반 학습 (Game-based Learning)", "https://en.wikipedia.org/wiki/Educational_game"),
    ("🎮 [교육공학] 시뮬레이션 기반 학습 (Simulation Learning)", "https://en.wikipedia.org/wiki/Simulation-based_learning"),

    # ── 8. AI in Education ──
    ("🤖 [교육공학] AI in Education 개요 (Wikipedia)", "https://en.wikipedia.org/wiki/Artificial_intelligence_in_education"),
    ("🤖 [교육공학] Intelligent Tutoring Systems", "https://en.wikipedia.org/wiki/Intelligent_tutoring_system"),
    ("🤖 [교육공학] 챗봇 in Education (Wikipedia)", "https://en.wikipedia.org/wiki/Chatbot"),
    ("🤖 [교육공학] 자연어처리 NLP in Education", "https://en.wikipedia.org/wiki/Natural_language_processing"),
    ("🤖 [교육공학] 학습추천시스템 (Recommender System)", "https://en.wikipedia.org/wiki/Recommender_system"),

    # ── 9. OER (Open Educational Resources) ──
    ("📖 [교육공학] OER 개방교육자원 (Wikipedia)", "https://en.wikipedia.org/wiki/Open_educational_resources"),
    ("📖 [교육공학] Creative Commons 라이선스", "https://en.wikipedia.org/wiki/Creative_Commons_license"),
    ("📖 [교육공학] Open Pedagogy (개방형 교수법)", "https://en.wikipedia.org/wiki/Open_pedagogy"),

    # ── 10. 교수학습방법 (Teaching Methods) ──
    ("🏫 [교육공학] 문제중심학습 PBL (Problem-based Learning)", "https://en.wikipedia.org/wiki/Problem-based_learning"),
    ("🏫 [교육공학] 프로젝트 기반 학습 (Project-based Learning)", "https://en.wikipedia.org/wiki/Project-based_learning"),
    ("🏫 [교육공학] 협동학습 (Cooperative Learning)", "https://en.wikipedia.org/wiki/Cooperative_learning"),
    ("🏫 [교육공학] 탐구학습 (Inquiry-based Learning)", "https://en.wikipedia.org/wiki/Inquiry-based_learning"),
    ("🏫 [교육공학] 스캐폴딩 (Scaffolding)", "https://en.wikipedia.org/wiki/Instructional_scaffolding"),
    ("🏫 [교육공학] 동료학습 (Peer Learning)", "https://en.wikipedia.org/wiki/Peer_learning"),
    ("🏫 [교육공학] 거꾸로 교실 + 능동학습 (Active Learning)", "https://en.wikipedia.org/wiki/Active_learning"),
    ("🏫 [교육공학] 차별화 수업 (Differentiated Instruction)", "https://en.wikipedia.org/wiki/Differentiated_instruction"),

    # ── 11. 교육공학 한국어 자료 (나무위키/한국교육학술정보원 등) ──
    ("🇰🇷 [교육공학] 교육공학 개요 (한국어 Wikipedia)", "https://ko.wikipedia.org/wiki/%EA%B5%90%EC%9C%A1%EA%B3%B5%ED%95%99"),
    ("🇰🇷 [교육공학] 구성주의 학습이론 (한국어)", "https://ko.wikipedia.org/wiki/%EA%B5%AC%EC%84%B1%EC%A3%BC%EC%9D%98_(%EA%B5%90%EC%9C%A1%ED%95%99)"),
    ("🇰🇷 [교육공학] 블렌디드 러닝 (한국어)", "https://ko.wikipedia.org/wiki/%EB%B8%94%EB%A0%8C%EB%94%94%EB%93%9C_%EB%9F%AC%EB%8B%9D"),
    ("🇰🇷 [교육공학] 이러닝 (한국어)", "https://ko.wikipedia.org/wiki/%EC%9D%B4%EB%9F%AC%EB%8B%9D"),
    ("🇰🇷 [교육공학] 플립러닝 거꾸로 교실 (한국어)", "https://ko.wikipedia.org/wiki/%EA%B1%B0%EA%BE%B8%EB%A1%9C_%EA%B5%90%EC%8B%A4"),
    ("🇰🇷 [교육공학] MOOC 무크 (한국어)", "https://ko.wikipedia.org/wiki/%EB%AC%B4%ED%81%AC"),
    ("🇰🇷 [교육공학] 행동주의 (한국어)", "https://ko.wikipedia.org/wiki/%ED%96%89%EB%8F%99%EC%A3%BC%EC%9D%98"),
    ("🇰🇷 [교육공학] 블룸의 분류학 (한국어)", "https://ko.wikipedia.org/wiki/%EB%B8%94%EB%A3%B8%EC%9D%98_%EA%B5%90%EC%9C%A1%EB%AA%A9%ED%91%9C_%EB%B6%84%EB%A5%98%ED%95%99"),
    ("🇰🇷 [교육공학] 게이미피케이션 (한국어)", "https://ko.wikipedia.org/wiki/%EA%B2%8C%EC%9D%B4%EB%AF%B8%ED%94%BC%EC%BC%80%EC%9D%B4%EC%85%98"),
    ("🇰🇷 [교육공학] 인공지능과 교육 (한국어)", "https://ko.wikipedia.org/wiki/%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5"),

    # ── 12. 멀티미디어 학습 (Multimedia Learning) ──
    ("🎬 [교육공학] 멀티미디어 학습이론 (Mayer)", "https://en.wikipedia.org/wiki/Multimedia_learning"),
    ("🎬 [교육공학] 인지부하이론 (Cognitive Load Theory)", "https://en.wikipedia.org/wiki/Cognitive_load"),
    ("🎬 [교육공학] 이중코딩이론 (Dual Coding Theory)", "https://en.wikipedia.org/wiki/Dual-coding_theory"),
    ("🎬 [교육공학] 간격 반복 학습 (Spaced Repetition)", "https://en.wikipedia.org/wiki/Spaced_repetition"),
    ("🎬 [교육공학] 정교화 이론 (Elaboration Theory)", "https://en.wikipedia.org/wiki/Elaboration_theory"),
]


# ═══════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════
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
    print(f" 🎓 교육공학(Educational Technology) 학습 자료 시드")
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
    print(f" 📊 교육공학 시드 결과 보고")
    print(f"{'='*60}")
    print(f"  신규 생성: {created_count}건")
    print(f"  이미 존재(건너뜀): {skipped_count}건")
    print(f"  크롤링 실패(LINK 대체): {failed_count}건")
    print(f"  총 LectureMaterial 수: {LectureMaterial.objects.count()}건")
    print(f"{'='*60}")
    print(f"\n⚠️  벡터화가 필요합니다:")
    print(f"  PYTHONUNBUFFERED=1 python vectorize_materials.py")
