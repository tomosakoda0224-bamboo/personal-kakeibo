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
            frame[header] = ""

    frame["日付"] = pd.to_datetime(frame["日付"], errors="coerce")
    frame["金額"] = (
        pd.to_numeric(frame["金額"], errors="coerce").fillna(0).astype(int)
    )
    frame = frame[
        frame["日付"].between(
            pd.Timestamp(start),
            pd.Timestamp(end),
            inclusive="both",
        )
    ].copy()
    frame["日付"] = frame["日付"].dt.strftime("%Y-%m-%d")
    return frame.sort_values(["日付", "登録日時"], ascending=False)


def delete_expense(expense_sheet, record_id):
    ids = expense_sheet.col_values(1)
    try:
        row_number = ids.index(record_id) + 1
    except ValueError:
        return False

    expense_sheet.delete_rows(row_number)
    return True


def render_calendar(start, end, daily_amounts):
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)

    cells = []

    for day in days:
        day_key = day.isoformat()
        has_expense = day_key in daily_amounts
        amount = int(daily_amounts.get(day_key, 0))
        if has_expense and amount >= 501:
            background = "#f9ded8"
        elif has_expense or day <= date.today():
            background = "#e4f4e8"
        else:
            background = "#f7f7f3"
        amount_html = (
            f"<strong>¥{amount:,}</strong>" if amount else "<span>—</span>"
        )
        today_class = " today" if day == date.today() else ""
        cells.append(
            f"""<div class="cal-cell{today_class}" style="background:{background}">
            <small>{day.month}/{day.day}</small>{amount_html}</div>"""
        )

    st.markdown(
        '<div class="calendar-grid">' + "".join(cells) + "</div>",
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"]{background:#f6f3ed}
    [data-testid="stHeader"]{background:transparent}
    .block-container{max-width:1100px;padding-top:2rem}
    h1,h2,h3{color:#24382f;letter-spacing:.02em}

    .hero{
      background:linear-gradient(135deg,#244b3b,#386c57);
      color:white;
      padding:28px 32px;
      border-radius:24px;
      margin-bottom:22px;
      box-shadow:0 12px 34px rgba(36,75,59,.16)
    }
    .hero h1{color:white;margin:0;font-size:2rem}
    .hero p{margin:.4rem 0 0;opacity:.8}

    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"]{
      background:#fff;
      border-radius:20px;
      border-color:#e7e1d8
    }

    div[data-testid="stMetric"]{
      background:white;
      padding:16px 20px;
      border-radius:18px;
      border:1px solid #e7e1d8
    }

    .calendar-grid{
      display:grid;
      grid-template-columns:repeat(7,minmax(75px,1fr));
      gap:8px
    }
    .cal-cell{
      min-height:74px;
      border-radius:13px;
      padding:10px;
      display:flex;
      flex-direction:column;
      justify-content:space-between;
      border:1px solid rgba(36,56,47,.06)
    }
    .cal-cell small{color:#52645c;font-weight:700}
    .cal-cell strong{color:#7c2f1f;font-size:.9rem}
    .cal-cell span{color:#aaa}
    .cal-cell.today{outline:3px solid #2f7257}

    .category-chip{
      display:inline-block;
      background:#edf3ef;
      color:#244b3b;
      border-radius:999px;
      padding:7px 12px;
      margin:2px;
      font-weight:700
    }

    [class*="st-key-expense-row-"]{
      border-bottom:1px solid #ddd8cf;
      min-height:64px;
      padding:.45rem 0 .55rem;
      margin:0;
      overflow:visible
    }
    [class*="st-key-expense-row-"] p{
      margin:.1rem 0;
      overflow:visible
    }

    [class*="st-key-period-nav-"] button{
      background:#2f7257 !important;
      color:#fff !important;
      border:1px solid #2f7257 !important;
      font-weight:700
    }
    [class*="st-key-period-nav-"] button:hover{
      background:#245a45 !important;
      border-color:#245a45 !important;
      color:#fff !important
    }
    [class*="st-key-period-nav-"] button p{
      color:#fff !important
    }

    @media(max-width:700px){
      .block-container{padding:1rem .4rem}
      .hero{padding:22px}

      .calendar-grid{
        grid-template-columns:repeat(7,minmax(0,1fr));
        gap:3px
      }
      .cal-cell{
        min-width:0;
        min-height:58px;
        padding:5px 1px;
        text-align:center;
        align-items:center
      }
      .cal-cell small{font-size:.65rem}
      .cal-cell strong{
        width:100%;
        font-size:.52rem;
        letter-spacing:-.04em;
        white-space:nowrap;
        overflow:visible
      }
      .cal-cell span{font-size:.6rem}

      div[data-testid="stMetricLabel"] p{
        font-size:.75rem !important;
        line-height:1.2
      }
      div[data-testid="stMetricValue"]{
        font-size:1.65rem !important;
        line-height:1.2
      }
      div[data-testid="stMetric"]{padding:12px 14px}

      [class*="st-key-expense-row-"]
      div[data-testid="stHorizontalBlock"]{
        display:grid !important;
        grid-template-columns:minmax(0,3fr) minmax(0,2fr) 50px;
        width:100% !important;
        max-width:100% !important;
        gap:4px;
        align-items:center;
        overflow:visible
      }

      [class*="st-key-expense-row-"]
      div[data-testid="column"]{
        width:100% !important;
        min-width:0 !important;
        flex:none !important
      }

      [class*="st-key-expense-row-"]
      div[data-testid="column"]:nth-child(2){
        text-align:right
      }

      [class*="st-key-expense-row-"] p{
        font-size:.72rem;
        line-height:1.25;
        margin:.1rem 0;
        overflow:visible
      }

      [class*="st-key-expense-row-"] .category-chip{
        padding:3px 6px;
        font-size:.65rem;
        line-height:1.2;
        white-space:nowrap
      }

      [class*="st-key-expense-row-"] button{
        min-height:36px;
        padding:3px 5px;
        font-size:.75rem;
        white-space:nowrap
      }
    }
    </style>

    <div class="hero">
      <h1>👛 わたしの家計簿</h1>
      <p>Googleスプレッドシートに保存。28日から翌27日までをひと目で。</p>
    </div>
    """,
    unsafe_allow_html=True,
)


try:
    expense_sheet, category_sheet = initialize_sheets()
    categories = load_categories(category_sheet)
except Exception as error:
    st.error("Googleスプレッドシートに接続できませんでした。")
    st.info(
        "StreamlitのSecrets設定と、スプレッドシートがサービスアカウントに"
        "「編集者」として共有されていることを確認してください。"
    )
    with st.expander("接続エラーの詳細"):
        st.code(str(error))
    st.stop()


entry_tab, report_tab = st.tabs(["✍️ 支出を入力", "📊 集計・カレンダー"])


with entry_tab:
    with st.form("expense_form", clear_on_submit=True, border=True):
        st.subheader("新しい支出")
        st.caption("日付は 年 → 月 → 日 の順に選択できます。")

        today = date.today()
        year_col, month_col, day_col = st.columns(3)

        with year_col:
            year = st.selectbox(
                "年",
                range(today.year - 10, today.year + 2),
                index=10,
            )

        with month_col:
            month = st.selectbox(
                "月",
                range(1, 13),
                index=today.month - 1,
            )

        max_day = calendar.monthrange(year, month)[1]
        with day_col:
            day = st.selectbox(
                "日",
                range(1, max_day + 1),
                index=min(today.day, max_day) - 1,
            )

        item = st.text_input("購入品", placeholder="例：日用品、ランチ")
        amount_text = st.text_input("金額（円）", placeholder="例：1280")
        labels = [f"{icon} {name}" for name, icon in categories.items()]
        selected_label = st.radio(
            "カテゴリー",
            labels,
            horizontal=True,
        )

        submitted = st.form_submit_button(
            "スプレッドシートに保存",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            cleaned = (
                amount_text.replace(",", "").replace("¥", "").strip()
            )

            if not item.strip():
                st.error("購入品を入力してください。")
            elif not cleaned.isdigit():
                st.error("金額は0以上の半角数字で入力してください。")
            else:
                category = selected_label.split(" ", 1)[1]
                expense_sheet.append_row(
                    [
                        str(uuid.uuid4()),
                        date(year, month, day).isoformat(),
                        item.strip(),
                        int(cleaned),
                        category,
                        datetime.now().isoformat(timespec="seconds"),
                    ],
                    value_input_option="USER_ENTERED",
                )
                st.success(
                    f"{item.strip()}（{money(cleaned)}）を保存しました。"
                )

    with st.expander("➕ カテゴリーを追加"):
        with st.form("category_form", clear_on_submit=True):
            icon_col, name_col = st.columns([1, 3])

            with icon_col:
                new_icon = st.text_input(
                    "アイコン",
                    value="🏷️",
                    max_chars=4,
                )

            with name_col:
                new_name = st.text_input(
                    "カテゴリー名",
                    placeholder="例：医療",
                )

            if st.form_submit_button("カテゴリーを追加"):
                if not new_name.strip():
                    st.error("カテゴリー名を入力してください。")
                elif new_name.strip() in categories:
                    st.warning(
                        "同じ名前のカテゴリーがすでにあります。"
                    )
                else:
                    category_sheet.append_row(
                        [
                            new_name.strip(),
                            new_icon.strip() or "🏷️",
                        ]
                    )
                    st.success(
                        f"{new_icon or '🏷️'} "
                        f"{new_name.strip()} を追加しました。"
                    )
                    st.rerun()


with report_tab:
    if "period_offset" not in st.session_state:
        st.session_state.period_offset = 0

    current_start, _ = period_for(date.today())
    start, end = shift_period(
        current_start,
        st.session_state.period_offset,
    )

    previous, title, following = st.columns([1, 4, 1])

    with previous:
        if st.button(
            "← 前期間",
            key="period-nav-prev",
            use_container_width=True,
        ):
            st.session_state.period_offset -= 1
            st.rerun()

    with title:
        st.markdown(
            f"<h3 style='text-align:center;margin:.35rem 0'>"
            f"{end.year}年{end.month}月</h3>",
            unsafe_allow_html=True,
        )

    with following:
        if st.button(
            "次期間 →",
            key="period-nav-next",
            use_container_width=True,
        ):
            st.session_state.period_offset += 1
            st.rerun()

    expenses = load_expenses(expense_sheet, start, end)
    total = int(expenses["金額"].sum()) if not expenses.empty else 0
    days_used = (
        int(expenses["日付"].nunique()) if not expenses.empty else 0
    )

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("期間の合計金額", money(total))
    metric2.metric("支出があった日", f"{days_used} 日")
    metric3.metric(
        "使用日の平均",
        money(round(total / days_used) if days_used else 0),
    )

    st.subheader("日ごとの使用金額")
    st.caption(
        "今日以前の500円以下・支出なしの日は薄緑、"
        "501円以上の日は薄赤で表示します。"
        "緑の枠は今日を表します。"
    )
    daily = (
        expenses.groupby("日付")["金額"].sum().to_dict()
        if not expenses.empty
        else {}
    )
    render_calendar(start, end, daily)

    if expenses.empty:
        st.info("この期間の支出はまだありません。")
    else:
        st.subheader("支出一覧")

        for _, row in expenses.iterrows():
            record_id = str(row["record_id"])

            with st.container(key=f"expense-row-{record_id}"):
                left, middle, right = st.columns([3, 2, 1])
                icon = categories.get(row["カテゴリー"], "🏷️")

                with left:
                    st.markdown(
                        f"**{html.escape(str(row['購入品']))}**  \n"
                        f"<span class='category-chip'>"
                        f"{icon} "
                        f"{html.escape(str(row['カテゴリー']))}"
                        f"</span>",
                        unsafe_allow_html=True,
                    )

                with middle:
                    st.markdown(
                        f"**{money(row['金額'])}**  \n"
                        f"{row['日付']}"
                    )

                with right:
                    if st.button(
                        "🗑️",
                        key=f"delete_{record_id}",
                        help="この支出を削除",
                    ):
                        if delete_expense(
                            expense_sheet,
                            record_id,
                        ):
                            st.rerun()
                        else:
                            st.warning(
                                "対象の記録が見つかりませんでした。"
                            )
