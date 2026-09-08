"""
K-apt(공동주택관리정보시스템) 입찰 공고 및 결과 전문 스크래퍼
"""

import sys
import os
import re
import ssl
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

class KaptScraper:
    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.k-apt.go.kr/'
        }
        self.csrf_token = None

    def _ensure_csrf_token(self):
        """K-apt 메인 또는 공고 페이지에서 CSRF 토큰을 획득합니다."""
        if self.csrf_token:
            return self.csrf_token

        url = 'https://www.k-apt.go.kr/bid/bidList.do?type=1'
        req = urllib.request.Request(url, headers=self.headers)
        with self.opener.open(req, timeout=10) as res:
            html = res.read().decode('utf-8', errors='ignore')

        m = re.search(r'name="_csrf"\s+content="([^"]+)"', html)
        if m:
            self.csrf_token = m.group(1)
        return self.csrf_token

    def fetch_bids(self, apt_name="리버파크자이", days=365):
        """
        지정 단지의 Type 1(공고), Type 2(개찰), Type 3(낙찰) 입찰 목록을 전수 수집합니다.
        """
        token = self._ensure_csrf_token()
        now = datetime.now()
        start_date = (now - timedelta(days=min(days, 360))).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        enc_apt = urllib.parse.quote(apt_name)
        all_bids = []

        type_meta = [
            (1, "입찰공고(진행중)"),
            (2, "개찰결과"),
            (3, "낙찰결과")
        ]

        for t_code, t_name in type_meta:
            url = (
                f"https://www.k-apt.go.kr/bid/bidList.do"
                f"?pageSelect=100&searchBidGb=bid_gb_1&bidTitle="
                f"&aptName={enc_apt}&searchDateGb=reg"
                f"&dateStart={start_date}&dateEnd={end_date}&dateArea=4"
                f"&pageNo=1&type={t_code}"
            )
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with self.opener.open(req, timeout=12) as res:
                    html = res.read().decode('utf-8', errors='ignore')

                soup = BeautifulSoup(html, 'html.parser')
                tbody = soup.find('tbody')
                if not tbody:
                    continue

                for tr in tbody.find_all('tr'):
                    tds = tr.find_all('td')
                    if len(tds) < 8:
                        continue

                    # goView 자바스크립트 함수에서 bidNum 추출
                    onclick = ""
                    for td in tds:
                        oc = td.get('onclick', '')
                        if 'goView' in oc:
                            onclick = oc
                            break
                    
                    bid_num = ""
                    m = re.search(r'goView\([\'"]([^\'"]+)[\'"]\)', onclick)
                    if m:
                        bid_num = m.group(1)

                    raw_title = tds[3].get_text(separator=' ', strip=True)
                    # 연속 공백 정리
                    clean_title = re.sub(r'\s+', ' ', raw_title)

                    bid_item = {
                        "seq": tds[0].get_text(strip=True),
                        "type_code": t_code,
                        "type_name": t_name,
                        "method": tds[2].get_text(strip=True),
                        "title": clean_title,
                        "limit_date": tds[4].get_text(strip=True),
                        "status": tds[5].get_text(strip=True),
                        "amount": tds[6].get_text(strip=True),
                        "apt": tds[7].get_text(strip=True),
                        "date": tds[8].get_text(strip=True),
                        "bid_num": bid_num,
                        "detail": None
                    }
                    all_bids.append(bid_item)

            except Exception as e:
                print(f"[경고] {t_name} 수집 중 오류: {e}")

        return all_bids

    def fetch_bid_detail(self, bid_num, type_code):
        """
        공고 상세 페이지(참여업체, 공고 전문, 관리소 정보 등)를 파싱합니다.
        """
        if not bid_num:
            return None

        token = self._ensure_csrf_token()
        detail_url = "https://www.k-apt.go.kr/bid/bidDetail.do"
        post_data = urllib.parse.urlencode({
            'bidNum': bid_num,
            'type': str(type_code),
            '_csrf': token
        }).encode('utf-8')

        req_headers = dict(self.headers)
        req_headers['X-CSRF-TOKEN'] = token
        req_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'

        try:
            req = urllib.request.Request(detail_url, data=post_data, headers=req_headers)
            with self.opener.open(req, timeout=12) as res:
                html = res.read().decode('utf-8', errors='ignore')

            soup = BeautifulSoup(html, 'html.parser')
            detail_info = {
                "participants": [],
                "basic_info": {},
                "admin_info": {},
                "result_reason": "",
                "files": []
            }

            tables = soup.find_all('table')
            for t in tables:
                rows = [[c.get_text(strip=True) for c in r.find_all(['th', 'td'])] for r in t.find_all('tr')]
                if not rows:
                    continue

                header_text = "".join([c for r in rows[:2] for c in r])

                # 1. 참여업체 테이블
                if "참여업체" in header_text or "응찰회사" in header_text:
                    for r in rows[2:]:
                        if len(r) >= 9 and r[0].isdigit():
                            detail_info["participants"].append({
                                "rank": r[0],
                                "company": r[1],
                                "biz_no": r[2],
                                "ceo": r[3],
                                "tel": r[4],
                                "bid_time": r[5],
                                "attend_briefing": r[6],
                                "doc_valid": r[7],
                                "bid_amount": r[8],
                                "is_winner": r[9] if len(r) > 9 else "",
                            })

                # 2. 결과 사유
                elif "낙찰/유찰/취소 사유" in header_text or "사유" in header_text:
                    for r in rows:
                        if len(r) >= 2 and r[0] in ["낙찰", "유찰", "취소", "낙찰무효"]:
                            detail_info["result_reason"] = f"[{r[0]}] {r[1]}"

                # 3. 관리사무소 정보
                elif "주택관리업자" in header_text or "관리사무소 주소" in header_text:
                    for r in rows:
                        if len(r) >= 6 and "주택관리업자" not in r[0]:
                            detail_info["admin_info"] = {
                                "manager_company": r[0],
                                "apt_name": r[1] if len(r) > 1 else "",
                                "address": r[2] if len(r) > 2 else "",
                                "phone": r[3] if len(r) > 3 else "",
                                "fax": r[4] if len(r) > 4 else "",
                                "dong_count": r[5] if len(r) > 5 else "",
                                "household_count": r[6] if len(r) > 6 else "",
                            }

                # 4. 입찰 기본 상세 정보
                elif "입찰번호" in header_text or "입찰방법" in header_text:
                    for r in rows:
                        for idx in range(0, len(r), 2):
                            if idx + 1 < len(r):
                                k = r[idx].strip()
                                v = r[idx+1].strip()
                                if k:
                                    detail_info["basic_info"][k] = v

            # 첨부파일 정보
            for a in soup.find_all('a'):
                href = a.get('href', '')
                if 'download' in href.lower() or 'file' in href.lower():
                    fname = a.get_text(strip=True)
                    if fname and len(fname) > 2:
                        detail_info["files"].append(fname)

            return detail_info

        except Exception as e:
            print(f"[경고] 상세 조회 오류 (bidNum: {bid_num}): {e}")
            return None

    def fetch_private_contracts(self, apt_name="리버파크자이", days=365):
        """
        K-apt에서 지정 단지의 수의계약 체결 및 결과 공개 목록을 수집합니다.
        """
        token = self._ensure_csrf_token()
        now = datetime.now()
        start_date = (now - timedelta(days=min(days, 360))).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        enc_apt = urllib.parse.quote(apt_name)
        url = (
            f"https://www.k-apt.go.kr/bid/privateContractList.do"
            f"?pageSelect=100&searchBidGb=bid_gb_1&bidTitle="
            f"&aptName={enc_apt}&searchDateGb=reg"
            f"&dateStart={start_date}&dateEnd={end_date}&dateArea=4"
            f"&pageNo=1"
        )
        private_bids = []
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with self.opener.open(req, timeout=12) as res:
                html = res.read().decode('utf-8', errors='ignore')

            soup = BeautifulSoup(html, 'html.parser')
            tbody = soup.find('tbody')
            if not tbody:
                return private_bids

            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 7:
                    continue

                onclick = ""
                for td in tds:
                    oc = td.get('onclick', '')
                    if 'goView' in oc:
                        onclick = oc
                        break

                pc_num = ""
                m = re.search(r'goView\([\'"]([^\'"]+)[\'"]\)', onclick)
                if m:
                    pc_num = m.group(1)

                raw_title = tds[3].get_text(separator=' ', strip=True)
                clean_title = re.sub(r'\s+', ' ', raw_title)
                apt_field = re.sub(r'\s+', ' ', tds[1].get_text(separator=' ', strip=True))

                bid_item = {
                    "seq": tds[0].get_text(strip=True),
                    "type_code": 4,
                    "type_name": "수의계약",
                    "method": "수의계약",
                    "title": clean_title,
                    "limit_date": tds[6].get_text(strip=True),  # 계약기간
                    "status": "수의계약",
                    "amount": tds[5].get_text(strip=True),
                    "apt": apt_field,
                    "date": tds[4].get_text(strip=True),  # 계약일
                    "company": tds[2].get_text(strip=True),  # 계약업체
                    "bid_num": pc_num,
                    "detail": None
                }
                private_bids.append(bid_item)

        except Exception as e:
            print(f"[경고] 수의계약 수집 중 오류: {e}")

        return private_bids

    def fetch_private_contract_detail(self, pc_num):
        """
        수의계약 상세 정보(체결사유, 업체상세, 공사분류 등)를 파싱합니다.
        """
        if not pc_num:
            return None

        token = self._ensure_csrf_token()
        detail_url = "https://www.k-apt.go.kr/bid/privateContractDetail.do"
        post_data = urllib.parse.urlencode({
            'pcNum': pc_num,
            '_csrf': token
        }).encode('utf-8')

        req_headers = dict(self.headers)
        req_headers['X-CSRF-TOKEN'] = token
        req_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'

        try:
            req = urllib.request.Request(detail_url, data=post_data, headers=req_headers)
            with self.opener.open(req, timeout=12) as res:
                html = res.read().decode('utf-8', errors='ignore')

            soup = BeautifulSoup(html, 'html.parser')
            detail_info = {
                "basic_info": {},
                "admin_info": {},
                "contract_reason": "",
                "participants": []
            }

            for t in soup.find_all('table'):
                rows = [[c.get_text(strip=True) for c in r.find_all(['th', 'td'])] for r in t.find_all('tr')]
                if not rows:
                    continue
                header_text = "".join([c for r in rows[:2] for c in r])

                if "수의계약 최신공개 정보" in header_text or "계약명" in header_text:
                    for r in rows:
                        if len(r) >= 2:
                            k = r[0].strip()
                            v = r[1].strip()
                            detail_info["basic_info"][k] = v
                            if "사유" in k and "변경사유" not in k:
                                detail_info["contract_reason"] = v

                elif "아파트명" in header_text or "관리사무소 주소" in header_text:
                    for r in rows:
                        if len(r) >= 6 and "아파트명" not in r[0]:
                            detail_info["admin_info"] = {
                                "apt_name": r[0],
                                "address": r[1],
                                "phone": r[2],
                                "fax": r[3],
                                "dong_count": r[4],
                                "household_count": r[5]
                            }

            # 수의계약 참여업체 형태로 포맷팅 (단일 계약업체)
            comp_name = detail_info["basic_info"].get("계약업체명", "")
            comp_ceo = detail_info["basic_info"].get("업체대표자명", "")
            comp_biz = detail_info["basic_info"].get("사업자등록번호", "")
            comp_amt = detail_info["basic_info"].get("계약금액", "")
            if comp_name:
                detail_info["participants"].append({
                    "rank": "1",
                    "company": comp_name,
                    "biz_no": comp_biz,
                    "ceo": comp_ceo,
                    "tel": detail_info["basic_info"].get("업체전화번호", ""),
                    "bid_time": detail_info["basic_info"].get("계약(예정)일", ""),
                    "attend_briefing": "-",
                    "doc_valid": "Y",
                    "bid_amount": comp_amt,
                    "is_winner": "Y"
                })

            return detail_info
        except Exception as e:
            print(f"[경고] 수의계약 상세 조회 오류 (pcNum: {pc_num}): {e}")
            return None

