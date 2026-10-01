# Crypto Coin Recommender (Graph Database)

โปรเจ็คตัวอย่างระดับปริญญาตรีสำหรับรายวิชา Graph Database / Advanced Database
พัฒนาด้วย **Streamlit + Neo4j Aura + Cypher** และออกแบบให้ deploy ผ่าน **GitHub → Streamlit Community Cloud** ได้โดยตรง

> โปรเจ็คนี้เป็นตัวอย่างเชิงวิชาการเรื่องโครงสร้าง Graph เท่านั้น ไม่ใช่คำแนะนำการลงทุน

## 1. แนวคิดของระบบ

ผู้ใช้ถือเหรียญอะไร → หาผู้ใช้คนอื่นที่พอร์ตคล้ายกัน → ดูว่าคนเหล่านั้นถือเหรียญอะไรอีก → แนะนำเหรียญนั้นกลับมา

ระบบใช้ Property Graph ดังนี้

```text
(:User {name})-[:HOLDS]->(:Coin {symbol, image})
(:Coin)-[:IN_CATEGORY]->(:Category {name})
(:User)-[:FRIEND_OF {shared_coins, weight}]->(:User)
```

`FRIEND_OF` เป็นข้อมูลที่ **คำนวณจาก `HOLDS`** (ผู้ใช้ 2 คนถือเหรียญเดียวกันอย่างน้อย 1 เหรียญ)
แอปจะสร้างใหม่ให้อัตโนมัติทุกครั้งที่ `HOLDS` เปลี่ยน จึงไม่มีหน้าจอให้แก้ `FRIEND_OF` โดยตรง

คำแนะนำมี 3 แบบ

| แบบ | เส้นทางในกราฟ | คะแนน |
|---|---|---|
| 3 hop ผ่าน `HOLDS` | ผู้ใช้ → เหรียญที่ถือ → คนอื่นที่ถือเหมือนกัน → เหรียญใหม่ | จำนวนเส้นทางที่เดินไปถึง |
| 2 hop ผ่าน `FRIEND_OF` | ผู้ใช้ → เพื่อน → เหรียญที่เพื่อนถือ | ผลรวม `weight` ของเพื่อน (เท่ากับแบบ 3 hop) |
| ตามหมวดหมู่ | ผู้ใช้ → เหรียญที่ถือ → หมวดหมู่ → เหรียญอื่นในหมวด | จำนวนเส้นทาง ใช้แก้ปัญหา Cold Start |

## 2. โครงสร้างไฟล์

```text
GrapDB1/
├── app.py                  # หน้าจอ Streamlit
├── neo4j_service.py        # ชั้นเชื่อมต่อฐานข้อมูลและ Cypher ทั้งหมด
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── secrets.toml.example
│   └── secrets.toml        # สร้างเองในเครื่อง ไม่ถูก commit
├── cypher/
│   ├── schema.cypher
│   └── recommendation.cypher
├── docs/
│   └── PROJECT_GUIDE_TH.md
└── homework/               # ไฟล์การบ้านที่แสดงบนการ์ด 01-03 ของหน้า Hub
    ├── 01_club/
    ├── 02_graph/
    └── 03_neo4j/
```

### หน้า Hub

หน้าแรกของแอปเป็นหน้ารวมการบ้าน 4 การ์ด การ์ดที่ 4 คือระบบแนะนำเหรียญนี้ (เปิดตรงได้ด้วย `?view=app`)
ส่วนการ์ด 01-03 สร้างปุ่มจากไฟล์ที่อยู่ในโฟลเดอร์ `homework/` ของแต่ละงาน

| ไฟล์ในโฟลเดอร์ | ปุ่มที่ได้ |
|---|---|
| `.ipynb` | เปิดการบ้านใน Colab |
| `.pdf` | ดาวน์โหลดเอกสาร PDF |
| ไม่มีไฟล์ | ปุ่ม “ยังไม่มีไฟล์งาน” (กดไม่ได้) |

ทุกการ์ดมีปุ่มดูไฟล์บน GitHub เสมอ ลิงก์ Colab และ GitHub จะใช้ได้หลัง push ไฟล์ขึ้น branch `main` แล้ว
ชื่อการ์ด คำอธิบาย และชื่อเจ้าของงานแก้ได้ที่ `HUB_CARDS`, `OWNER_NAME` และ `OWNER_ID` ตอนต้นของ `app.py`

## 3. สร้าง Neo4j Aura

1. สร้าง AuraDB instance
2. เก็บค่า Connection URI, username และ password
3. URI ของ Aura อยู่ในรูป `neo4j+s://...databases.neo4j.io`
4. อย่านำ password ไปใส่ในไฟล์ที่ commit ขึ้น GitHub

## 4. รันในเครื่อง

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

ใส่ credential ในไฟล์ `.streamlit/secrets.toml` (ถ้ายังไม่มีให้คัดลอกจาก `secrets.toml.example`)

```toml
[neo4j]
uri = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"
username = "YOUR_USERNAME"
password = "YOUR_PASSWORD"
```

ไม่ต้องใส่ `database` ก็ได้ ระบบจะถาม `SHOW HOME DATABASE` แล้วใช้ค่านั้นให้เอง จากนั้นรัน

```bash
streamlit run app.py
```

## 5. ครั้งแรกที่เปิดระบบ

1. จากหน้า Hub กด **เข้าสู่ระบบแนะนำ** แล้วเข้าเมนู **ตั้งค่าข้อมูล**
2. กด **สร้าง Constraint + Demo Data** จะได้ผู้ใช้ 10 คน เหรียญ 8 เหรียญ และ `HOLDS` 26 เส้นตาม Notebook
3. ระบบใช้ `MERGE` จึงกดซ้ำได้โดยไม่สร้าง node ซ้ำ
4. จากนั้นทดลองเมนู แนะนำเหรียญ และ กราฟความสัมพันธ์

## 6. การเพิ่ม ลบ แก้ไขข้อมูล

| เมนู | ทำอะไรได้ |
|---|---|
| จัดการคน & เพื่อน | เพิ่มผู้ใช้ (พร้อมเหรียญที่ถือ) เปลี่ยนชื่อ และลบ รวมถึงดู `FRIEND_OF` และสั่งคำนวณใหม่ |
| จัดการเหรียญ & การถือ | เพิ่มเหรียญพร้อมอัปโหลดรูป แก้ไขสัญลักษณ์ รูป และหมวด (`IN_CATEGORY`) ลบเหรียญ แก้ไขพอร์ตทั้งชุด เพิ่มหรือลบ `HOLDS` ทีละเส้น และเพิ่ม เปลี่ยนชื่อ ลบหมวดหมู่ |
| ตั้งค่าข้อมูล | สร้างข้อมูลตัวอย่าง และล้างข้อมูล User / Coin / Category ทั้งหมด |

### รูปเหรียญ

แอปเลือกรูปของแต่ละเหรียญตามลำดับนี้

1. รูปที่อัปโหลดตอนเพิ่มหรือแก้ไขเหรียญ (PNG, JPG, WEBP) แอปย่อให้ไม่เกิน 128 px แล้วเก็บเป็น data URI ใน property `image` ของ node `Coin` รูปจึงไม่หายเมื่อ Streamlit Cloud รีสตาร์ต
2. ไฟล์ `images/coins/<SYMBOL>.png` ใน repo ซึ่งมีให้แล้วสำหรับ BTC, ETH, BNB, SOL, ADA, XRP, DOGE (จากชุดไอคอน [cryptocurrency-icons](https://github.com/spothq/cryptocurrency-icons) สัญญาอนุญาต CC0)
3. ป้ายวงกลมสีที่สร้างจากสัญลักษณ์ของเหรียญ

ทุกการแก้ไขที่กระทบ `HOLDS` จะรันในทรานแซกชันเดียวกับการสร้าง `FRIEND_OF` ใหม่ ข้อมูลจึงตรงกันเสมอ
ถ้าแก้ข้อมูลจากนอกแอป เช่น Notebook หรือ Aura Query ให้กดปุ่ม **คำนวณ FRIEND_OF ใหม่จาก HOLDS** ในแท็บ `FRIEND_OF`

## 7. Deploy GitHub → Streamlit Community Cloud

1. push ไฟล์ทั้งหมดขึ้น GitHub **ยกเว้น `.streamlit/secrets.toml`** (อยู่ใน `.gitignore` แล้ว)
2. เข้า Streamlit Community Cloud แล้วเลือก Create app
3. เลือก repository, branch และ entrypoint = `app.py`
4. ใน Advanced settings → Secrets ใส่ค่า `[neo4j]` แบบเดียวกับข้อ 4
5. Deploy

## 8. ประเด็น Graph Database ที่นักศึกษาจะได้ฝึก

- Node, Label, Property
- Relationship และ Direction รวมถึงการเดินย้อนทิศ `<-[:HOLDS]-` และไม่สนทิศ `-[:FRIEND_OF]-`
- Constraint และ Unique Key
- `MATCH`, `MERGE`, `CREATE`, `SET`, `DELETE`, `DETACH DELETE`, `OPTIONAL MATCH`, `WITH`, `UNWIND`
- Graph traversal 2 hop และ 3 hop
- Aggregation เช่น `count`, `sum`, `collect`
- Relationship ที่คำนวณจากข้อมูลอื่น (derived relationship) และการรักษาให้ตรงกับต้นทาง
- Parameterized Cypher
- Python Driver, connection pooling และ transaction function
- Streamlit UI, Secrets และ cloud deployment

## 9. สิ่งที่ปรับจาก Notebook ต้นแบบ

- แยก database layer (`neo4j_service.py`) ออกจาก UI (`app.py`)
- ใช้ Streamlit Secrets แทนการพิมพ์ password ผ่าน `getpass`
- เพิ่ม ลบ แก้ไข User, Coin, Category และความสัมพันธ์ได้จากหน้าเว็บ
- สร้าง `FRIEND_OF` ใหม่อัตโนมัติในทรานแซกชันเดียวกับการแก้ `HOLDS`
- เรียง `shared_coins` ตามตัวอักษรเพื่อให้ผลลัพธ์คงที่
- คำแนะนำบอกเหตุผลได้ เช่น เดินผ่านผู้ใช้คนใด เพื่อนคนไหนถืออยู่ หรืออยู่หมวดใด
- วาดกราฟด้วย Graphviz ในหน้า กราฟความสัมพันธ์ แทน NetworkX + matplotlib
