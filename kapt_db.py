"""
K-apt 입찰 이력 및 상태 추적 로컬 데이터베이스 모듈
"""

import json
import os
import time

DB_FILE = os.path.join(os.path.dirname(__file__), "seen_bids.json")

def load_db():
    """저장된 입찰 목록과 상태를 로드합니다."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}

def save_db(db_data):
    """입찰 데이터를 JSON 파일에 저장합니다."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=2)

def detect_changes(current_bids):
    """
    현재 크롤링된 입찰 목록과 기존 DB를 비교하여:
    - new_bids: 최초 발견된 신규 공고/입찰
    - updated_bids: 상태(예: 공고 -> 개찰, 개찰 -> 낙찰)가 변경된 입찰
    - unchange_bids: 기존과 동일한 입찰
    을 구분하여 반환합니다.
    """
    db = load_db()
    new_bids = []
    updated_bids = []

    for bid in current_bids:
        bid_key = bid.get("bid_num") or f"{bid.get('apt')}_{bid.get('title')}_{bid.get('date')}"
        current_status = bid.get("status", "")
        current_type = bid.get("type_name", "")

        if bid_key not in db:
            # 완전 신규
            bid["first_seen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            new_bids.append(bid)
            db[bid_key] = bid
        else:
            old_item = db[bid_key]
            old_status = old_item.get("status", "")
            old_type = old_item.get("type_name", "")

            # 상태나 단계가 바뀐 경우
            if old_status != current_status or old_type != current_type:
                bid["previous_status"] = old_status
                bid["previous_type"] = old_type
                bid["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                updated_bids.append(bid)
                db[bid_key] = bid

    # 갱신 저장
    save_db(db)
    return new_bids, updated_bids
