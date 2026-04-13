import re
from urllib.parse import urlparse, parse_qs

import requests
import csv
import io

from flask import Flask, render_template, jsonify, request

app = Flask(__name__)


# ── URL 파싱 ────────────────────────────────────────────────

def parse_sheets_url(url: str):
    """Google Sheets URL에서 spreadsheet_id 와 gid 추출"""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        raise ValueError("유효한 Google Sheets URL이 아닙니다")
    spreadsheet_id = match.group(1)

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if 'gid' in params:
        gid = params['gid'][0]
    else:
        frag = parse_qs(parsed.fragment)
        gid = frag.get('gid', ['0'])[0]

    return spreadsheet_id, gid


# ── 시트 데이터 ──────────────────────────────────────────────

def fetch_csv(spreadsheet_id: str, gid: str):
    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )
    resp = requests.get(url, allow_redirects=True, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return list(csv.reader(io.StringIO(resp.text)))


def parse_spec(rows):
    """
    스펙표 컬럼:
      [1] B: 클래스  [3] D: 아이디
      [7] H: 등급   [8] I: 투력   [12] M: 총합
    """
    members = []
    current_class = ""
    for row in rows:
        if len(row) < 13:
            continue
        if row[1].strip():
            current_class = row[1].strip()

        아이디   = row[3].strip()
        등급_str = row[7].strip()
        투력_str = row[8].strip()
        총합_str = row[12].strip().replace(",", "")

        if not 아이디 or not 등급_str.isdigit() or not 투력_str.isdigit():
            continue

        members.append({
            "아이디": 아이디,
            "클래스": current_class,
            "등급":   int(등급_str),
            "투력":   int(투력_str),
            "총합":   int(총합_str) if 총합_str.isdigit() else 0,
        })
    return members


def parse_dashboard(rows):
    """
    대시보드 컬럼:
      [2] C: 아이디   [9] J: 총 참여율
    """
    participation = {}
    for row in rows:
        if len(row) < 10:
            continue
        아이디 = row[2].strip()
        참여율 = row[9].strip()
        if not 아이디 or 아이디 == "아이디" or not 참여율:
            continue
        participation[아이디] = 참여율
    return participation


# ── 라우트 ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def get_data():
    spec_url  = request.args.get("spec_url", "").strip()
    dash_url  = request.args.get("dash_url", "").strip()

    if not spec_url or not dash_url:
        return jsonify({"error": "스펙표와 대시보드 URL을 모두 입력해주세요."}), 400

    try:
        spec_id, spec_gid = parse_sheets_url(spec_url)
        dash_id, dash_gid = parse_sheets_url(dash_url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        spec_rows = fetch_csv(spec_id, spec_gid)
        dash_rows = fetch_csv(dash_id, dash_gid)
    except requests.HTTPError as e:
        return jsonify({"error": f"시트를 불러오지 못했습니다: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    members      = parse_spec(spec_rows)
    participation = parse_dashboard(dash_rows)

    for m in members:
        m["총 참여율"] = participation.get(m["아이디"], "N/A")

    return jsonify(members)


if __name__ == "__main__":
    app.run(debug=True)
