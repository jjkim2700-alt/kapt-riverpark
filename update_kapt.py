"""
GitHub Actions용 K-apt 자동 갱신 및 index.html 생성 스크립트
"""

import os
import sys
import time

from kapt_scraper import KaptScraper
from kapt_analyzer import analyze_bid
from kapt_notifier import generate_html_report
from kapt_db import detect_changes, load_db

def main():
    apt_name = "리버파크자이"
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] K-apt '{apt_name}' 최신 데이터 수집 시작...")

    public_bids = []
    private_bids = []
    scraper = None

    try:
        scraper = KaptScraper()
        # 1. 공개경쟁입찰 수집
        public_bids = scraper.fetch_bids(apt_name=apt_name, days=365)
        print(f"-> 공개입찰: {len(public_bids)}건 수집 완료.")
    except Exception as e:
        print(f"[오류] 공개입찰 수집 중 예외 발생: {e}")

    try:
        if scraper is None:
            scraper = KaptScraper()
        # 2. 수의계약 수집
        private_bids = scraper.fetch_private_contracts(apt_name=apt_name, days=365)
        print(f"-> 수의계약: {len(private_bids)}건 수집 완료.")
    except Exception as e:
        print(f"[오류] 수의계약 수집 중 예외 발생: {e}")

    # [안전장치] 해외 네트워크 지연 등으로 수집 실패 시 기존 캐시 DB에서 자동 복원
    db = load_db()
    if not public_bids and db:
        cached_public = [v for v in db.values() if v.get("type_code") in [1, 2, 3]]
        if cached_public:
            print(f"-> [안전 보호] 캐시 DB에서 공개입찰 {len(cached_public)}건 자동 복원 완료.")
            public_bids = cached_public

    if not private_bids and db:
        cached_private = [v for v in db.values() if v.get("type_code") == 4]
        if cached_private:
            print(f"-> [안전 보호] 캐시 DB에서 수의계약 {len(cached_private)}건 자동 복원 완료.")
            private_bids = cached_private

    # 상세 정보 조회
    if scraper:
        try:
            for b in public_bids:
                if b.get("bid_num") and not b.get("detail"):
                    detail = scraper.fetch_bid_detail(b["bid_num"], b.get("type_code", 1))
                    if detail:
                        b["detail"] = detail

            for b in private_bids[:35]:
                if b.get("bid_num") and not b.get("detail"):
                    detail = scraper.fetch_private_contract_detail(b["bid_num"])
                    if detail:
                        b["detail"] = detail
        except Exception as e:
            print(f"[경고] 상세 정보 조회 중 오류(계속 진행): {e}")

    all_bids = sorted(public_bids + private_bids, key=lambda x: x.get("date", ""), reverse=True)
    print(f"-> 통합 총 {len(all_bids)}건 분석 진행...")

    analyzed_items = []
    for b in all_bids:
        try:
            analysis = analyze_bid(b, b.get("detail"))
        except Exception as ae:
            analysis = {"risk_level": "NORMAL", "risk_tags": [], "summary": f"기본 분석 완료 ({ae})"}
        analyzed_items.append({
            "bid": b,
            "analysis": analysis
        })

    # 상태 변경 감지
    try:
        new_bids, updated_bids = detect_changes(all_bids)
        print(f"-> 신규 등록: {len(new_bids)}건, 상태 변경: {len(updated_bids)}건")
    except Exception as de:
        print(f"[경고] detect_changes 오류: {de}")

    # 웹사이트 메인 index.html 로 저장
    index_html_path = os.path.join(os.path.dirname(__file__), "index.html")
    generate_html_report(analyzed_items, output_path=index_html_path, auto_open=False, apt_name=apt_name)
    print(f"-> GitHub Pages용 'index.html' 생성 완료: {index_html_path}")

if __name__ == "__main__":
    main()
