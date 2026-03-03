"""
DS-CNN 기반 키워드 스포팅 엔진 (Keyword Spotting Engine) - DEPRECATED

* 구조 변경 (Phase 3 Webhook 아키텍처 도입)으로 인해 
  더 이상 Django가 KWS 오디오 릴레이 및 추론을 직접 담당하지 않습니다.
* 라즈베리 파이(Edge)가 오디오를 다이렉트로 분석한 뒤, 
  `live_views.py`의 `kws-webhook` API를 호출합니다.
"""

class KWSEngine:
    @classmethod
    def get_instance(cls):
        return None
