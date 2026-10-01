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
# Stops 1-3 list the files found in homework/<folder>; the stop without a folder opens this app.
HUB_STOPS = [
    {
        "title": "แนะนำหนังสือและชมรมด้วย Neo4j",
        "desc": "เอกสาร PDF งาน Neo4j และ Graph Database: แนะนำหนังสือจากเพื่อนด้วย Traversal 1–2 hop และแนะนำชมรมจาก FRIEND_OF กับ MEMBER_OF",
        "folder": "01_club",
    },
    {
        "title": "Crypto Recommender ด้วย NetworkX",
        "desc": "สร้างกราฟผู้ใช้ 10 คนกับเหรียญ 8 เหรียญด้วย Python / NetworkX แล้วแนะนำเหรียญด้วยการเดินกราฟ 3 hop และหมวดหมู่สำหรับ Cold Start",
        "folder": "02_graph",
    },
    {
        "title": "Crypto Recommender ด้วย Neo4j",
        "desc": "ย้ายข้อมูลชุดเดียวกันขึ้น Neo4j Aura เดินกราฟด้วย Cypher สร้าง FRIEND_OF จาก HOLDS และแนะนำเหรียญ 3 แบบ",
        "folder": "03_neo4j",
    },
    {
        "title": "ระบบแนะนำเหรียญ Crypto",
        "desc": "แอปที่ต่อกับ Neo4j Aura จริง เลือกผู้ใช้แล้วดูว่าเหรียญที่แนะนำเดินมาถึงได้ทางไหน เพิ่ม ลบ แก้ไขข้อมูล และสำรวจกราฟความสัมพันธ์",
    },
]
NO_CATEGORY = "(ไม่มีหมวด)"
# One colour per relationship, used wherever a relationship is drawn. Mirrors DESIGN.md and config.toml.
INK = "#111A17"
PANEL = "#EEF2F0"
REL_COLORS = {"HOLDS": "#0A7A5A", "FRIEND_OF": "#5B3FA6", "IN_CATEGORY": "#B8500A"}
REL_LABELS = {"HOLDS": "HOLDS ถือเหรียญ", "FRIEND_OF": "FRIEND_OF ถือเหรียญเดียวกัน", "IN_CATEGORY": "IN_CATEGORY อยู่ในหมวด"}

st.set_page_config(
    page_title="ระบบแนะนำเหรียญ Crypto",
    page_icon=":material/hub:",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
      :root {
        --ink: #111A17; --muted: #51605A; --panel: #EEF2F0; --rule: #DCE3E0;
        --holds: #0A7A5A; --friend: #5B3FA6; --category: #B8500A;
      }
      ::selection {background: #BFE8D8; color: var(--ink);}
      .block-container {padding-top: 3.5rem; padding-bottom: 4rem; max-width: 1180px;}
      .lead {color: var(--muted); max-width: 68ch; margin: -.25rem 0 1rem 0;}
      .note {color: var(--muted); font-size: .9rem; max-width: 68ch; margin-bottom: .75rem;}

      /* Sidebar menu drawn as one line with a stop per page */
      [data-testid="stSidebar"] [role="radiogroup"] {gap: 0; position: relative; margin-top: 1rem; width: 100%;}
      [data-testid="stSidebar"] [role="radiogroup"] > div {width: 100%;}
      [data-testid="stSidebar"] [role="radiogroup"]::before {
        content: ""; position: absolute; left: calc(.925rem - 1.5px); top: 1.3rem; bottom: 1.3rem;
        width: 3px; background: #35493F;
      }
      [data-testid="stSidebar"] label[data-testid="stRadioOption"] {
        position: relative; width: 100%; margin: 0; padding: .6rem .75rem .6rem 2.25rem; border-radius: .375rem;
        transition: background-color .15s ease-out;
      }
      [data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child {display: none;}
      [data-testid="stSidebar"] label[data-testid="stRadioOption"]::before {
        content: ""; position: absolute; left: .5rem; top: 50%; width: .85rem; height: .85rem;
        transform: translateY(-50%); box-sizing: border-box; border-radius: 50%;
        background: #10201A; border: 3px solid #8FA39A;
      }
      [data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover {background: #1C2F28;}
      [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) {background: #1C2F28;}
      [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked)::before {
        background: #6FD9AE; border-color: #6FD9AE;
      }
      [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) p {font-weight: 600;}
      [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:focus-visible) {
        outline: 2px solid #6FD9AE; outline-offset: 2px;
      }
      .side-title {font-size: 1.2rem; font-weight: 700; line-height: 1.35; margin-bottom: .35rem;}
      .side-note {color: #B5C4BD; font-size: .85rem; line-height: 1.6;}
      .st-key-back_hub {margin-top: 1.25rem;}

      /* Holdings */
      .holdings {display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1.5rem;}
      .holding {
        display: flex; align-items: center; gap: .5rem; padding: .3rem .8rem .3rem .3rem;
        border: 1px solid var(--rule); border-radius: 999px; font-weight: 600;
      }
      .holding img {width: 1.75rem; height: 1.75rem; border-radius: 50%; object-fit: cover;}
      .holding small {color: var(--muted); font-weight: 400;}

      /* Ranked recommendations with the routes that reach each coin */
      .rec {
        display: grid; grid-template-columns: 2.25rem minmax(0, 1fr); column-gap: .75rem;
        padding: 1.4rem 0; border-top: 1px solid var(--rule);
      }
      .rec:first-child {border-top: 0; padding-top: .5rem;}
      .rec-rank {
        font-size: 1.35rem; font-weight: 700; line-height: 2.75rem; color: var(--muted);
        font-variant-numeric: tabular-nums;
      }
      .rec-head {display: flex; align-items: center; gap: .75rem;}
      .rec-head img {width: 2.75rem; height: 2.75rem; border-radius: 50%; object-fit: cover;}
      .rec-name {font-size: 1.35rem; font-weight: 700;}
      .rec-score {margin-left: auto; color: var(--muted); font-size: .9rem; white-space: nowrap;}
      .rec-score b {
        font-size: 1.35rem; color: var(--ink); margin-right: .35rem; font-variant-numeric: tabular-nums;
      }
      .routes {display: grid; gap: .5rem; margin-top: 1rem;}
      .route {display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); max-width: 32rem;}
      .stop {
        --in: transparent; --out: transparent;
        position: relative; padding-top: 1.75rem; text-align: center; font-size: .85rem; line-height: 1.35;
        overflow-wrap: anywhere;
      }
      .stop::before, .stop::after {
        content: ""; position: absolute; top: .75rem; width: 50%; height: 4px; margin-top: -2px;
      }
      .stop::before {left: 0; background: var(--in);}
      .stop::after {left: 50%; background: var(--out);}
      .stop .mark {
        position: absolute; z-index: 1; top: .75rem; left: 50%; transform: translate(-50%, -50%);
        box-sizing: border-box; width: 1rem; height: 1rem; border-radius: 50%;
        background: #fff; border: 3px solid var(--ink);
      }
      .stop.me .mark {background: var(--ink);}
      .stop.coin .mark {width: 1.5rem; height: 1.5rem; border: 0; object-fit: cover;}
      .stop.category .mark {border-radius: 2px;}
      .stop.end {font-weight: 700;}
      .stop small {display: block; color: var(--muted);}
      .in-HOLDS {--in: var(--holds);} .out-HOLDS {--out: var(--holds);}
      .in-FRIEND_OF {--in: var(--friend);} .out-FRIEND_OF {--out: var(--friend);}
      .in-IN_CATEGORY {--in: var(--category);} .out-IN_CATEGORY {--out: var(--category);}
      details.more {display: grid; gap: .5rem;}
      details.more summary {
        cursor: pointer; color: var(--holds); font-size: .9rem; font-weight: 600; padding: .25rem 0;
      }
      details.more[open] summary {margin-bottom: .5rem;}

      /* Relationship legend */
      .legend {display: flex; flex-wrap: wrap; gap: .4rem 1.5rem; font-size: .9rem; margin: .25rem 0 1rem 0;}
      .legend span {display: inline-flex; align-items: center; gap: .5rem;}
      .legend i {display: inline-block; width: 1.75rem; height: 4px;}
      .legend i.dashed {
        height: 0; border-top: 4px dashed var(--friend); background: none !important;
      }
      .coin-preview {width: 3rem; height: 3rem; border-radius: 50%; object-fit: cover; display: block; margin: .25rem 0;}
      .facts {display: flex; flex-wrap: wrap; gap: .25rem 2rem; margin: 0 0 1.5rem 0;}
      .facts span {color: var(--muted);}
      .facts b {color: var(--ink); font-variant-numeric: tabular-nums; margin-right: .3rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def page_header(title: str, lead: str) -> None:
    st.title(title, anchor=False)
    html(f'<div class="lead">{lead}</div>')


def require_connection() -> None:
    try:
        if not db.ping():
            raise RuntimeError("Neo4j did not return a healthy response")
    except Exception as exc:
        st.title("ยังเชื่อมต่อ Neo4j Aura ไม่ได้", anchor=False)
        st.markdown(
            "ใส่ค่าการเชื่อมต่อในไฟล์ `.streamlit/secrets.toml` เมื่อรันในเครื่อง "
            "หรือที่ **App settings → Secrets** บน Streamlit Community Cloud แล้วโหลดหน้านี้ใหม่"
        )
        st.code(
            '[neo4j]\nuri = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"\n'
            'username = "YOUR_USERNAME"\npassword = "YOUR_PASSWORD"',
            language="toml",
        )
        st.caption("ห้าม commit password ลง GitHub · ไม่ต้องใส่ database ก็ได้ ระบบจะใช้ home database ให้เอง")
        st.button("กลับหน้ารวมการบ้าน", icon=":material/arrow_back:", on_click=open_hub)
        with st.expander("รายละเอียดข้อผิดพลาด"):
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


def show_table(rows: list[dict], columns: dict[str, str], empty: str) -> None:
    """`columns` maps each field to the heading shown for it."""
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, column_config=columns)
    else:
        st.info(empty)


def user_selector(key: str, label: str = "ผู้ใช้") -> str:
    names = [u["name"] for u in db.get_users()]
    if not names:
        st.info("ยังไม่มีผู้ใช้ในฐานข้อมูล เพิ่มได้ที่เมนู จัดการคน & เพื่อน หรือสร้างข้อมูลตัวอย่างที่เมนู ตั้งค่าข้อมูล")
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


def show_coin_table(rows: list[dict], symbol_key: str, columns: dict[str, str], empty: str) -> None:
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
        height=len(rows) * 44 + 38,  # the automatic height assumes the default row height and clips the last row
        column_config={"image": st.column_config.ImageColumn("รูป", width="small"), **columns},
    )


def legend(types: list[str]) -> None:
    items = "".join(
        f'<span><i class="{"dashed" if rel == "FRIEND_OF" else ""}" style="background:{REL_COLORS[rel]}"></i>'
        f"{REL_LABELS[rel]}</span>"
        for rel in types
    )
    html(f'<div class="legend">{items}</div>')


def route_html(stops: list[dict], rels: list[str]) -> str:
    """One path through the graph: a marker per node, joined by segments coloured by relationship."""
    parts = []
    for i, stop in enumerate(stops):
        classes = ["stop", stop["kind"]]
        if i > 0:
            classes.append(f"in-{rels[i - 1]}")
        if i < len(rels):
            classes.append(f"out-{rels[i]}")
        else:
            classes.append("end")
        if stop.get("image"):
            mark = f'<img class="mark" src="{stop["image"]}" alt="">'
        else:
            mark = '<span class="mark"></span>'
        note = f"<small>{escape(stop['note'])}</small>" if stop.get("note") else ""
        parts.append(f'<div class="{" ".join(classes)}">{mark}{escape(stop["label"])}{note}</div>')
    return f'<div class="route" role="listitem">{"".join(parts)}</div>'


def recommendation_html(rank: int, row: dict, score: int, unit: str, routes: list[str]) -> str:
    shown, hidden = routes[:3], routes[3:]
    more = ""
    if hidden:
        more = f'<details class="more"><summary>ดูอีก {len(hidden)} เส้นทาง</summary>{"".join(hidden)}</details>'
    return (
        f'<div class="rec" role="listitem"><div class="rec-rank">{rank}</div><div>'
        f'<div class="rec-head"><img src="{coin_image(row["coin"], row["image"])}" alt="">'
        f'<span class="rec-name">{escape(row["coin"])}</span>'
        f'<span class="rec-score"><b>{score}</b>{unit}</span></div>'
        f'<div class="routes" role="list">{"".join(shown)}{more}</div>'
        "</div></div>"
    )


def show_recommendations(items: list[str], empty: str) -> None:
    if items:
        html(f'<div role="list">{"".join(items)}</div>')
    else:
        st.info(empty)


def dot_quote(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_dot(rows: list[dict]) -> str:
    node_styles = {
        "User": f'shape=box, style="rounded,filled", fillcolor="{INK}", fontcolor="white"',
        "Coin": 'shape=ellipse, style="filled", fillcolor="white"',
        "Category": f'shape=box, style="filled", fillcolor="{PANEL}"',
    }
    dot = [
        "digraph G {",
        'rankdir="TB"; bgcolor="transparent"; nodesep=0.3; ranksep=1.0;',
        f'node [fontname="Anuphan, sans-serif", fontsize=13, penwidth=2, color="{INK}", margin="0.16,0.08"];',
        'edge [fontname="Anuphan, sans-serif", fontsize=11, penwidth=2, arrowsize=0.7];',
    ]
    seen_nodes = set()
    for r in rows:
        ends = []
        for label, name in [(r["source_label"], r["source_name"]), (r["target_label"], r["target_name"])]:
            nid = dot_quote(f"{label}:{name}")
            ends.append(nid)
            if nid not in seen_nodes:
                dot.append(f"{nid} [label={dot_quote(name)}, {node_styles.get(label, '')}];")
                seen_nodes.add(nid)
        color = REL_COLORS[r["relationship"]]
        if r["relationship"] == "FRIEND_OF":
            # Symmetric and derived: no arrow head, and it must not push users into different ranks.
            attrs = f'label="{r["weight"] or 1}", fontcolor="{color}", dir=none, style=dashed, constraint=false'
        else:
            attrs = ""
        dot.append(f'{ends[0]} -> {ends[1]} [color="{color}", {attrs}];')
    dot.append("}")
    return "\n".join(dot)


def page_recommendations() -> None:
    page_header(
        "แนะนำเหรียญ",
        "เลือกผู้ใช้ แล้วดูว่าเหรียญที่ยังไม่ถือเหรียญไหนเดินมาถึงได้มากที่สุด ทุกเส้นทางที่นับเป็นคะแนนแสดงให้เห็นใต้เหรียญนั้น "
        "ตัวอย่างนี้ใช้สอนโครงสร้าง Graph เท่านั้น ไม่ใช่คำแนะนำการลงทุน",
    )
    c1, c2 = st.columns([2, 1], gap="large")
    with c1:
        name = user_selector("rec_user")
    top_n = c2.slider("จำนวนเหรียญที่แนะนำ", 1, 10, 3)

    images = {c["symbol"]: coin_image(c["symbol"], c["image"]) for c in db.get_coins()}
    me = {"kind": "me", "label": name}

    def coin_stop(symbol: str) -> dict:
        return {"kind": "coin", "label": symbol, "image": images.get(symbol) or default_coin_image(symbol)}

    side, main = st.columns([2, 3], gap="large")
    with side:
        st.subheader(f"พอร์ตของ {name}", anchor=False)
        holdings = db.get_user_holdings(name)
        if holdings:
            chips = "".join(
                f'<span class="holding"><img src="{coin_image(h["coin"], h["image"])}" alt="">{escape(h["coin"])}'
                f'<small>{escape(h["category"] or "ไม่มีหมวด")}</small></span>'
                for h in holdings
            )
            html(f'<div class="holdings">{chips}</div>')
        else:
            st.info(f"{name} ยังไม่ถือเหรียญใด จึงยังไม่มีเส้นทางให้เดิน เพิ่มเหรียญได้ที่เมนู จัดการเหรียญ & การถือ")
        st.subheader("เพื่อน", anchor=False)
        show_table(
            db.get_friends(name),
            {"friend": "ผู้ใช้", "shared_coins": "เหรียญที่ถือร่วมกัน", "weight": "weight"},
            "ยังไม่มีใครถือเหรียญซ้ำกับผู้ใช้นี้",
        )

    with main:
        hop3, friends, category = st.tabs(["เดิน 3 hop ผ่าน HOLDS", "เดิน 2 hop ผ่านเพื่อน", "ตามหมวดหมู่"])
        with hop3:
            html('<div class="note">คะแนน = จำนวนเส้นทางจากผู้ใช้ ผ่านเหรียญที่ถือและคนที่ถือเหรียญเดียวกัน ไปถึงเหรียญใหม่</div>')
            legend(["HOLDS"])
            items = []
            for rank, row in enumerate(db.recommend_coins(name, top_n), start=1):
                routes = [
                    route_html(
                        [me, coin_stop(p["coin"]), {"kind": "user", "label": p["user"]}, coin_stop(row["coin"])],
                        ["HOLDS", "HOLDS", "HOLDS"],
                    )
                    for p in row["paths"]
                ]
                items.append(recommendation_html(rank, row, row["score"], "เส้นทาง", routes))
            show_recommendations(items, "ยังไม่มีเส้นทางไปถึงเหรียญใหม่ เพราะยังไม่มีใครถือเหรียญซ้ำกับผู้ใช้นี้ ลองดูแท็บ ตามหมวดหมู่")
        with friends:
            html('<div class="note">คะแนน = ผลรวม weight ของเพื่อนที่ถือเหรียญนั้น ซึ่งเท่ากับคะแนนแบบ 3 hop เพราะ weight คือจำนวนเหรียญที่ถือร่วมกัน</div>')
            legend(["FRIEND_OF", "HOLDS"])
            items = []
            for rank, row in enumerate(db.recommend_by_friends(name, top_n), start=1):
                routes = [
                    route_html(
                        [
                            me,
                            {"kind": "user", "label": p["user"], "note": f"weight {p['weight']}"},
                            coin_stop(row["coin"]),
                        ],
                        ["FRIEND_OF", "HOLDS"],
                    )
                    for p in row["paths"]
                ]
                unit = f"จากเพื่อน {row['friend_score']} คน"
                items.append(recommendation_html(rank, row, row["weighted_score"], unit, routes))
            show_recommendations(items, "ผู้ใช้นี้ยังไม่มีเพื่อนที่ถือเหรียญอื่น ลองดูแท็บ ตามหมวดหมู่")
        with category:
            html('<div class="note">ไม่ต้องพึ่งผู้ใช้คนอื่น จึงแนะนำได้แม้เป็นผู้ใช้ใหม่ (Cold Start) คะแนน = จำนวนเส้นทางผ่านหมวดหมู่ของเหรียญที่ถือ</div>')
            legend(["HOLDS", "IN_CATEGORY"])
            items = []
            for rank, row in enumerate(db.recommend_by_category(name, top_n), start=1):
                routes = [
                    route_html(
                        [me, coin_stop(p["coin"]), {"kind": "category", "label": p["category"]}, coin_stop(row["coin"])],
                        ["HOLDS", "IN_CATEGORY", "IN_CATEGORY"],
                    )
                    for p in row["paths"]
                ]
                items.append(recommendation_html(rank, row, row["score"], "เส้นทาง", routes))
            show_recommendations(items, "ไม่มีเหรียญอื่นในหมวดเดียวกับที่ผู้ใช้นี้ถืออยู่ กำหนดหมวดได้ที่เมนู จัดการเหรียญ & การถือ")


def users_section() -> None:
    users = db.get_users()
    names = [u["name"] for u in users]
    symbols = [c["symbol"] for c in db.get_coins()]

    table, panel = st.columns([3, 2], gap="large")
    with table:
        show_table(
            users,
            {"name": "ผู้ใช้", "coins": "เหรียญที่ถือ"},
            "ยังไม่มีผู้ใช้ เพิ่มคนแรกได้จากแผงด้านขวา หรือสร้างข้อมูลตัวอย่างที่เมนู ตั้งค่าข้อมูล",
        )
    with panel, st.container(border=True):
        action = st.radio(
            "การทำงานกับผู้ใช้", ["เพิ่ม", "เปลี่ยนชื่อ", "ลบ"], horizontal=True, key="user_action", label_visibility="collapsed"
        )
        if action == "เพิ่ม":
            with st.form("add_user", clear_on_submit=True, border=False):
                name = st.text_input("ชื่อผู้ใช้")
                coins = st.multiselect("เหรียญที่ถือ", symbols)
                if st.form_submit_button("เพิ่มผู้ใช้", type="primary"):
                    run_action(f"เพิ่มผู้ใช้ {name.strip()} แล้ว", db.create_user, name, coins)
        elif not names:
            st.caption("ยังไม่มีผู้ใช้ให้แก้ไข")
        elif action == "เปลี่ยนชื่อ":
            target = st.selectbox("ผู้ใช้", names, key="rename_user")
            new_name = st.text_input("ชื่อใหม่", value=target, key=f"rename_user_to_{target}")
            if st.button("บันทึกชื่อใหม่", type="primary", key="rename_user_save"):
                run_action(f"เปลี่ยนชื่อ {target} เป็น {new_name.strip()} แล้ว", db.rename_user, target, new_name)
        else:
            target = st.selectbox("ผู้ใช้", names, key="delete_user")
            sure = st.checkbox(f"ยืนยันการลบ {target} และความสัมพันธ์ทั้งหมดของผู้ใช้นี้", key=f"delete_user_sure_{target}")
            if st.button("ลบผู้ใช้", key="delete_user_go", disabled=not sure):
                run_action(f"ลบผู้ใช้ {target} แล้ว", db.delete_user, target)


def friends_section() -> None:
    html(
        '<div class="lead">FRIEND_OF ไม่ได้กรอกเอง ระบบสร้างใหม่ทุกครั้งที่ HOLDS เปลี่ยน ผู้ใช้ 2 คนที่ถือเหรียญเดียวกัน'
        "อย่างน้อย 1 เหรียญเป็นเพื่อนกัน และ weight คือจำนวนเหรียญที่ถือร่วมกัน</div>"
    )
    show_table(
        db.get_friendships(),
        {"user1": "ผู้ใช้ 1", "user2": "ผู้ใช้ 2", "shared_coins": "เหรียญที่ถือร่วมกัน", "weight": "weight"},
        "ยังไม่มีคู่เพื่อน เพราะยังไม่มีผู้ใช้ 2 คนที่ถือเหรียญเดียวกัน",
    )
    if st.button("คำนวณ FRIEND_OF ใหม่จาก HOLDS", icon=":material/sync:", key="rebuild_friends"):
        run_action("คำนวณ FRIEND_OF ใหม่แล้ว", db.rebuild_friendships)
    st.caption("ใช้เมื่อมีการแก้ข้อมูลจากนอกแอป เช่น Notebook หรือ Aura Query")


def page_people() -> None:
    page_header("จัดการคน & เพื่อน", "เพิ่ม เปลี่ยนชื่อ หรือลบผู้ใช้ และดูว่าใครเป็นเพื่อนกับใครจากเหรียญที่ถือร่วมกัน")
    user_tab, friend_tab = st.tabs(["ผู้ใช้", "เพื่อน (FRIEND_OF)"])
    with user_tab:
        users_section()
    with friend_tab:
        friends_section()


def holds_section(coins: list[dict]) -> None:
    users = db.get_users()
    if not users or not coins:
        st.info("ต้องมีทั้งผู้ใช้และเหรียญก่อน จึงจะสร้าง HOLDS ได้ เพิ่มผู้ใช้ที่เมนู จัดการคน & เพื่อน และเพิ่มเหรียญที่แท็บ เหรียญ")
        return
    holdings = {u["name"]: u["coins"] for u in users}
    names = list(holdings)
    symbols = [c["symbol"] for c in coins]

    table, panel = st.columns([3, 2], gap="large")
    with table:
        show_table(users, {"name": "ผู้ใช้", "coins": "เหรียญที่ถือ (HOLDS)"}, "ยังไม่มี HOLDS")
    with panel, st.container(border=True):
        action = st.radio(
            "การทำงานกับ HOLDS",
            ["แก้ทั้งพอร์ต", "เพิ่มทีละเส้น", "ลบทีละเส้น"],
            horizontal=True,
            key="holds_action",
            label_visibility="collapsed",
        )
        if action == "แก้ทั้งพอร์ต":
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
        elif action == "เพิ่มทีละเส้น":
            user = st.selectbox("ผู้ใช้", names, key="add_hold_user")
            coin = st.selectbox("เหรียญ", symbols, key="add_hold_coin")
            if st.button("เพิ่ม HOLDS", type="primary", key="add_hold_go"):
                if coin in holdings[user]:
                    st.warning(f"{user} ถือ {coin} อยู่แล้ว")
                else:
                    run_action(f"เพิ่ม ({user})-[:HOLDS]->({coin}) แล้ว", db.add_hold, user, coin)
        else:
            edges = {f"{u} → {c}": (u, c) for u, held in holdings.items() for c in held}
            if edges:
                chosen = st.selectbox("ความสัมพันธ์", list(edges), key="remove_hold")
                if st.button("ลบ HOLDS", key="remove_hold_go"):
                    run_action(f"ลบ HOLDS {chosen} แล้ว", db.remove_hold, *edges[chosen])
            else:
                st.caption("ยังไม่มี HOLDS ให้ลบ")


def coins_section(coins: list[dict], options: list[str]) -> None:
    table, panel = st.columns([3, 2], gap="large")
    with table:
        show_coin_table(
            coins,
            "symbol",
            {"symbol": "สัญลักษณ์", "category": "หมวดหมู่", "holders": "ผู้ถือ"},
            "ยังไม่มีเหรียญ เพิ่มเหรียญแรกได้จากแผงด้านขวา หรือสร้างข้อมูลตัวอย่างที่เมนู ตั้งค่าข้อมูล",
        )
    with panel, st.container(border=True):
        action = st.radio(
            "การทำงานกับเหรียญ", ["เพิ่ม", "แก้ไข", "ลบ"], horizontal=True, key="coin_action", label_visibility="collapsed"
        )
        if action == "เพิ่ม":
            with st.form("add_coin", clear_on_submit=True, border=False):
                symbol = st.text_input("สัญลักษณ์", placeholder="เช่น BTC")
                category = st.selectbox("หมวดหมู่", options)
                upload = st.file_uploader("รูปเหรียญ (ไม่บังคับ)", type=COIN_IMAGE_TYPES)
                if st.form_submit_button("เพิ่มเหรียญ", type="primary"):
                    run_action(
                        f"เพิ่มเหรียญ {symbol.strip().upper()} แล้ว",
                        create_coin,
                        symbol,
                        None if category == NO_CATEGORY else category,
                        upload,
                    )
        elif not coins:
            st.caption("ยังไม่มีเหรียญให้แก้ไข")
        elif action == "แก้ไข":
            current = {c["symbol"]: c["category"] or NO_CATEGORY for c in coins}
            images = {c["symbol"]: c["image"] for c in coins}
            target = st.selectbox("เหรียญ", list(current), key="edit_coin")
            stored = images[target]
            html(f'<img class="coin-preview" src="{coin_image(target, stored)}" alt="รูปปัจจุบันของ {escape(target)}">')
            new_symbol = st.text_input("สัญลักษณ์", value=target, key=f"edit_coin_symbol_{target}")
            category = st.selectbox(
                "หมวดหมู่",
                options,
                index=options.index(current[target]),
                key=f"edit_coin_category_{target}_{current[target]}",
            )
            # The key carries the stored picture so the uploader empties once a new one is saved.
            tag = zlib.crc32((stored or "").encode())
            upload = st.file_uploader("เปลี่ยนรูปเหรียญ", type=COIN_IMAGE_TYPES, key=f"edit_coin_image_{target}_{tag}")
            clear_image = bool(stored) and st.checkbox(
                "ลบรูปที่อัปโหลดไว้ แล้วกลับไปใช้รูปเริ่มต้น", key=f"edit_coin_clear_{target}_{tag}"
            )
            if st.button("บันทึกเหรียญ", type="primary", key="edit_coin_save"):
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
            target = st.selectbox("เหรียญ", [c["symbol"] for c in coins], key="delete_coin")
            sure = st.checkbox(f"ยืนยันการลบ {target} และ HOLDS ทั้งหมดของเหรียญนี้", key=f"delete_coin_sure_{target}")
            if st.button("ลบเหรียญ", key="delete_coin_go", disabled=not sure):
                run_action(f"ลบเหรียญ {target} แล้ว", db.delete_coin, target)


def categories_section(categories: list[dict]) -> None:
    names = [k["name"] for k in categories]
    table, panel = st.columns([3, 2], gap="large")
    with table:
        show_table(
            categories,
            {"name": "หมวดหมู่", "coins": "เหรียญในหมวด (IN_CATEGORY)"},
            "ยังไม่มีหมวดหมู่ หมวดหมู่ทำให้แนะนำเหรียญได้แม้ผู้ใช้ยังไม่มีเพื่อน เพิ่มได้จากแผงด้านขวา",
        )
    with panel, st.container(border=True):
        action = st.radio(
            "การทำงานกับหมวดหมู่",
            ["เพิ่ม", "เปลี่ยนชื่อ", "ลบ"],
            horizontal=True,
            key="category_action",
            label_visibility="collapsed",
        )
        if action == "เพิ่ม":
            with st.form("add_category", clear_on_submit=True, border=False):
                name = st.text_input("ชื่อหมวดหมู่", placeholder="เช่น Layer1")
                if st.form_submit_button("เพิ่มหมวดหมู่", type="primary"):
                    run_action(f"เพิ่มหมวดหมู่ {name.strip()} แล้ว", db.create_category, name)
        elif not names:
            st.caption("ยังไม่มีหมวดหมู่ให้แก้ไข")
        elif action == "เปลี่ยนชื่อ":
            target = st.selectbox("หมวดหมู่", names, key="rename_category")
            new_name = st.text_input("ชื่อใหม่", value=target, key=f"rename_category_to_{target}")
            if st.button("บันทึกชื่อใหม่", type="primary", key="rename_category_save"):
                run_action(
                    f"เปลี่ยนชื่อหมวด {target} เป็น {new_name.strip()} แล้ว", db.rename_category, target, new_name
                )
        else:
            target = st.selectbox("หมวดหมู่", names, key="delete_category")
            sure = st.checkbox(f"ยืนยันการลบ {target} เหรียญในหมวดนี้จะไม่มีหมวด", key=f"delete_category_sure_{target}")
            if st.button("ลบหมวดหมู่", key="delete_category_go", disabled=not sure):
                run_action(f"ลบหมวดหมู่ {target} แล้ว", db.delete_category, target)


def page_coins() -> None:
    page_header("จัดการเหรียญ & การถือ", "เพิ่มหรือแก้ไขเหรียญและรูปของเหรียญ กำหนดว่าใครถือเหรียญไหน และจัดหมวดหมู่ของเหรียญ")
    coins = db.get_coins()
    categories = db.get_categories()
    coin_tab, holds_tab, category_tab = st.tabs(["เหรียญ", "การถือ (HOLDS)", "หมวดหมู่"])
    with coin_tab:
        coins_section(coins, category_options(categories))
    with holds_tab:
        holds_section(coins)
    with category_tab:
        categories_section(categories)


def page_graph() -> None:
    page_header("กราฟความสัมพันธ์", "ภาพรวมของ Node และ Relationship ที่อยู่ในฐานข้อมูลตอนนี้ สีของเส้นบอกชนิดความสัมพันธ์")
    c1, c2 = st.columns([1, 2], gap="large")
    scope = c1.radio("ขอบเขต", ["ทั้งกราฟ", "รอบผู้ใช้หนึ่งคน"], horizontal=True)
    types = c2.multiselect("ความสัมพันธ์ที่แสดง", list(REL_COLORS), default=["HOLDS", "IN_CATEGORY"])
    name = user_selector("graph_user") if scope == "รอบผู้ใช้หนึ่งคน" else None
    if not types:
        st.info("เลือกความสัมพันธ์อย่างน้อย 1 ชนิดเพื่อวาดกราฟ")
        return
    rows = db.graph_edges(types, name)
    if not rows:
        st.info("ยังไม่มีความสัมพันธ์ชนิดที่เลือก สร้างข้อมูลตัวอย่างได้ที่เมนู ตั้งค่าข้อมูล")
        return
    legend(types)
    # A neighbourhood is small: stretching it to the page width would blow the nodes up.
    st.graphviz_chart(build_dot(rows), width="content" if name else "stretch")
    with st.expander("ดูข้อมูล edge ที่ใช้วาดกราฟ"):
        show_table(
            rows,
            {
                "source_label": "ชนิดต้นทาง",
                "source_name": "ต้นทาง",
                "relationship": "ความสัมพันธ์",
                "weight": "weight",
                "target_label": "ชนิดปลายทาง",
                "target_name": "ปลายทาง",
            },
            "",
        )


def page_admin() -> None:
    page_header("ตั้งค่าข้อมูล", "สร้างชุดข้อมูลตัวอย่างจาก Notebook หรือล้างข้อมูลของโปรเจกต์นี้ออกจากฐานข้อมูล")
    info = db.connection_info()
    m = db.get_dashboard_metrics()
    st.subheader("ฐานข้อมูลตอนนี้", anchor=False)
    st.markdown(f"เชื่อมต่ออยู่กับ `{info['uri']}` · database `{info['database']}`")
    facts = [
        ("ผู้ใช้", m.get("users", 0)),
        ("เหรียญ", m.get("coins", 0)),
        ("หมวดหมู่", m.get("categories", 0)),
        ("HOLDS", m.get("holds", 0)),
        ("FRIEND_OF", m.get("friendships", 0)),
    ]
    html('<div class="facts">' + "".join(f"<span><b>{value}</b>{label}</span>" for label, value in facts) + "</div>")
    st.markdown(
        """
        - `(:User {name})-[:HOLDS]->(:Coin {symbol, image})`
        - `(:Coin)-[:IN_CATEGORY]->(:Category {name})`
        - `(:User)-[:FRIEND_OF {shared_coins, weight}]->(:User)` คำนวณจาก `HOLDS`
        """
    )

    st.subheader("สร้างข้อมูลตัวอย่าง", anchor=False)
    st.markdown("ผู้ใช้ 10 คน เหรียญ 8 เหรียญ และ HOLDS 26 เส้นจาก Notebook ใช้ `MERGE` จึงกดซ้ำได้และไม่ลบข้อมูลเดิม")
    if st.button("สร้างข้อมูลตัวอย่าง", type="primary", icon=":material/database:"):
        with st.spinner("กำลังสร้างข้อมูล..."):
            run_action("สร้างข้อมูลตัวอย่างเรียบร้อยแล้ว", db.seed_demo_data)

    st.subheader("ล้างข้อมูล", anchor=False)
    st.markdown("ลบ Node ทุกตัวที่เป็น User, Coin และ Category พร้อมความสัมพันธ์ทั้งหมด **กู้คืนไม่ได้**")
    sure = st.checkbox("ยืนยันว่าต้องการล้างข้อมูลทั้งหมด")
    if st.button("ล้างข้อมูล", icon=":material/delete:", disabled=not sure):
        run_action("ล้างข้อมูลเรียบร้อยแล้ว", db.clear_data)


PAGES = {
    "แนะนำเหรียญ": page_recommendations,
    "จัดการคน & เพื่อน": page_people,
    "จัดการเหรียญ & การถือ": page_coins,
    "กราฟความสัมพันธ์": page_graph,
    "ตั้งค่าข้อมูล": page_admin,
}


def open_app() -> None:
    st.query_params["view"] = "app"


def open_hub() -> None:
    st.query_params.clear()


def homework_files(folder: str, suffix: str) -> list[Path]:
    return sorted((HOMEWORK_DIR / folder).glob(f"*{suffix}"))


def hub_stop(index: int, stop: dict) -> None:
    with st.container(key=f"hub_stop_{index}"):
        folder = stop.get("folder")
        files = [] if folder is None else homework_files(folder, ".ipynb") + homework_files(folder, ".pdf")
        file_note = f'<div class="stop-files">{escape(" · ".join(f.name for f in files))}</div>' if files else ""
        html(
            f'<div class="stop-title">{stop["title"]}</div>'
            f'<div class="stop-desc">{stop["desc"]}</div>{file_note}'
        )
        with st.container(horizontal=True):
            if folder is None:
                st.button("เข้าสู่ระบบแนะนำ", key="hub_enter", type="primary", icon=":material/arrow_forward:", on_click=open_app)
                st.link_button("ดูโค้ดบน GitHub", REPO_URL, icon=":material/open_in_new:")
                return

            # Buttons follow whatever is in the folder: drop a notebook or PDF in and it shows up here.
            path = f"homework/{folder}"
            notebooks = homework_files(folder, ".ipynb")
            pdfs = homework_files(folder, ".pdf")
            if notebooks:
                notebook_path = quote(f"{path}/{notebooks[0].name}")
                st.link_button("เปิดใน Colab", f"{COLAB_URL}/{notebook_path}", icon=":material/open_in_new:")
            if pdfs:
                st.download_button(
                    "ดาวน์โหลด PDF",
                    pdfs[0].read_bytes(),
                    file_name=pdfs[0].name,
                    mime="application/pdf",
                    icon=":material/download:",
                    key=f"hub_pdf_{index}",
                )
            if not files:
                st.button("ยังไม่มีไฟล์งาน", key=f"hub_empty_{index}", disabled=True)
            st.link_button("ดูไฟล์บน GitHub", f"{REPO_URL}/tree/{BRANCH}/{path}", icon=":material/open_in_new:")


def render_hub() -> None:
    last = len(HUB_STOPS)
    numbers = "".join(f'.st-key-hub_stop_{i}::after {{content: "{i:02d}";}}' for i in range(1, last + 1))
    html(
        f"""
        <style>
          .block-container {{padding-top: 0; max-width: 1040px;}}
          [data-testid="stHeader"] {{background: transparent;}}
          [data-testid="stHeader"] :is(button, a, span, p) {{color: #fff;}}
          .hub-band {{
            background: var(--holds); color: #fff; margin-top: -1rem; padding: 6.5rem 0 3rem 0;
            box-shadow: 0 0 0 100vmax var(--holds); clip-path: inset(0 -100vmax);
          }}
          .hub-title {{font-size: 2.75rem; font-weight: 700; line-height: 1.25; letter-spacing: -.01em; text-wrap: balance;}}
          .hub-sub {{font-size: 1.1rem; line-height: 1.7; max-width: 60ch; margin-top: .75rem;}}
          .hub-owner {{font-size: .95rem; margin-top: 1.75rem; font-variant-numeric: tabular-nums;}}

          /* The four assignments as stops on one line that leaves the band and ends at the app */
          .st-key-hub_line {{gap: 0; position: relative; margin-top: -1rem; padding-top: 3rem;}}
          .st-key-hub_line::before {{
            content: ""; position: absolute; left: calc(1.5rem - 4px); top: 0; height: 3rem; width: 8px;
            background: var(--holds);
          }}
          [class*="st-key-hub_stop_"] {{position: relative; padding: 0 0 3rem 5rem; gap: 1.1rem;}}
          [class*="st-key-hub_stop_"]::before {{
            content: ""; position: absolute; left: calc(1.5rem - 4px); top: 0; bottom: 0; width: 8px;
            background: var(--holds);
          }}
          [class*="st-key-hub_stop_"]::after {{
            position: absolute; left: 0; top: 0; box-sizing: border-box; width: 3rem; height: 3rem;
            display: flex; align-items: center; justify-content: center; border-radius: 50%;
            background: #fff; border: 5px solid var(--ink); color: var(--ink);
            font-weight: 700; font-size: 1rem; font-variant-numeric: tabular-nums;
          }}
          .st-key-hub_stop_{last} {{padding-bottom: 0;}}
          .st-key-hub_stop_{last}::before {{bottom: auto; height: 1.5rem;}}
          .st-key-hub_stop_{last}::after {{background: var(--ink); color: #fff;}}
          {numbers}
          .stop-title {{font-size: 1.4rem; font-weight: 700; line-height: 3rem; text-wrap: balance;}}
          .st-key-hub_stop_{last} .stop-title {{font-size: 1.9rem;}}
          .stop-desc {{color: var(--muted); max-width: 62ch;}}
          .stop-files {{font-size: .85rem; color: var(--muted); margin-top: .6rem; overflow-wrap: anywhere;}}
          .hub-foot {{
            color: var(--muted); font-size: .85rem; border-top: 1px solid var(--rule);
            margin-top: 3.5rem; padding-top: 1.25rem;
          }}
          @media (max-width: 640px) {{
            .hub-title {{font-size: 2rem;}}
            [class*="st-key-hub_stop_"] {{padding-left: 4rem;}}
            .stop-title {{font-size: 1.2rem; line-height: 1.4; padding-top: .6rem;}}
            .st-key-hub_stop_{last} .stop-title {{font-size: 1.5rem;}}
          }}
          @media (prefers-reduced-motion: no-preference) {{
            [class*="st-key-hub_stop_"]::before, .st-key-hub_line::before {{
              transform-origin: top; animation: draw-line .7s cubic-bezier(.16, 1, .3, 1) both;
            }}
            @keyframes draw-line {{from {{transform: scaleY(0);}} to {{transform: scaleY(1);}}}}
          }}
        </style>
        <div class="hub-band">
          <div class="hub-title">รวมการบ้านและระบบแนะนำ</div>
          <div class="hub-sub">งานวิชา Graph Database สี่ชิ้นที่ต่อเนื่องกัน เริ่มจาก Cypher พื้นฐาน ไปถึงระบบแนะนำเหรียญที่ต่อกับ Neo4j Aura</div>
          <div class="hub-owner">{OWNER_NAME} · รหัสนักศึกษา {OWNER_ID}</div>
        </div>
        """
    )
    with st.container(key="hub_line"):
        for index, stop in enumerate(HUB_STOPS, start=1):
            hub_stop(index, stop)
    html('<div class="hub-foot">ตัวอย่างเชิงวิชาการเรื่องโครงสร้าง Graph เท่านั้น ไม่ใช่คำแนะนำการลงทุน</div>')


def render_app() -> None:
    require_connection()

    with st.sidebar:
        html(
            '<div class="side-title">ระบบแนะนำเหรียญ Crypto</div>'
            f'<div class="side-note">{OWNER_NAME}<br>รหัสนักศึกษา {OWNER_ID}</div>'
        )
        page = st.radio("เมนู", list(PAGES), label_visibility="collapsed")
        st.button("กลับหน้ารวมการบ้าน", icon=":material/arrow_back:", on_click=open_hub, key="back_hub", width="stretch")

    flash = st.session_state.pop("flash", None)
    if flash:
        st.toast(flash, icon=":material/check_circle:")

    PAGES[page]()


if st.query_params.get("view") == "app":
    render_app()
else:
    render_hub()
