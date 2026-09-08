"""
K-apt 모니터링 알림, 카카오톡 텍스트 생성 및 모바일 반응형 HTML 리포트 생성기
"""

import os
import shutil
import subprocess
import webbrowser
import time

def send_windows_notification(title, message):
    """
    PowerShell을 활용하여 Windows 작업표시줄 토스트 팝업 알림을 띄웁니다.
    """
    clean_title = title.replace('"', '\"').replace("'", "")
    clean_msg = message.replace('"', '\"').replace("'", "").replace("\n", "  ")

    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
    $textNodes = $xml.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($xml.CreateTextNode("{clean_title}")) > $null
    $textNodes.Item(1).AppendChild($xml.CreateTextNode("{clean_msg}")) > $null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("K-apt 모니터링").Show($toast)
    """

    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=5)
    except Exception:
        pass

def copy_to_clipboard(text):
    """클립보드에 텍스트를 복사합니다."""
    try:
        cmd = f"Set-Clipboard -Value @'\n{text}\n'@"
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

def generate_kakao_text(bids_data, apt_name="리버파크자이"):
    """
    카카오톡 채팅방에 바로 붙여넣기(Ctrl+V)할 수 있는 가독성 높은 요약 텍스트를 생성합니다.
    """
    now_str = time.strftime("%Y-%m-%d %H:%M")
    total_count = len(bids_data)
    awarded_count = sum(1 for b in bids_data if b["bid"].get("status") == "낙찰")
    active_count = sum(1 for b in bids_data if b["bid"].get("type_code") == 1)

    lines = []
    lines.append(f"🏢 [{apt_name} 아파트 K-apt 입찰 브리핑]")
    lines.append(f"• 기준일시: {now_str}")
    lines.append(f"• 입찰현황: 총 {total_count}건 (진행공고 {active_count}건 / 낙찰완료 {awarded_count}건)")
    lines.append("─────────────────────")

    for idx, item in enumerate(bids_data, 1):
        b = item["bid"]
        a = item["analysis"]
        status = b.get("status", "-")
        title = b.get("title", "")
        amount = b.get("amount", "-")
        date = b.get("date", "")[:10]

        # 금액 표시 정리
        amt_str = f" | {amount}원" if amount != "-" else ""
        lines.append(f"{idx}. [{status}] {title}{amt_str} ({date})")

        if a.get("risk_tags"):
            lines.append(f"   ⚠️ 분석: {', '.join(a['risk_tags'])}")

    lines.append("─────────────────────")
    lines.append("📱 상세 투찰업체 및 계약조건은 첨부된 '리버파크자이_Kapt_모바일공유리포트.html' 파일을 카톡에서 바로 터치하시면 열람하실 수 있습니다.")

    return "\n".join(lines)

def generate_html_report(bids_data, output_path=None, auto_open=False, apt_name="리버파크자이"):
    """
    스마트폰 카카오톡 인앱 브라우저 및 PC 브라우저에서 모두 완벽하게 작동하는
    모바일 반응형 단일 HTML 대시보드 리포트를 생성합니다.
    """
    if not output_path:
        reports_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        output_path = os.path.join(reports_dir, "kapt_report_latest.html")

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    total_count = len(bids_data)
    active_count = sum(1 for b in bids_data if b["bid"].get("type_code") == 1)
    awarded_count = sum(1 for b in bids_data if b["bid"].get("status") == "낙찰")
    warning_count = sum(1 for b in bids_data if b["analysis"].get("risk_level") in ["WARNING", "CAUTION"])

    cards_html = []
    for idx, item in enumerate(bids_data):
        b = item["bid"]
        a = item["analysis"]
        d = b.get("detail")

        status = b.get("status", "-")
        status_badge_class = "badge-gray"
        if status == "낙찰":
            status_badge_class = "badge-blue"
        elif status == "진행중":
            status_badge_class = "badge-green"
        elif status in ["유찰", "취소", "낙찰무효"]:
            status_badge_class = "badge-red"

        risk_level = a.get("risk_level", "NORMAL")
        risk_badge = ""
        if risk_level == "WARNING":
            risk_badge = '<span class="badge badge-warning">⚠️ 주의 필요</span>'
        elif risk_level == "CAUTION":
            risk_badge = '<span class="badge badge-caution">🔍 검토 요망</span>'

        risk_tags_html = ""
        if a.get("risk_tags"):
            tags = "".join([f'<span class="tag-item">📌 {t}</span>' for t in a["risk_tags"]])
            risk_tags_html = f'<div class="risk-tags-box">{tags}</div>'

        # 참가업체 테이블 HTML
        participants_html = ""
        if d and d.get("participants"):
            rows_html = []
            for p in d["participants"]:
                win_icon = "🏆 낙찰" if p.get("is_winner") == "Y" else "-"
                row_cls = "winner-row" if p.get("is_winner") == "Y" else ""
                rows_html.append(f"""
                <tr class="{row_cls}">
                    <td>{p.get('rank')}</td>
                    <td><strong>{p.get('company')}</strong></td>
                    <td>{p.get('bid_amount')}원</td>
                    <td>{p.get('bid_time', '')[:10]}</td>
                    <td>{win_icon}</td>
                </tr>
                """)
            participants_html = f"""
            <div class="participants-box">
                <div class="participants-title">📊 응찰 업체 투찰 내역 (총 {len(d['participants'])}개사)</div>
                <div class="table-responsive">
                    <table class="sub-table">
                        <thead>
                            <tr>
                                <th>순위</th>
                                <th>회사명</th>
                                <th>투찰금액</th>
                                <th>투찰일</th>
                                <th>결과</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(rows_html)}
                        </tbody>
                    </table>
                </div>
            </div>
            """

        admin_info_html = ""
        if d and d.get("admin_info"):
            ad = d["admin_info"]
            admin_info_html = f"""
            <div class="meta-row">
                <span>🏢 관리업자: <strong>{ad.get('manager_company')}</strong></span>
                <span>📞 {ad.get('phone')}</span>
                <span>🏘️ {ad.get('dong_count')}개동 ({ad.get('household_count')}세대)</span>
            </div>
            """

        card_html = f"""
        <div class="bid-card filter-item" data-status="{status}" data-risk="{risk_level}">
            <div class="card-header" onclick="toggleCard({idx})">
                <div class="header-top">
                    <div class="badges-row">
                        <span class="badge {status_badge_class}">{status}</span>
                        <span class="badge badge-type">{b.get('type_name')}</span>
                        {risk_badge}
                    </div>
                    <div class="amount-tag">{b.get('amount') if b.get('amount') != '-' else '금액미정'}</div>
                </div>
                <div class="card-title">{b.get('title')}</div>
                <div class="card-hint">터치하여 상세 및 투찰업체 보기 ▼</div>
            </div>

            <div class="card-body" id="card-body-{idx}">
                <div class="meta-grid">
                    <div><strong>📅 공고/등록일:</strong> {b.get('date')}</div>
                    <div><strong>⏰ 마감일시:</strong> {b.get('limit_date')}</div>
                    <div><strong>⚖️ 낙찰방식:</strong> {b.get('method')}</div>
                    <div><strong>🏢 발주단지:</strong> {b.get('apt')}</div>
                </div>

                {admin_info_html}
                {risk_tags_html}
                {participants_html}
            </div>
        </div>
        """
        cards_html.append(card_html)

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{apt_name} K-apt 입찰 모니터링</title>
    <style>
        :root {{
            --bg: #F8FAFC;
            --header-bg: #0F172A;
            --primary: #2563EB;
            --kakao: #FEE500;
            --text-main: #0F172A;
            --text-muted: #64748B;
            --border: #E2E8F0;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}
        body {{
            background-color: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Segoe UI', Roboto, 'Malgun Gothic', sans-serif;
            line-height: 1.5;
            padding-bottom: 50px;
        }}
        
        /* 모바일 최적화 상단 헤더 */
        .app-header {{
            background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
            color: white;
            padding: 20px 16px 16px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 10px rgba(0,0,0,0.15);
        }}
        .header-brand {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
        }}
        .header-brand h1 {{
            font-size: 19px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .kakao-badge {{
            background-color: var(--kakao);
            color: #181600;
            font-size: 10px;
            font-weight: 800;
            padding: 3px 7px;
            border-radius: 12px;
        }}
        .header-desc {{
            font-size: 12px;
            color: #93C5FD;
        }}

        /* 카카오톡 공유 버튼 바 */
        .share-bar {{
            max-width: 680px;
            margin: 12px auto;
            padding: 0 14px;
            display: flex;
            gap: 8px;
        }}
        .btn-filter {{
            flex: 1;
            padding: 9px 4px;
            border: 1px solid var(--border);
            background: white;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            color: var(--text-muted);
            cursor: pointer;
            text-align: center;
        }}
        .btn-filter.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        /* 통계 그리드 */
        .stats-grid {{
            max-width: 680px;
            margin: 0 auto 12px;
            padding: 0 14px;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
        }}
        .stat-box {{
            background: white;
            border-radius: 8px;
            padding: 10px 8px;
            text-align: center;
            border: 1px solid var(--border);
        }}
        .stat-box.green {{ border-top: 3px solid #10B981; }}
        .stat-box.blue {{ border-top: 3px solid #2563EB; }}
        .stat-box.red {{ border-top: 3px solid #EF4444; }}
        .stat-box-num {{ font-size: 18px; font-weight: 800; color: #0F172A; }}
        .stat-box-lbl {{ font-size: 10.5px; color: var(--text-muted); font-weight: 600; }}

        /* 피드 리스트 */
        .feed-container {{
            max-width: 680px;
            margin: 0 auto;
            padding: 0 14px;
        }}
        
        .bid-card {{
            background: white;
            border-radius: 12px;
            margin-bottom: 12px;
            border: 1px solid var(--border);
            box-shadow: 0 2px 5px rgba(0,0,0,0.03);
            overflow: hidden;
        }}
        
        .card-header {{
            padding: 14px 15px;
            cursor: pointer;
            background: #FFFFFF;
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .badges-row {{
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }}
        .card-title {{
            font-size: 15px;
            font-weight: 700;
            color: #1E293B;
            line-height: 1.4;
            margin-bottom: 6px;
        }}
        .card-hint {{
            font-size: 11px;
            color: #94A3B8;
            text-align: right;
        }}

        .badge {{
            padding: 2.5px 6.5px;
            border-radius: 5px;
            font-size: 10.5px;
            font-weight: 700;
        }}
        .badge-blue {{ background: #DBEAFE; color: #1D4ED8; }}
        .badge-green {{ background: #D1FAE5; color: #047857; }}
        .badge-red {{ background: #FEE2E2; color: #B91C1C; }}
        .badge-gray {{ background: #F1F5F9; color: #475569; }}
        .badge-type {{ background: #EDE9FE; color: #6D28D9; }}
        .badge-warning {{ background: #EF4444; color: white; }}
        .badge-caution {{ background: #F59E0B; color: white; }}

        .amount-tag {{
            font-size: 13.5px;
            font-weight: 800;
            color: #2563EB;
            background: #EFF6FF;
            padding: 3px 8px;
            border-radius: 6px;
        }}

        /* 접이식 본문 */
        .card-body {{
            padding: 14px 15px;
            background: #F8FAFC;
            border-top: 1px dashed #E2E8F0;
            display: none;
        }}
        .card-body.open {{
            display: block;
        }}

        .meta-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 6px;
            font-size: 12.5px;
            color: #334155;
            margin-bottom: 10px;
        }}
        .meta-row {{
            font-size: 11.5px;
            color: #64748B;
            background: #FFFFFF;
            padding: 8px 10px;
            border-radius: 6px;
            margin-bottom: 10px;
            border: 1px solid #E2E8F0;
            display: flex;
            flex-direction: column;
            gap: 3px;
        }}
        
        .risk-tags-box {{
            background: #FFFBEB;
            border: 1px solid #FDE68A;
            padding: 8px 10px;
            border-radius: 6px;
            margin-bottom: 10px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .tag-item {{
            font-size: 11.5px;
            color: #B45309;
            font-weight: 700;
        }}

        /* 테이블 */
        .participants-box {{
            margin-top: 10px;
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 10px;
        }}
        .participants-title {{
            font-size: 12px;
            font-weight: 700;
            color: #475569;
            margin-bottom: 6px;
        }}
        .table-responsive {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        .sub-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11.5px;
            white-space: nowrap;
        }}
        .sub-table th {{
            background: #F1F5F9;
            color: #475569;
            padding: 5px 8px;
            font-weight: 600;
            text-align: left;
            border-bottom: 1px solid #CBD5E1;
        }}
        .sub-table td {{
            padding: 6px 8px;
            border-bottom: 1px solid #E2E8F0;
        }}
        .winner-row {{
            background: #ECFDF5;
            font-weight: 700;
            color: #065F46;
        }}

        .footer-note {{
            text-align: center;
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 20px;
            padding: 0 16px;
        }}
    </style>
</head>
<body>
    <div class="app-header">
        <div class="header-brand">
            <h1>🏢 {apt_name} 입찰 모니터링</h1>
            <span class="kakao-badge">카톡 공유용</span>
        </div>
        <div class="header-desc">K-apt 실시간 공시 데이터 | {now_str} 기준</div>
    </div>

    <!-- 필터 바 -->
    <div class="share-bar">
        <div class="btn-filter active" onclick="applyFilter('ALL', this)">전체 ({total_count})</div>
        <div class="btn-filter" onclick="applyFilter('낙찰', this)">낙찰완료 ({awarded_count})</div>
        <div class="btn-filter" onclick="applyFilter('WARN', this)">감사주의 ({warning_count})</div>
    </div>

    <!-- 통계 카드 -->
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-box-num">{total_count}</div>
            <div class="stat-box-lbl">전체</div>
        </div>
        <div class="stat-box green">
            <div class="stat-box-num">{active_count}</div>
            <div class="stat-box-lbl">진행공고</div>
        </div>
        <div class="stat-box blue">
            <div class="stat-box-num">{awarded_count}</div>
            <div class="stat-box-lbl">낙찰완료</div>
        </div>
        <div class="stat-box red">
            <div class="stat-box-num">{warning_count}</div>
            <div class="stat-box-lbl">감사주의</div>
        </div>
    </div>

    <!-- 입찰 리스트 피드 -->
    <div class="feed-container">
        {''.join(cards_html) if cards_html else '<p style="text-align:center; padding:30px; font-size:13px; color:#64748B;">수집된 입찰 공고가 없습니다.</p>'}
    </div>

    <div class="footer-note">
        카카오톡에서 전송받은 이 파일을 누르면 스마트폰에서 즉시 열립니다.<br>
        국토교통부 K-apt 데이터 기반 분석 리포트
    </div>

    <script>
        function toggleCard(id) {{
            var body = document.getElementById('card-body-' + id);
            if (body) {{
                body.classList.toggle('open');
            }}
        }}

        function applyFilter(type, el) {{
            document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
            el.classList.add('active');

            var cards = document.querySelectorAll('.filter-item');
            cards.forEach(c => {{
                if (type === 'ALL') {{
                    c.style.display = 'block';
                }} else if (type === '낙찰') {{
                    c.style.display = (c.getAttribute('data-status') === '낙찰') ? 'block' : 'none';
                }} else if (type === 'WARN') {{
                    var risk = c.getAttribute('data-risk');
                    c.style.display = (risk === 'WARNING' || risk === 'CAUTION') ? 'block' : 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""

    # 1. kapt_monitor 내부 reports 폴더에 저장
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 2. 사용자가 카카오톡으로 바로 끌어다 놓기 편하도록 상위 폴더(그래빗)에도 복사
    root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    kakao_mobile_file = os.path.join(root_folder, f"{apt_name}_Kapt_모바일공유리포트.html")
    try:
        shutil.copyfile(output_path, kakao_mobile_file)
    except Exception:
        pass

    if auto_open:
        try:
            os.startfile(os.path.abspath(output_path))
        except Exception:
            webbrowser.open(os.path.abspath(output_path))

    return output_path, kakao_mobile_file
