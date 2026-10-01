from __future__ import annotations

import base64
import zlib
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st
from neo4j.exceptions import Neo4jError
from PIL import Image, UnidentifiedImageError

import neo4j_service as db

COIN_IMAGE_DIR = Path(__file__).parent / "images" / "coins"
COIN_IMAGE_SIZE = 128
COIN_IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]
HOMEWORK_DIR = Path(__file__).parent / "homework"
REPO_URL = "https://github.com/tpp72/GrapDB1"
BRANCH = "main"
COLAB_URL = f"https://colab.research.google.com/github/tpp72/GrapDB1/blob/{BRANCH}"
OWNER_NAME = "ต่อพงศ์ เพียรพัฒน์กุล"
OWNER_ID = "664245010"
# Cards 1-3 list the files found in homework/<folder>; the card without a folder opens this app.
HUB_CARDS = [
    {
        "tag": "01 / CYPHER",
        "icon": "📚",
        "title": "แนะนำหนังสือและชมรมด้วย Neo4j",
        "desc": "เอกสาร PDF งาน Neo4j และ Graph Database: แนะนำหนังสือจากเพื่อนด้วย Traversal 1–2 hop และแนะนำชมรมจาก FRIEND_OF กับ MEMBER_OF",
        "folder": "01_club",
    },
    {
        "tag": "02 / GRAPH",
        "icon": "🕸️",
        "title": "Crypto Recommender ด้วย NetworkX",
        "desc": "สร้างกราฟผู้ใช้ 10 คนกับเหรียญ 8 เหรียญด้วย Python / NetworkX แล้วแนะนำเหรียญด้วยการเดินกราฟ 3 hop และหมวดหมู่สำหรับ Cold Start",
        "folder": "02_graph",
    },
    {
        "tag": "03 / NEO4J",
        "icon": "🔗",
        "title": "Crypto Recommender ด้วย Neo4j",
        "desc": "ย้ายข้อมูลชุดเดียวกันขึ้น Neo4j Aura เดินกราฟด้วย Cypher สร้าง FRIEND_OF จาก HOLDS และแนะนำเหรียญ 3 แบบ",
        "folder": "03_neo4j",
    },
    {
        "tag": "04 / APPLICATION",
        "icon": "🎯",
        "title": "ระบบแนะนำเหรียญ Crypto",
        "desc": "ทดลองระบบแนะนำ เลือกผู้ใช้ จัดการข้อมูลเหรียญ และสำรวจกราฟความสัมพันธ์ภายในแอป",
    },
]
NO_CATEGORY = "(ไม่มีหมวด)"
REL_TYPES = ["HOLDS", "IN_CATEGORY", "FRIEND_OF"]
NODE_COLORS = {"User": "#87CEFA", "Coin": "#FFD27F", "Category": "#B7E4C7"}

st.set_page_config(
    page_title="CryptoGraph Recommender",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
      .hero {
        padding: 1.4rem 1.6rem; border-radius: 22px;
        background: linear-gradient(120deg, #111827 0%, #1f2937 55%, #b45309 100%);
        color: white; margin-bottom: 1rem;
      }
      .hero h1 {margin:0; font-size:2.15rem;}
      .hero p {opacity:.88; margin:.35rem 0 0 0;}
      .coin-card {
        padding: 1rem 1.1rem; border: 1px solid rgba(128,128,128,.25);
        border-radius: 16px; margin-bottom: .75rem;
      }
      .score-pill {
        display:inline-block; padding:.2rem .55rem; border-radius:999px;
        background:#b45309; color:white; font-size:.8rem; font-weight:700;
      }
      .muted {opacity:.72; font-size:.9rem;}
      .coin-head {display:flex; align-items:center; gap:.7rem; margin:.55rem 0 .2rem 0;}
      .coin-head h3 {margin:0; padding:0;}
      .coin-head img, .coin-preview {width:44px; height:44px; border-radius:50%; object-fit:cover;}
    </style>
    """,
    unsafe_allow_html=True,
)


def require_connection() -> None:
    try:
        if not db.ping():
            raise RuntimeError("Neo4j did not return a healthy response")
    except Exception as exc:
        st.error("ยังเชื่อมต่อ Neo4j Aura ไม่สำเร็จ")
        st.markdown(
            "ใส่ค่าการเชื่อมต่อในไฟล์ `.streamlit/secrets.toml` (รันในเครื่อง) "
            "หรือที่ **App settings → Secrets** (Streamlit Community Cloud)"
        )
        st.code(
            '[neo4j]\nuri = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"\n'
            'username = "YOUR_USERNAME"\npassword = "YOUR_PASSWORD"',
            language="toml",
        )
        st.caption("ห้าม commit password ลง GitHub · ไม่ต้องใส่ database ก็ได้ ระบบจะใช้ home database ให้เอง")
        st.exception(exc)
        st.stop()
    try:
        db.ensure_schema()
    except Exception as exc:
        st.warning(f"สร้าง Unique Constraint ไม่สำเร็จ: {exc}")


def run_action(success: str, fn, *args) -> None:
    """Run a write, then rerun so every table shows the new state."""
    try:
        fn(*args)
    except ValueError as exc:
        st.error(str(exc))
        return
    except Neo4jError as exc:
        st.error(f"Neo4j ปฏิเสธคำสั่ง: {exc.message or exc}")
        return
    st.session_state["flash"] = success
    st.rerun()


def show_table(rows: list[dict], empty: str = "ยังไม่มีข้อมูล") -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    else:
        st.info(empty)


def user_selector(key: str, label: str = "เลือกผู้ใช้") -> str:
    names = [u["name"] for u in db.get_users()]
    if not names:
        st.info("ยังไม่มีผู้ใช้ กรุณาเพิ่มที่หน้า จัดการคน & เพื่อน หรือสร้างข้อมูลตัวอย่างที่หน้า ตั้งค่าข้อมูล")
        st.stop()
    return st.selectbox(label, names, key=key)


def category_options(categories: list[dict]) -> list[str]:
    return [NO_CATEGORY] + [k["name"] for k in categories]


def data_uri(content: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


@st.cache_data(show_spinner=False)
def default_coin_image(symbol: str) -> str:
    """Bundled icon from images/coins, or a generated badge carrying the symbol."""
    path = COIN_IMAGE_DIR / f"{symbol}.png"
    if symbol.isalnum() and path.is_file():
        return data_uri(path.read_bytes(), "image/png")
    label = symbol[:4]
    hue = zlib.crc32(symbol.encode()) % 360
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
        f'<circle cx="64" cy="64" r="64" fill="hsl({hue}, 55%, 50%)"/>'
        '<text x="64" y="64" dy=".35em" text-anchor="middle" font-family="sans-serif" font-weight="700" '
        f'font-size="{44 if len(label) <= 3 else 34}" fill="white">{escape(label)}</text>'
        "</svg>"
    )
    return data_uri(svg.encode(), "image/svg+xml")


def coin_image(symbol: str, image: str | None) -> str:
    """Uploaded picture stored in Neo4j first, then the bundled or generated default."""
    return image or default_coin_image(symbol)


def encode_upload(upload) -> str | None:
    """Shrink an uploaded picture to a small PNG data URI that fits in a node property."""
    if upload is None:
        return None
    try:
        image = Image.open(upload).convert("RGBA")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("ไฟล์รูปไม่ถูกต้อง กรุณาใช้ไฟล์ PNG, JPG หรือ WEBP") from exc
    image.thumbnail((COIN_IMAGE_SIZE, COIN_IMAGE_SIZE))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return data_uri(buffer.getvalue(), "image/png")


def create_coin(symbol: str, category: str | None, upload) -> None:
    db.create_coin(symbol, category, encode_upload(upload))


def update_coin(symbol: str, new_symbol: str, category: str | None, upload, clear_image: bool) -> None:
    db.update_coin(symbol, new_symbol, category, encode_upload(upload), clear_image)


def show_coin_table(rows: list[dict], symbol_key: str, empty: str) -> None:
    """Like show_table, with each coin's picture in the first column."""
    if not rows:
        st.info(empty)
        return
    rows = [
        {"image": coin_image(r[symbol_key], r["image"]), **{k: v for k, v in r.items() if k != "image"}}
        for r in rows
    ]
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        row_height=44,
        column_config={"image": st.column_config.ImageColumn("รูป", width="small")},
    )


def coin_card(rank: int, row: dict, score: str, reason: str) -> None:
    st.markdown(
        f"""
        <div class="coin-card">
          <span class="score-pill">#{rank} · {escape(score)}</span>
          <div class="coin-head"><img src="{coin_image(row['coin'], row['image'])}" alt=""><h3>{escape(row['coin'])}</h3></div>
          <div class="muted"><b>เหตุผล:</b> {escape(reason)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dot_quote(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_dot(rows: list[dict]) -> str:
    dot = [
        "digraph G {",
        'rankdir="LR";',
        'bgcolor="transparent";',
        'node [shape=box, style="rounded,filled", fontcolor="#111827"];',
        'edge [color="#94a3b8", fontcolor="#94a3b8", fontsize=10];',
    ]
    seen_nodes = set()
    for r in rows:
        ends = []
        for label, name in [(r["source_label"], r["source_name"]), (r["target_label"], r["target_name"])]:
            nid = dot_quote(f"{label}:{name}")
            ends.append(nid)
            if nid not in seen_nodes:
                color = NODE_COLORS.get(label, "#f8fafc")
                dot.append(f'{nid} [label={dot_quote(name)}, fillcolor="{color}"];')
                seen_nodes.add(nid)
        if r["relationship"] == "FRIEND_OF":
            # Symmetric and derived: no arrow head, and it must not push users into different ranks.
            weight = r["weight"] or 1
            attrs = f'label="{weight}", dir=none, style=dashed, constraint=false, penwidth={weight}'
        else:
            attrs = f'label="{r["relationship"]}"'
        dot.append(f"{ends[0]} -> {ends[1]} [{attrs}];")
    dot.append("}")
    return "\n".join(dot)


def page_recommendations() -> None:
    m = db.get_dashboard_metrics()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Users", m.get("users", 0))
    c2.metric("Coins", m.get("coins", 0))
    c3.metric("Categories", m.get("categories", 0))
    c4.metric("HOLDS", m.get("holds", 0))
    c5.metric("FRIEND_OF", m.get("friendships", 0))

    st.divider()
    st.subheader("✨ เหรียญที่แนะนำ")
    c1, c2 = st.columns(2)
    with c1:
        name = user_selector("rec_user")
    top_n = c2.slider("จำนวนคำแนะนำ", 1, 10, 3)
    st.caption("ตัวอย่างเชิงวิชาการเรื่องโครงสร้าง Graph เท่านั้น ไม่ใช่คำแนะนำการลงทุน")

    left, right = st.columns([1, 2])
    with left:
        st.markdown("**พอร์ตที่ถือ**")
        show_coin_table(db.get_user_holdings(name), "coin", "ผู้ใช้นี้ยังไม่ถือเหรียญใด")
    with right:
        st.markdown("**เพื่อน (ถือเหรียญเดียวกัน)**")
        show_table(db.get_friends(name), "ยังไม่มีใครถือเหรียญซ้ำกับผู้ใช้นี้")

    hop3, friends, category = st.tabs(["3 hop ผ่าน HOLDS", "2 hop ผ่าน FRIEND_OF", "ตามหมวดหมู่ (Cold Start)"])
    with hop3:
        st.caption("ผู้ใช้ → เหรียญที่ถือ → คนอื่นที่ถือเหมือนกัน → เหรียญใหม่ · score = จำนวนเส้นทางที่เดินไปถึง")
        rows = db.recommend_coins(name, top_n)
        if not rows:
            st.info("ยังไม่มีคำแนะนำสำหรับผู้ใช้นี้")
        for i, row in enumerate(rows, start=1):
            via = ", ".join(row["via_users"])
            coin_card(i, row, f"score {row['score']}", f"เดินไปถึงได้ {row['score']} เส้นทาง ผ่าน {via}")
    with friends:
        st.caption("ผู้ใช้ → เพื่อน → เหรียญที่เพื่อนถือ · weighted score = ผลรวม weight ของเพื่อน (เท่ากับคะแนนแบบ 3 hop)")
        rows = db.recommend_by_friends(name, top_n)
        if not rows:
            st.info("ผู้ใช้นี้ยังไม่มีเพื่อนที่ถือเหรียญอื่น")
        for i, row in enumerate(rows, start=1):
            names = ", ".join(row["from_friends"])
            coin_card(
                i,
                row,
                f"weighted {row['weighted_score']}",
                f"เพื่อน {row['friend_score']} คนถืออยู่ ({names})",
            )
    with category:
        st.caption("ผู้ใช้ → เหรียญที่ถือ → หมวดหมู่ → เหรียญอื่นในหมวดเดียวกัน · ไม่ต้องพึ่งผู้ใช้คนอื่น")
        rows = db.recommend_by_category(name, top_n)
        if not rows:
            st.info("ไม่มีเหรียญอื่นในหมวดเดียวกับที่ผู้ใช้นี้ถืออยู่")
        for i, row in enumerate(rows, start=1):
            cats = ", ".join(row["categories"])
            coin_card(i, row, f"score {row['score']}", f"อยู่หมวดเดียวกับเหรียญที่ถืออยู่ ({cats})")


def users_section() -> None:
    users = db.get_users()
    names = [u["name"] for u in users]
    symbols = [c["symbol"] for c in db.get_coins()]

    add, edit, delete = st.columns(3)
    with add, st.form("add_user", clear_on_submit=True):
        st.markdown("**เพิ่มผู้ใช้**")
        name = st.text_input("ชื่อผู้ใช้")
        coins = st.multiselect("เหรียญที่ถือ", symbols)
        if st.form_submit_button("เพิ่ม", type="primary"):
            run_action(f"เพิ่มผู้ใช้ {name.strip()} แล้ว", db.create_user, name, coins)
    with edit, st.container(border=True):
        st.markdown("**แก้ไขชื่อผู้ใช้**")
        if names:
            target = st.selectbox("ผู้ใช้", names, key="rename_user")
            new_name = st.text_input("ชื่อใหม่", value=target, key=f"rename_user_to_{target}")
            if st.button("บันทึก", key="rename_user_save"):
                run_action(f"เปลี่ยนชื่อ {target} เป็น {new_name.strip()} แล้ว", db.rename_user, target, new_name)
        else:
            st.caption("ยังไม่มีผู้ใช้")
    with delete, st.container(border=True):
        st.markdown("**ลบผู้ใช้**")
        if names:
            target = st.selectbox("ผู้ใช้", names, key="delete_user")
            sure = st.checkbox("ยืนยันการลบ (รวมความสัมพันธ์ทั้งหมดของผู้ใช้นี้)", key=f"delete_user_sure_{target}")
            if st.button("ลบ", key="delete_user_go", disabled=not sure):
                run_action(f"ลบผู้ใช้ {target} แล้ว", db.delete_user, target)
        else:
            st.caption("ยังไม่มีผู้ใช้")

    st.divider()
    show_table(users, "ยังไม่มีผู้ใช้")


def friends_section() -> None:
    st.info(
        "FRIEND_OF คำนวณจาก HOLDS อัตโนมัติทุกครั้งที่ข้อมูลเปลี่ยน (ถือเหรียญเดียวกันอย่างน้อย 1 เหรียญ = เพื่อน) "
        "จึงแก้ไขโดยตรงไม่ได้ · weight = จำนวนเหรียญที่ถือร่วมกัน"
    )
    if st.button("คำนวณ FRIEND_OF ใหม่จาก HOLDS", key="rebuild_friends"):
        run_action("คำนวณ FRIEND_OF ใหม่แล้ว", db.rebuild_friendships)
    st.caption("ใช้ปุ่มนี้เมื่อมีการแก้ข้อมูลจากภายนอกแอป เช่น Notebook หรือ Aura Query")
    show_table(db.get_friendships(), "ยังไม่มี FRIEND_OF")


def page_people() -> None:
    st.subheader("👥 จัดการคน & เพื่อน")
    user_tab, friend_tab = st.tabs(["ผู้ใช้ (User)", "เพื่อน (FRIEND_OF)"])
    with user_tab:
        users_section()
    with friend_tab:
        friends_section()


def holds_section(coins: list[dict]) -> None:
    users = db.get_users()
    if not users or not coins:
        st.info("ต้องมีทั้งผู้ใช้และเหรียญก่อน จึงจะสร้าง HOLDS ได้")
        return
    holdings = {u["name"]: u["coins"] for u in users}
    names = list(holdings)
    symbols = [c["symbol"] for c in coins]
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown("**แก้ไขพอร์ตของผู้ใช้** (เพิ่ม/ลบหลายเส้นพร้อมกัน)")
        user = st.selectbox("ผู้ใช้", names, key="holds_user")
        # The key carries the stored portfolio so the widget resets whenever the data changes.
        selected = st.multiselect(
            "เหรียญที่ถือ",
            symbols,
            default=holdings[user],
            key=f"holds_coins_{user}_{'-'.join(holdings[user])}",
        )
        if st.button("บันทึกพอร์ต", type="primary", key="holds_save"):
            run_action(f"บันทึกพอร์ตของ {user} แล้ว", db.set_user_holds, user, selected)
    with right:
        with st.container(border=True):
            st.markdown("**เพิ่ม HOLDS ทีละเส้น**")
            c1, c2 = st.columns(2)
            user = c1.selectbox("ผู้ใช้", names, key="add_hold_user")
            coin = c2.selectbox("เหรียญ", symbols, key="add_hold_coin")
            if st.button("เพิ่ม", key="add_hold_go"):
                if coin in holdings[user]:
                    st.warning(f"{user} ถือ {coin} อยู่แล้ว")
                else:
                    run_action(f"เพิ่ม ({user})-[:HOLDS]->({coin}) แล้ว", db.add_hold, user, coin)
        with st.container(border=True):
            st.markdown("**ลบ HOLDS ทีละเส้น**")
            edges = {f"{u} → {c}": (u, c) for u, held in holdings.items() for c in held}
            if edges:
                chosen = st.selectbox("ความสัมพันธ์", list(edges), key="remove_hold")
                if st.button("ลบ", key="remove_hold_go"):
                    run_action(f"ลบ HOLDS {chosen} แล้ว", db.remove_hold, *edges[chosen])
            else:
                st.caption("ยังไม่มี HOLDS")
    st.divider()
    show_table(db.get_holds(), "ยังไม่มี HOLDS")


def page_coins() -> None:
    st.subheader("🪙 จัดการเหรียญ & การถือ")
    coins = db.get_coins()
    categories = db.get_categories()
    options = category_options(categories)
    coin_tab, holds_tab, category_tab = st.tabs(["เหรียญ (Coin)", "การถือ (HOLDS)", "หมวดหมู่ (Category)"])

    with holds_tab:
        holds_section(coins)

    with coin_tab:
        add, edit, delete = st.columns(3)
        with add, st.form("add_coin", clear_on_submit=True):
            st.markdown("**เพิ่มเหรียญ**")
            symbol = st.text_input("สัญลักษณ์ (เช่น BTC)")
            category = st.selectbox("หมวดหมู่", options)
            upload = st.file_uploader("รูปเหรียญ (ไม่บังคับ)", type=COIN_IMAGE_TYPES)
            if st.form_submit_button("เพิ่ม", type="primary"):
                run_action(
                    f"เพิ่มเหรียญ {symbol.strip().upper()} แล้ว",
                    create_coin,
                    symbol,
                    None if category == NO_CATEGORY else category,
                    upload,
                )
        with edit, st.container(border=True):
            st.markdown("**แก้ไขเหรียญ**")
            if coins:
                current = {c["symbol"]: c["category"] or NO_CATEGORY for c in coins}
                images = {c["symbol"]: c["image"] for c in coins}
                target = st.selectbox("เหรียญ", list(current), key="edit_coin")
                stored = images[target]
                st.markdown(
                    f'<img class="coin-preview" src="{coin_image(target, stored)}" alt="">',
                    unsafe_allow_html=True,
                )
                new_symbol = st.text_input("สัญลักษณ์", value=target, key=f"edit_coin_symbol_{target}")
                category = st.selectbox(
                    "หมวดหมู่",
                    options,
                    index=options.index(current[target]),
                    key=f"edit_coin_category_{target}_{current[target]}",
                )
                # The key carries the stored picture so the uploader empties once a new one is saved.
                tag = zlib.crc32((stored or "").encode())
                upload = st.file_uploader(
                    "เปลี่ยนรูปเหรียญ",
                    type=COIN_IMAGE_TYPES,
                    key=f"edit_coin_image_{target}_{tag}",
                )
                clear_image = bool(stored) and st.checkbox(
                    "ลบรูปที่อัปโหลดไว้ (กลับไปใช้รูปเริ่มต้น)",
                    key=f"edit_coin_clear_{target}_{tag}",
                )
                if st.button("บันทึก", key="edit_coin_save"):
                    run_action(
                        f"แก้ไขเหรียญ {target} แล้ว",
                        update_coin,
                        target,
                        new_symbol,
                        None if category == NO_CATEGORY else category,
                        upload,
                        clear_image,
                    )
            else:
                st.caption("ยังไม่มีเหรียญ")
        with delete, st.container(border=True):
            st.markdown("**ลบเหรียญ**")
            if coins:
                target = st.selectbox("เหรียญ", [c["symbol"] for c in coins], key="delete_coin")
                sure = st.checkbox("ยืนยันการลบ (รวม HOLDS ของเหรียญนี้)", key=f"delete_coin_sure_{target}")
                if st.button("ลบ", key="delete_coin_go", disabled=not sure):
                    run_action(f"ลบเหรียญ {target} แล้ว", db.delete_coin, target)
            else:
                st.caption("ยังไม่มีเหรียญ")
        st.divider()
        show_coin_table(coins, "symbol", "ยังไม่มีเหรียญ")

    with category_tab:
        names = [k["name"] for k in categories]
        add, edit, delete = st.columns(3)
        with add, st.form("add_category", clear_on_submit=True):
            st.markdown("**เพิ่มหมวดหมู่**")
            name = st.text_input("ชื่อหมวดหมู่ (เช่น Layer1)")
            if st.form_submit_button("เพิ่ม", type="primary"):
                run_action(f"เพิ่มหมวดหมู่ {name.strip()} แล้ว", db.create_category, name)
        with edit, st.container(border=True):
            st.markdown("**แก้ไขชื่อหมวดหมู่**")
            if names:
                target = st.selectbox("หมวดหมู่", names, key="rename_category")
                new_name = st.text_input("ชื่อใหม่", value=target, key=f"rename_category_to_{target}")
                if st.button("บันทึก", key="rename_category_save"):
                    run_action(
                        f"เปลี่ยนชื่อหมวด {target} เป็น {new_name.strip()} แล้ว",
                        db.rename_category,
                        target,
                        new_name,
                    )
            else:
                st.caption("ยังไม่มีหมวดหมู่")
        with delete, st.container(border=True):
            st.markdown("**ลบหมวดหมู่**")
            if names:
                target = st.selectbox("หมวดหมู่", names, key="delete_category")
                sure = st.checkbox("ยืนยันการลบ (เหรียญในหมวดจะไม่มีหมวด)", key=f"delete_category_sure_{target}")
                if st.button("ลบ", key="delete_category_go", disabled=not sure):
                    run_action(f"ลบหมวดหมู่ {target} แล้ว", db.delete_category, target)
            else:
                st.caption("ยังไม่มีหมวดหมู่")
        st.divider()
        show_table(categories, "ยังไม่มีหมวดหมู่")


def page_graph() -> None:
    st.subheader("🕸️ กราฟความสัมพันธ์")
    c1, c2 = st.columns([1, 2])
    scope = c1.radio("ขอบเขต", ["ทั้งกราฟ", "รอบผู้ใช้หนึ่งคน"], horizontal=True)
    types = c2.multiselect("ความสัมพันธ์ที่แสดง", REL_TYPES, default=["HOLDS", "IN_CATEGORY"])
    name = user_selector("graph_user") if scope == "รอบผู้ใช้หนึ่งคน" else None
    rows = db.graph_edges(types, name)
    if not rows:
        st.info("ยังไม่มีความสัมพันธ์ให้แสดง")
        return
    st.caption("🟦 User · 🟧 Coin · 🟩 Category · เส้นประ = FRIEND_OF (ตัวเลข = weight)")
    st.graphviz_chart(build_dot(rows), width="stretch")
    with st.expander("ดูข้อมูล edge ที่ใช้วาดกราฟ"):
        show_table(rows)


def page_admin() -> None:
    st.subheader("⚙️ ตั้งค่าข้อมูล")
    info = db.connection_info()
    st.caption(f"เชื่อมต่ออยู่กับ `{info['uri']}` · database `{info['database']}`")
    st.markdown(
        """
        **Graph schema**
        - `(:User {name})-[:HOLDS]->(:Coin {symbol})`
        - `(:Coin)-[:IN_CATEGORY]->(:Category {name})`
        - `(:User)-[:FRIEND_OF {shared_coins, weight}]->(:User)` — คำนวณจาก `HOLDS`
        """
    )

    st.markdown("#### สร้างข้อมูลตัวอย่าง")
    st.caption("ผู้ใช้ 10 คน เหรียญ 8 เหรียญ และ HOLDS 26 เส้นจาก Notebook · ใช้ MERGE จึงกดซ้ำได้และไม่ลบข้อมูลเดิม")
    if st.button("สร้าง Constraint + Demo Data", type="primary"):
        with st.spinner("กำลังสร้างข้อมูล..."):
            run_action("สร้างข้อมูลตัวอย่างเรียบร้อยแล้ว", db.seed_demo_data)

    st.markdown("#### ล้างข้อมูล")
    st.warning("ลบ Node ทุกตัวที่เป็น User / Coin / Category พร้อมความสัมพันธ์ทั้งหมด และกู้คืนไม่ได้")
    sure = st.checkbox("ยืนยันว่าต้องการล้างข้อมูลทั้งหมด")
    if st.button("ล้างข้อมูล", disabled=not sure):
        run_action("ล้างข้อมูลเรียบร้อยแล้ว", db.clear_data)


PAGES = {
    "🪙 แนะนำเหรียญ": page_recommendations,
    "👥 จัดการคน & เพื่อน": page_people,
    "💰 จัดการเหรียญ & การถือ": page_coins,
    "🕸️ กราฟความสัมพันธ์": page_graph,
    "⚙️ ตั้งค่าข้อมูล": page_admin,
}


def open_app() -> None:
    st.query_params["view"] = "app"


def open_hub() -> None:
    st.query_params.clear()


def homework_files(folder: str, suffix: str) -> list[Path]:
    return sorted((HOMEWORK_DIR / folder).glob(f"*{suffix}"))


def hub_card(index: int, card: dict) -> None:
    with st.container(key=f"hub_card_{index}", height="stretch"):
        st.markdown(
            f"""
            <div class="hub-top"><span class="hub-icon">{card['icon']}</span><span class="hub-tag">{card['tag']}</span></div>
            <div class="hub-card-title">{card['title']}</div>
            <div class="hub-desc">{card['desc']}</div>
            """,
            unsafe_allow_html=True,
        )
        folder = card.get("folder")
        if folder is None:
            st.button("เข้าสู่ระบบแนะนำ →", key="hub_enter", on_click=open_app, width="stretch")
            st.link_button("ดูโค้ดโปรเจกต์บน GitHub ↗", REPO_URL, width="stretch")
            return

        # Buttons follow whatever is in the folder: drop a notebook or PDF in and it shows up here.
        path = f"homework/{folder}"
        notebooks = homework_files(folder, ".ipynb")
        pdfs = homework_files(folder, ".pdf")
        if notebooks:
            notebook_path = quote(f"{path}/{notebooks[0].name}")
            st.link_button("เปิดการบ้านใน Colab ↗", f"{COLAB_URL}/{notebook_path}", width="stretch")
        if pdfs:
            st.download_button(
                "ดาวน์โหลดเอกสาร PDF ↓",
                pdfs[0].read_bytes(),
                file_name=pdfs[0].name,
                mime="application/pdf",
                key=f"hub_pdf_{index}",
                width="stretch",
            )
        if not notebooks and not pdfs:
            st.button("ยังไม่มีไฟล์งาน", key=f"hub_empty_{index}", disabled=True, width="stretch")
        st.link_button("ดูไฟล์บน GitHub ↗", f"{REPO_URL}/tree/{BRANCH}/{path}", width="stretch")


def render_hub() -> None:
    st.markdown(
        """
        <style>
          .stApp {background: radial-gradient(1200px 520px at 50% 0%, #fde6ee 0%, #fff6f9 55%, #fffafc 100%);}
          [data-testid="stHeader"] {background: transparent;}
          .hub-head {text-align:center; color:#7a4a63; margin-bottom:1.4rem;}
          .hub-badge {
            display:inline-block; padding:.45rem 1.2rem; border:1px solid #efcfdc; border-radius:999px;
            background:#fff; font-size:.68rem; letter-spacing:.18em;
          }
          .hub-title {font-size:2.6rem; font-weight:700; color:#8a4a6b; margin:1rem 0 .7rem 0; line-height:1.3;}
          .hub-sub {font-size:.9rem; line-height:1.9;}
          [class*="st-key-hub_card_"] {
            background:#fffdfe; border:1px solid #f3dce5; border-radius:26px;
            padding:1.3rem 1.3rem 1.6rem 1.3rem; box-shadow:0 10px 30px rgba(214,150,178,.12);
          }
          .hub-top {display:flex; justify-content:space-between; align-items:center;}
          .hub-icon {
            display:inline-flex; width:2.75rem; height:2.75rem; align-items:center; justify-content:center;
            border-radius:12px; background:#fbe3ec; font-size:1.25rem;
          }
          .hub-tag {font-size:.7rem; letter-spacing:.08em; color:#a8748d;}
          .hub-card-title {font-size:1.25rem; font-weight:700; color:#8a4a6b; margin:1rem 0 0 0; min-height:3.4rem;}
          .hub-desc {font-size:.95rem; line-height:1.85; color:#8d6079; min-height:7.2rem;}
          [class*="st-key-hub_card_"] .stButton button,
          [class*="st-key-hub_card_"] .stDownloadButton button,
          [class*="st-key-hub_card_"] .stLinkButton a {
            background:#fbe6ee; color:#8a4a6b; border:1px solid #efcbd9; border-radius:14px; min-height:2.9rem;
          }
          [class*="st-key-hub_card_"] .stButton button:hover:enabled,
          [class*="st-key-hub_card_"] .stDownloadButton button:hover,
          [class*="st-key-hub_card_"] .stLinkButton a:hover {
            background:#f7d6e3; border-color:#e3a9c0; color:#7a3a5c;
          }
          [class*="st-key-hub_card_"] button p, [class*="st-key-hub_card_"] a p {color:inherit; font-size:.85rem;}
          .hub-foot {
            text-align:center; color:#a8748d; font-size:.75rem; line-height:2;
            border-top:1px solid #f1dbe4; margin-top:2.2rem; padding-top:1.2rem;
          }
        </style>
        <div class="hub-head">
          <span class="hub-badge">HOMEWORK · RECOMMENDATION HUB</span>
          <div class="hub-title">รวมการบ้านและระบบแนะนำ</div>
          <div class="hub-sub">หนังสือและชมรม · กราฟ Crypto · Neo4j<br>เลือกงานที่ต้องการเปิดดูได้จากการ์ดด้านล่าง</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for index, (column, card) in enumerate(zip(st.columns(len(HUB_CARDS)), HUB_CARDS), start=1):
        with column:
            hub_card(index, card)
    st.markdown(
        f'<div class="hub-foot">{OWNER_NAME} · รหัสนักศึกษา {OWNER_ID}<br>Crypto Recommendation Project</div>',
        unsafe_allow_html=True,
    )


def render_app() -> None:
    require_connection()

    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] {background: linear-gradient(180deg, #6f5b8a 0%, #b07f9c 100%);}
          [data-testid="stSidebar"] :is(h3, p, label, span) {color: #fff;}
          [data-testid="stSidebar"] .stButton button {
            background: linear-gradient(90deg, #d07fa6 0%, #a98bc0 100%); border: 0; border-radius: 999px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.button("← กลับหน้ารวมโปรเจกต์", on_click=open_hub, width="stretch")
        st.markdown(f"### ผู้จัดทำ: {OWNER_NAME}")
        st.markdown(f"**รหัส: {OWNER_ID}**")
        st.markdown("### เมนู")
        page = st.radio("เมนู", list(PAGES), label_visibility="collapsed")

    st.markdown(
        """
        <div class="hero">
          <h1>🪙 Crypto Coin Recommender</h1>
          <p>ระบบแนะนำเหรียญด้วย Graph Database: ผู้ใช้ที่พอร์ตคล้ายกันถือเหรียญอะไรอีกบ้าง</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    PAGES[page]()


if st.query_params.get("view") == "app":
    render_app()
else:
    render_hub()
