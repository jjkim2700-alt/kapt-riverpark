"""
GitHub Actions용 K-apt 자동 갱신 및 index.html 생성 스크립트
"""

import os
import sys
import time

from kapt_scraper import KaptScraper
from kapt_analyzer import analyze_bid
from kapt_notifier import generate_html_report
from kapt_db import detect_changes

def main():
    apt_name = "리버파크자이"
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] K-apt '{apt_name}' 최신 데이터 수집 시작...")

    scraper = KaptScraper()
    # 1. 공개경쟁입찰 수집
    public_bids = scraper.fetch_bids(apt_name=apt_name, days=365)
    print(f"-> 공개입찰: {len(public_bids)}건 수집 완료.")

    # 2. 수의계약 수집
    private_bids = scraper.fetch_private_contracts(apt_name=apt_name, days=365)
    print(f"-> 수의계약: {len(private_bids)}건 수집 완료.")

    # 상세 정보 조회
    for b in public_bids:
        if b.get("bid_num"):
            detail = scraper.fetch_bid_detail(b["bid_num"], b.get("type_code", 1))
            b["detail"] = detail

    for b in private_bids[:35]:
        if b.get("bid_num"):
            detail = scraper.fetch_private_contract_detail(b["bid_num"])
            b["detail"] = detail

    all_bids = sorted(public_bids + private_bids, key=lambda x: x.get("date", ""), reverse=True)
    print(f"-> 통합 총 {len(all_bids)}건 분석 진행...")

    analyzed_items = []
    for b in all_bids:
        analysis = analyze_bid(b, b.get("detail"))
        analyzed_items.append({
            "bid": b,
            "analysis": analysis
        })

    # 상태 변경 감지
    new_bids, updated_bids = detect_changes(all_bids)
    print(f"-> 신규 등록: {len(new_bids)}건, 상태 변경: {len(updated_bids)}건")

    # 웹사이트 메인 index.html 로 저장
    index_html_path = os.path.join(os.path.dirname(__file__), "index.html")
    generate_html_report(analyzed_items, output_path=index_html_path, auto_open=False, apt_name=apt_name)
    print(f"-> GitHub Pages용 'index.html' 생성 완료: {index_html_path}")

if __name__ == "__main__":
    main()
