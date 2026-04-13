import requests
import csv
import io

SPREADSHEET_ID = "1-OYnf8pjZCkrjlgPcSkvuFoLMzp-XcKSllUChj8kjl0"
SPEC_GID = "8154540"        # 스펙표 시트
DASHBOARD_GID = "1988878229"  # 대시보드 시트


def fetch_csv(spreadsheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    resp = requests.get(url, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return list(csv.reader(io.StringIO(resp.text)))


def parse_spec(rows):
    """
    스펙표 컬럼 구조:
      [0] A: 그룹 레이블 (빈 경우 多)
      [1] B: 클래스 (그룹 대표 행에만 표기, 이후 빈칸)
      [2] C: 투력 전체 순위
      [3] D: 아이디
      [4] E: 클래스 (중복)
      [5] F: 빈칸
      [6] G: (생략)
      [7] H: 등급
      [8] I: 투력
      ...
      [12] M: 총합
    """
    members = []
    current_class = ""
    for row in rows:
        if len(row) < 13:
            continue

        # B열 클래스: 값이 있으면 갱신, 없으면 이전 값 유지 (전진 채움)
        if row[1].strip():
            current_class = row[1].strip()

        아이디 = row[3].strip()
        등급_str = row[7].strip()
        투력_str = row[8].strip()
        총합_str = row[12].strip().replace(",", "")

        # 헤더·빈 행 제외: 아이디가 있고 등급·투력이 숫자인 행만
        if not 아이디 or not 등급_str.isdigit() or not 투력_str.isdigit():
            continue

        members.append({
            "아이디": 아이디,
            "등급": int(등급_str),
            "투력": int(투력_str),
            "클래스": current_class,
            "총합": int(총합_str) if 총합_str.isdigit() else 0,
        })
    return members


def parse_dashboard(rows):
    """
    대시보드 컬럼 구조:
      [1] B: 순번
      [2] C: 아이디
      [3] D: 클래스
      [9] J: 총 참여율
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


def main():
    print("스펙표 불러오는 중...")
    spec_rows = fetch_csv(SPREADSHEET_ID, SPEC_GID)

    print("대시보드 불러오는 중...")
    dash_rows = fetch_csv(SPREADSHEET_ID, DASHBOARD_GID)

    members = parse_spec(spec_rows)
    participation = parse_dashboard(dash_rows)

    # 총 참여율 병합
    for m in members:
        m["총 참여율"] = participation.get(m["아이디"], "N/A")

    # 콘솔 출력
    print(f"\n{'번호':>4}  {'아이디':<24} {'클래스':<14} {'등급':>4} {'투력':>8} {'총합':>10} {'총 참여율':>10}")
    print("-" * 82)
    for i, m in enumerate(members, 1):
        print(
            f"{i:>4}  {m['아이디']:<24} {m['클래스']:<14} "
            f"{m['등급']:>4} {m['투력']:>8,} {m['총합']:>10,} {m['총 참여율']:>10}"
        )
    print(f"\n총 {len(members)}명")

    # 참여율 없는 멤버 경고
    missing = [m["아이디"] for m in members if m["총 참여율"] == "N/A"]
    if missing:
        print(f"\n[경고] 대시보드에 없는 멤버: {', '.join(missing)}")

    # CSV 저장
    save = input("\nCSV로 저장하시겠습니까? (y/n): ").strip().lower()
    if save == "y":
        output_path = "members_result.csv"
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["아이디", "등급", "투력", "클래스", "총합", "총 참여율"])
            writer.writeheader()
            writer.writerows(members)
        print(f"저장 완료: {output_path}")

    return members


if __name__ == "__main__":
    main()
