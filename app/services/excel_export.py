"""도매시세 그리드 Excel 내보내기."""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.services import market_query

GRID_HEADERS = [
    "카코드", "제조사", "모델", "세부모델", "등급", "세부등급", "차량명",
    "년식", "유종", "AWD", "사고여부", "주행구간",
    "시작가평균", "낙찰가평균", "전주대비(%)", "표본수", "주차",
]


def _style_headers(ws, headers):
    header_fill = PatternFill(start_color="C0392B", end_color="C0392B", fill_type="solid")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")


def _autosize(ws):
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 14


def export_grid_excel(args) -> io.BytesIO:
    rows = market_query.grid(
        maker=args.get("maker"),
        model_name=args.get("model_name"),
        mdetail_name=args.get("mdetail_name") or args.get("car_name"),
        grade_name=args.get("grade_name"),
        gdetail_name=args.get("gdetail_name"),
        car_year=args.get("car_year"),
        fuel=args.get("fuel"),
        awd=args.get("awd"),
        lang="ko",
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "도매시세"
    _style_headers(ws, GRID_HEADERS)
    for i, r in enumerate(rows, 2):
        values = [
            r.get("car_code"),
            r.get("maker"),
            r.get("model_name"),
            r.get("mdetail_name"),
            r.get("grade_name"),
            r.get("gdetail_name"),
            r.get("car_name"),
            r.get("car_year"),
            r.get("fuel"),
            r.get("awd"),
            r.get("is_accident_free"),
            r.get("km_bin"),
            r.get("start_avg"),
            r.get("hammer_avg"),
            r.get("wow_pct"),
            r.get("sample_count"),
            r.get("week_no") or "",
        ]
        for col, val in enumerate(values, 1):
            ws.cell(row=i, column=col, value=val)
    _autosize(ws)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
