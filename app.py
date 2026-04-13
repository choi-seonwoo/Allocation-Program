import os
import re
import requests
import csv
import io

from flask import Flask, render_template, jsonify, request
import anthropic

app = Flask(__name__)

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def parse_spreadsheet_id(url: str) -> str:
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        raise ValueError("유효한 Google Sheets URL이 아닙니다")
    return match.group(1)


def get_sheet_list(spreadsheet_id: str) -> list:
    """Google Sheets API로 시트 목록 반환 [{title, gid}, ...]"""
    api_url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
        f"?key={GOOGLE_API_KEY}&fields=sheets.properties(title,sheetId)"
    )
    resp = requests.get(api_url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": s["properties"]["title"], "gid": str(s["properties"]["sheetId"])}
        for s in data.get("sheets", [])
    ]


def fetch_csv(spreadsheet_id: str, gid: str):
    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )
    resp = requests.get(url, allow_redirects=True, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return list(csv.reader(io.StringIO(resp.text)))


def parse_spec(rows):
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/sheets")
def get_sheets():
    """URL로부터 시트 목록 반환"""
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL을 입력해주세요."}), 400
    if not GOOGLE_API_KEY:
        return jsonify({"error": "서버에 API 키가 설정되지 않았습니다."}), 500
    try:
        sid = parse_spreadsheet_id(url)
        sheets = get_sheet_list(sid)
        return jsonify({"spreadsheet_id": sid, "sheets": sheets})
    except requests.HTTPError as e:
        return jsonify({"error": f"시트 목록을 불러오지 못했습니다: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data")
def get_data():
    url      = request.args.get("url", "").strip()
    spec_gid = request.args.get("spec_gid", "").strip()
    dash_gid = request.args.get("dash_gid", "").strip()

    if not url or not spec_gid or not dash_gid:
        return jsonify({"error": "URL과 GID를 모두 입력해주세요."}), 400

    try:
        sid = parse_spreadsheet_id(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        spec_rows = fetch_csv(sid, spec_gid)
        dash_rows = fetch_csv(sid, dash_gid)
    except requests.HTTPError as e:
        return jsonify({"error": f"시트를 불러오지 못했습니다: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    members       = parse_spec(spec_rows)
    participation = parse_dashboard(dash_rows)

    if not members:
        return jsonify({"error": "스펙표에서 데이터를 찾지 못했습니다. GID를 확인해주세요."}), 400

    for m in members:
        m["총 참여율"] = participation.get(m["아이디"], "N/A")

    return jsonify(members)


@app.route("/api/ocr", methods=["POST"])
def ocr_image():
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}), 500

    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "이미지 데이터가 없습니다."}), 400

    img_data = data["image"]
    if "," in img_data:
        header, b64 = img_data.split(",", 1)
        media_type = header.split(":")[1].split(";")[0]
    else:
        b64 = img_data
        media_type = "image/png"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        "이 이미지에서 게임 닉네임이나 아이디(한글, 영문, 숫자 조합)를 모두 추출해주세요. "
                        "한 줄에 하나씩만 출력하고, 다른 설명·번호·기호는 쓰지 마세요."
                    ),
                },
            ],
        }],
    )

    raw = message.content[0].text
    names = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return jsonify({"names": names})


if __name__ == "__main__":
    app.run(debug=True)
