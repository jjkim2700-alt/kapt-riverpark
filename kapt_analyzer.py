"""
K-apt 입찰 공고 지능형 요약 및 감사/위험 분석 모듈
"""

import re
from datetime import datetime

def analyze_bid(bid_item, detail_info=None):
    """
    개별 입찰 건에 대한 핵심 요약 및 감사 관점의 리스크(특허 알박기, 공고기간 위반 등)를 자동 분석합니다.
    """
    analysis = {
        "summary": "",
        "risk_level": "NORMAL",  # NORMAL, CAUTION, WARNING
        "risk_tags": [],
        "details_summary": []
    }

    title = bid_item.get("title", "")
    method = bid_item.get("method", "")
    status = bid_item.get("status", "")
    amount = bid_item.get("amount", "-")
    limit_date_str = bid_item.get("limit_date", "")
    reg_date_str = bid_item.get("date", "")

    # 1. 공고 기간 분석 (최소 10일 준수 여부)
    notice_days = None
    try:
        if limit_date_str and reg_date_str:
            d_start = datetime.strptime(reg_date_str[:10], "%Y-%m-%d")
            d_end = datetime.strptime(limit_date_str[:10], "%Y-%m-%d")
            notice_days = (d_end - d_start).days
            if "긴급" not in title and notice_days < 10:
                analysis["risk_tags"].append(f"공고기간 미달({notice_days}일, 법정10일)")
                analysis["risk_level"] = "WARNING"
            elif "긴급" in title and notice_days < 5:
                analysis["risk_tags"].append(f"긴급공고기간 미달({notice_days}일, 법정5일)")
                analysis["risk_level"] = "WARNING"
    except Exception:
        pass

    # 2. 특허 / 협약서 / 제한경쟁 알박기 키워드 분석
    restrictive_keywords = ["특허", "신기술", "협약서", "제조사", "지정", "제한경쟁"]
    found_keywords = [k for k in restrictive_keywords if k in title]
    
    if detail_info:
        basic = detail_info.get("basic_info", {})
        basic_text = " ".join(basic.values())
        for k in restrictive_keywords:
            if k in basic_text and k not in found_keywords:
                found_keywords.append(k)

    if found_keywords:
        analysis["risk_tags"].append(f"제한요건 감지({', '.join(found_keywords)})")
        if analysis["risk_level"] == "NORMAL":
            analysis["risk_level"] = "CAUTION"

    # 3. 상세 참여업체 및 투찰 패턴 분석 (개찰/낙찰 건)
    winner_company = None
    participants_count = 0
    if detail_info and detail_info.get("participants"):
        parts = detail_info["participants"]
        participants_count = len(parts)

        winner = next((p for p in parts if p.get("is_winner") == "Y"), None)
        if winner:
            winner_company = f"{winner.get('company')} ({winner.get('bid_amount')}원)"

        # 담합/경쟁도 체크
        if participants_count <= 2 and status == "낙찰":
            analysis["risk_tags"].append(f"경쟁률 저조({participants_count}개사 응찰)")
            if analysis["risk_level"] == "NORMAL":
                analysis["risk_level"] = "CAUTION"

        # 조기 투찰 vs 마감일 몰림 패턴 체크
        try:
            times = []
            for p in parts:
                t_str = p.get("bid_time", "")[:10]
                if t_str:
                    times.append((p.get("company"), t_str, p.get("is_winner") == "Y"))
            if times and len(times) >= 3:
                # 낙찰자만 며칠 전 미리 투찰하고 나머지는 마감일에 몰린 경우
                winner_t = next((t[1] for t in times if t[2]), None)
                other_ts = [t[1] for t in times if not t[2]]
                if winner_t and other_ts and all(ot > winner_t for ot in other_ts):
                    analysis["risk_tags"].append("사전 단독투찰 패턴(들러리 의심)")
                    analysis["risk_level"] = "WARNING"
        except Exception:
            pass

    # 4. 종합 브리핑 요약문 생성
    summary_lines = []
    summary_lines.append(f"[{bid_item.get('type_name')}] {title}")
    summary_lines.append(f"• 진행상태: {status} | 낙찰방식: {method}")
    if notice_days is not None:
        summary_lines.append(f"• 공고기간: {reg_date_str[:10]} ~ {limit_date_str[:10]} (총 {notice_days}일)")
    if amount and amount != "-":
        summary_lines.append(f"• 낙찰금액: {amount}원")
    if winner_company:
        summary_lines.append(f"• 최종낙찰사: {winner_company}")
    if participants_count > 0:
        summary_lines.append(f"• 응찰업체수: {participants_count}개사")

    if analysis["risk_tags"]:
        summary_lines.append(f"⚠️ [감사 분석 포인트]: {' / '.join(analysis['risk_tags'])}")

    analysis["summary"] = "\n".join(summary_lines)
    return analysis
