import calendar
import html
import uuid
from datetime import date, datetime, timedelta

import gspread
import pandas as pd
import streamlit as st


DEFAULT_CATEGORIES = {
    "買い物": "🛍️",
    "交通": "🚃",
    "外食": "🍽️",
    "レジャー": "🎡",
    "贈り物": "🎁",
}
EXPENSE_HEADERS = ["record_id", "日付", "購入品", "金額", "カテゴリー", "登録日時"]

st.set_page_config(page_title="わたしの家計簿", page_icon="👛", layout="wide")


def period_for(anchor):
    """指定日を含む、28日から翌27日までの期間を返す。"""
    if anchor.day >= 28:
        start = anchor.replace(day=28)
    else:
        previous_month = anchor.replace(day=1) - timedelta(days=1)
        start = previous_month.replace(day=28)

    next_month = (start.replace(day=1) + timedelta(days=32)).replace(day=1)
    return start, next_month.replace(day=27)


def shift_period(start, months):
    """集計期間を指定月数だけ前後へ移動する。"""
    month_index = start.year * 12 + start.month - 1 + months
    shifted = date(month_index // 12, month_index % 12 + 1, 28)
    next_month = (shifted.replace(day=1) + timedelta(days=32)).replace(day=1)
    return shifted, next_month.replace(day=27)


def money(value):
    return f"¥{int(value):,}"


@st.cache_resource
def open_spreadsheet():
    credentials = dict(st.secrets["gcp_service_account"])
    client = gspread.service_account_from_dict(credentials)
    return client.open_by_url(st.secrets["spreadsheet_url"])


def worksheet_or_create(book, title, rows, cols):
    try:
        return book.worksheet(title)
    except gspread.WorksheetNotFound:
        return book.add_worksheet(title=title, rows=rows, cols=cols)


def initialize_sheets():
    book = open_spreadsheet()
    expenses = worksheet_or_create(book, "支出", 2000, 6)
    categories = worksheet_or_create(book, "カテゴリー", 100, 2)

    if not expenses.row_values(1):
        expenses.append_row(EXPENSE_HEADERS, value_input_option="USER_ENTERED")
        expenses.freeze(rows=1)

    if not categories.row_values(1):
        categories.append_row(["カテゴリー", "アイコン"])
        categories.append_rows(
            [[name, icon] for name, icon in DEFAULT_CATEGORIES.items()]
        )
        categories.freeze(rows=1)

    return expenses, categories


def load_categories(category_sheet):
    rows = category_sheet.get_all_records()
    result = {
        str(row.get("カテゴリー", "")).strip(): str(
            row.get("アイコン", "🏷️")
        ).strip()
        for row in rows
        if str(row.get("カテゴリー", "")).strip()
    }
    return result or DEFAULT_CATEGORIES.copy()


def load_expenses(expense_sheet, start, end):
    """対象期間内のすべての支出を新しい順で返す。"""
    rows = expense_sheet.get_all_records()
    if not rows:
        return pd.DataFrame(columns=EXPENSE_HEADERS)

    frame = pd.DataFrame(rows)
    for header in EXPENSE_HEADERS:
        if header not in frame.columns:
