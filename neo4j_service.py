from __future__ import annotations

from typing import Any

import streamlit as st
from neo4j import GraphDatabase, RoutingControl

# Sample dataset from the CryptoRecommender notebook
DEMO_COINS = {
    "BTC": "Layer1",
    "ETH": "Layer1",
    "SOL": "Layer1",
    "ADA": "Layer1",
    "BNB": "Exchange",
    "XRP": "Payment",
    "DOGE": "Meme",
    "PEPE": "Meme",
}
DEMO_HOLDS = {
    "Anan": ["BTC", "ETH"],
    "Bee": ["BTC", "ETH", "SOL"],
    "Chai": ["BTC", "BNB"],
    "Dao": ["SOL", "DOGE"],
    "Earn": ["ETH", "SOL", "ADA"],
    "Fah": ["BTC", "XRP"],
    "Gun": ["DOGE", "PEPE"],
    "Ice": ["ETH", "ADA", "XRP"],
    "Jane": ["BTC", "ETH", "BNB", "SOL"],
    "Kong": ["SOL", "PEPE", "DOGE"],
}

# FRIEND_OF is derived data: two users are friends when they hold at least one coin in common.
_FRIEND_CLEAR = "MATCH (:User)-[f:FRIEND_OF]->(:User) DELETE f"
_FRIEND_BUILD = """
MATCH (a:User)-[:HOLDS]->(c:Coin)<-[:HOLDS]-(b:User)
WHERE a.name < b.name
WITH a, b, c ORDER BY c.symbol
WITH a, b, collect(c.symbol) AS shared
MERGE (a)-[f:FRIEND_OF]->(b)
SET f.shared_coins = shared, f.weight = size(shared)
"""

Step = tuple[str, dict[str, Any]]


@st.cache_resource(show_spinner=False)
def _connect():
    """Create one thread-safe Neo4j Driver for the Streamlit process."""
    cfg = st.secrets["neo4j"]
    uri, username, password = cfg.get("uri"), cfg.get("username"), cfg.get("password")
    if not (uri and username and password):
        raise RuntimeError("ยังไม่ได้กรอก uri / username / password ใน Streamlit Secrets")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    # No database in secrets: fall back to the home database, as the notebook does.
    database = cfg.get("database") or driver.execute_query("SHOW HOME DATABASE").records[0]["name"]
    return driver, database


def connection_info() -> dict[str, str]:
    _, database = _connect()
    return {"uri": st.secrets["neo4j"]["uri"], "database": database}


def query(cypher: str, parameters: dict[str, Any] | None = None, *, write: bool = False) -> list[dict[str, Any]]:
    """Execute parameterized Cypher and return rows as dictionaries."""
    driver, database = _connect()
    records, _, _ = driver.execute_query(
        cypher,
        parameters_=parameters or {},
        database_=database,
        routing_=RoutingControl.WRITE if write else RoutingControl.READ,
    )
    return [record.data() for record in records]


def _write(*steps: Step, sync_friends: bool = False) -> None:
    """Run every statement in one transaction, optionally rebuilding FRIEND_OF from HOLDS."""
    statements = list(steps)
    if sync_friends:
        statements += [(_FRIEND_CLEAR, {}), (_FRIEND_BUILD, {})]

    def work(tx):
        for cypher, parameters in statements:
            tx.run(cypher, parameters).consume()

    driver, database = _connect()
    with driver.session(database=database) as session:
        session.execute_write(work)


def ping() -> bool:
    rows = query("RETURN 1 AS ok")
    return bool(rows and rows[0]["ok"] == 1)


def create_schema() -> None:
    statements = [
        "CREATE CONSTRAINT user_name_unique IF NOT EXISTS FOR (u:User) REQUIRE u.name IS UNIQUE",
        "CREATE CONSTRAINT coin_symbol_unique IF NOT EXISTS FOR (c:Coin) REQUIRE c.symbol IS UNIQUE",
        "CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (k:Category) REQUIRE k.name IS UNIQUE",
    ]
    for stmt in statements:
        query(stmt, write=True)


@st.cache_resource(show_spinner=False)
def ensure_schema() -> bool:
    """Create the unique constraints once per Streamlit process."""
    create_schema()
    return True


def seed_demo_data() -> None:
    """Idempotent sample dataset: safe to run more than once."""
    create_schema()
    coins = [{"symbol": s, "category": k} for s, k in DEMO_COINS.items()]
    holds = [{"user": u, "coin": c} for u, symbols in DEMO_HOLDS.items() for c in symbols]
    _write(
        ("UNWIND $rows AS name MERGE (:User {name: name})", {"rows": list(DEMO_HOLDS)}),
        (
            """
            UNWIND $rows AS row
            MERGE (c:Coin {symbol: row.symbol})
            MERGE (k:Category {name: row.category})
            MERGE (c)-[:IN_CATEGORY]->(k)
            """,
            {"rows": coins},
        ),
        (
            """
            UNWIND $rows AS row
            MATCH (u:User {name: row.user}), (c:Coin {symbol: row.coin})
            MERGE (u)-[:HOLDS]->(c)
            """,
            {"rows": holds},
        ),
        sync_friends=True,
    )


def clear_data() -> None:
    """Delete only this project's nodes (User / Coin / Category) and their relationships."""
    _write(("MATCH (n) WHERE n:User OR n:Coin OR n:Category DETACH DELETE n", {}))


def rebuild_friendships() -> None:
    _write(sync_friends=True)


# ---------- validation helpers ----------

def _clean(value: str | None, what: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"กรุณากรอก{what}")
    return value


def _user_exists(name: str) -> bool:
    return bool(query("MATCH (u:User {name: $name}) RETURN 1 AS ok LIMIT 1", {"name": name}))


def _coin_exists(symbol: str) -> bool:
    return bool(query("MATCH (c:Coin {symbol: $symbol}) RETURN 1 AS ok LIMIT 1", {"symbol": symbol}))


def _category_exists(name: str) -> bool:
    return bool(query("MATCH (k:Category {name: $name}) RETURN 1 AS ok LIMIT 1", {"name": name}))


# ---------- User ----------

def get_users() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:User)
        OPTIONAL MATCH (u)-[:HOLDS]->(c:Coin)
        WITH u, c ORDER BY c.symbol
        RETURN u.name AS name, collect(c.symbol) AS coins
        ORDER BY name
        """
    )


def create_user(name: str, coins: list[str] | None = None) -> None:
    name = _clean(name, "ชื่อผู้ใช้")
    if _user_exists(name):
        raise ValueError(f"มีผู้ใช้ชื่อ {name} อยู่แล้ว")
    _write(
        ("CREATE (:User {name: $name})", {"name": name}),
        (
            """
            MATCH (u:User {name: $name})
            UNWIND $coins AS symbol
            MATCH (c:Coin {symbol: symbol})
            MERGE (u)-[:HOLDS]->(c)
            """,
            {"name": name, "coins": coins or []},
        ),
        sync_friends=bool(coins),
    )


def rename_user(name: str, new_name: str) -> None:
    new_name = _clean(new_name, "ชื่อใหม่")
    if new_name == name:
        return
    if _user_exists(new_name):
        raise ValueError(f"มีผู้ใช้ชื่อ {new_name} อยู่แล้ว")
    # FRIEND_OF direction follows a.name < b.name, so it is rebuilt after a rename.
    _write(
        ("MATCH (u:User {name: $name}) SET u.name = $new_name", {"name": name, "new_name": new_name}),
        sync_friends=True,
    )


def delete_user(name: str) -> None:
    _write(("MATCH (u:User {name: $name}) DETACH DELETE u", {"name": name}))


# ---------- Coin ----------

def get_coins() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (c:Coin)
        OPTIONAL MATCH (c)-[:IN_CATEGORY]->(k:Category)
        WITH c, head(collect(k.name)) AS category
        OPTIONAL MATCH (u:User)-[:HOLDS]->(c)
        WITH c, category, u ORDER BY u.name
        RETURN c.symbol AS symbol, category, collect(u.name) AS holders
        ORDER BY symbol
        """
    )


def _category_steps(symbol: str, category: str | None) -> list[Step]:
    """A coin belongs to at most one category: drop the old link, then attach the new one."""
    steps: list[Step] = [
        ("MATCH (:Coin {symbol: $symbol})-[r:IN_CATEGORY]->(:Category) DELETE r", {"symbol": symbol}),
    ]
    category = (category or "").strip()
    if category:
        steps.append(
            (
                """
                MATCH (c:Coin {symbol: $symbol})
                MERGE (k:Category {name: $category})
                MERGE (c)-[:IN_CATEGORY]->(k)
                """,
                {"symbol": symbol, "category": category},
            )
        )
    return steps


def create_coin(symbol: str, category: str | None = None) -> None:
    symbol = _clean(symbol, "สัญลักษณ์เหรียญ").upper()
    if _coin_exists(symbol):
        raise ValueError(f"มีเหรียญ {symbol} อยู่แล้ว")
    _write(("CREATE (:Coin {symbol: $symbol})", {"symbol": symbol}), *_category_steps(symbol, category))


def update_coin(symbol: str, new_symbol: str, category: str | None) -> None:
    new_symbol = _clean(new_symbol, "สัญลักษณ์เหรียญ").upper()
    renamed = new_symbol != symbol
    steps: list[Step] = []
    if renamed:
        if _coin_exists(new_symbol):
            raise ValueError(f"มีเหรียญ {new_symbol} อยู่แล้ว")
        steps.append(
            ("MATCH (c:Coin {symbol: $symbol}) SET c.symbol = $new_symbol", {"symbol": symbol, "new_symbol": new_symbol})
        )
    # shared_coins on FRIEND_OF stores symbols, so a rename needs a rebuild.
    _write(*steps, *_category_steps(new_symbol, category), sync_friends=renamed)


def delete_coin(symbol: str) -> None:
    _write(("MATCH (c:Coin {symbol: $symbol}) DETACH DELETE c", {"symbol": symbol}), sync_friends=True)


# ---------- Category ----------

def get_categories() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (k:Category)
        OPTIONAL MATCH (c:Coin)-[:IN_CATEGORY]->(k)
        WITH k, c ORDER BY c.symbol
        RETURN k.name AS name, collect(c.symbol) AS coins
        ORDER BY name
        """
    )


def create_category(name: str) -> None:
    name = _clean(name, "ชื่อหมวดหมู่")
    if _category_exists(name):
        raise ValueError(f"มีหมวดหมู่ {name} อยู่แล้ว")
    _write(("CREATE (:Category {name: $name})", {"name": name}))


def rename_category(name: str, new_name: str) -> None:
    new_name = _clean(new_name, "ชื่อใหม่")
    if new_name == name:
        return
    if _category_exists(new_name):
        raise ValueError(f"มีหมวดหมู่ {new_name} อยู่แล้ว")
    _write(("MATCH (k:Category {name: $name}) SET k.name = $new_name", {"name": name, "new_name": new_name}))


def delete_category(name: str) -> None:
    _write(("MATCH (k:Category {name: $name}) DETACH DELETE k", {"name": name}))


# ---------- HOLDS ----------

def get_holds() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:User)-[:HOLDS]->(c:Coin)
        RETURN u.name AS user, c.symbol AS coin
        ORDER BY user, coin
        """
    )


def get_user_holdings(name: str) -> list[dict[str, Any]]:
    return query(
        """
        MATCH (:User {name: $name})-[:HOLDS]->(c:Coin)
        OPTIONAL MATCH (c)-[:IN_CATEGORY]->(k:Category)
        RETURN c.symbol AS coin, head(collect(k.name)) AS category
        ORDER BY coin
        """,
        {"name": name},
    )


def add_hold(user: str, coin: str) -> None:
    _write(
        (
            "MATCH (u:User {name: $user}), (c:Coin {symbol: $coin}) MERGE (u)-[:HOLDS]->(c)",
            {"user": user, "coin": coin},
        ),
        sync_friends=True,
    )


def remove_hold(user: str, coin: str) -> None:
    _write(
        (
            "MATCH (:User {name: $user})-[r:HOLDS]->(:Coin {symbol: $coin}) DELETE r",
            {"user": user, "coin": coin},
        ),
        sync_friends=True,
    )


def set_user_holds(user: str, coins: list[str]) -> None:
    """Replace a user's whole portfolio with the given coins."""
    parameters = {"user": user, "coins": coins}
    _write(
        (
            """
            MATCH (:User {name: $user})-[r:HOLDS]->(c:Coin)
            WHERE NOT c.symbol IN $coins
            DELETE r
            """,
            parameters,
        ),
        (
            """
            MATCH (u:User {name: $user})
            UNWIND $coins AS symbol
            MATCH (c:Coin {symbol: symbol})
            MERGE (u)-[:HOLDS]->(c)
            """,
            parameters,
        ),
        sync_friends=True,
    )


# ---------- FRIEND_OF (read-only, derived from HOLDS) ----------

def get_friendships() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (a:User)-[f:FRIEND_OF]->(b:User)
        RETURN a.name AS user1, b.name AS user2, f.shared_coins AS shared_coins, f.weight AS weight
        ORDER BY weight DESC, user1, user2
        """
    )


def get_friends(name: str) -> list[dict[str, Any]]:
    return query(
        """
        MATCH (me:User {name: $name})-[f:FRIEND_OF]-(friend:User)
        RETURN friend.name AS friend, f.shared_coins AS shared_coins, f.weight AS weight
        ORDER BY weight DESC, friend
        """,
        {"name": name},
    )


# ---------- Dashboard / recommendations / graph ----------

def get_dashboard_metrics() -> dict[str, int]:
    rows = query(
        """
        OPTIONAL MATCH (u:User) WITH count(u) AS users
        OPTIONAL MATCH (c:Coin) WITH users, count(c) AS coins
        OPTIONAL MATCH (k:Category) WITH users, coins, count(k) AS categories
        OPTIONAL MATCH (:User)-[h:HOLDS]->(:Coin) WITH users, coins, categories, count(h) AS holds
        OPTIONAL MATCH (:User)-[f:FRIEND_OF]->(:User)
        RETURN users, coins, categories, holds, count(f) AS friendships
        """
    )
    return rows[0] if rows else {"users": 0, "coins": 0, "categories": 0, "holds": 0, "friendships": 0}


def recommend_coins(name: str, limit: int = 5) -> list[dict[str, Any]]:
    """3 hops: me -> coins I hold -> users holding the same coins -> coins I do not hold yet."""
    return query(
        """
        MATCH (me:User {name: $name})-[:HOLDS]->(:Coin)<-[:HOLDS]-(other:User)-[:HOLDS]->(rec:Coin)
        WHERE other <> me
          AND NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
        RETURN rec.symbol AS coin, count(*) AS score, collect(DISTINCT other.name) AS via_users
        ORDER BY score DESC, coin
        LIMIT $limit
        """,
        {"name": name, "limit": int(limit)},
    )


def recommend_by_friends(name: str, limit: int = 5) -> list[dict[str, Any]]:
    """2 hops through FRIEND_OF; weighted_score equals the 3-hop score."""
    return query(
        """
        MATCH (me:User {name: $name})-[f:FRIEND_OF]-(friend:User)-[:HOLDS]->(rec:Coin)
        WHERE NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
        RETURN rec.symbol AS coin,
               count(DISTINCT friend) AS friend_score,
               sum(f.weight) AS weighted_score,
               collect(friend.name) AS from_friends
        ORDER BY weighted_score DESC, friend_score DESC, coin
        LIMIT $limit
        """,
        {"name": name, "limit": int(limit)},
    )


def recommend_by_category(name: str, limit: int = 5) -> list[dict[str, Any]]:
    """Cold-start fallback: other coins in the categories of the coins I hold."""
    return query(
        """
        MATCH (me:User {name: $name})-[:HOLDS]->(:Coin)-[:IN_CATEGORY]->(k:Category)<-[:IN_CATEGORY]-(rec:Coin)
        WHERE NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
        RETURN rec.symbol AS coin, count(*) AS score, collect(DISTINCT k.name) AS categories
        ORDER BY score DESC, coin
        LIMIT $limit
        """,
        {"name": name, "limit": int(limit)},
    )


def graph_edges(types: list[str], name: str | None = None) -> list[dict[str, Any]]:
    """Edges for the Graph Explorer: the whole graph, or the neighborhood of one user."""
    return query(
        """
        MATCH (s)-[r:HOLDS|IN_CATEGORY|FRIEND_OF]->(t)
        WHERE type(r) IN $types
          AND (s:User OR s:Coin)
          AND (t:User OR t:Coin OR t:Category)
          AND (
            $name IS NULL
            OR (s:User AND s.name = $name)
            OR (t:User AND t.name = $name)
            OR (s:Coin AND EXISTS { MATCH (:User {name: $name})-[:HOLDS]->(s) })
          )
        RETURN labels(s)[0] AS source_label, coalesce(s.name, s.symbol) AS source_name,
               type(r) AS relationship, r.weight AS weight,
               labels(t)[0] AS target_label, coalesce(t.name, t.symbol) AS target_name
        ORDER BY relationship, source_name, target_name
        """,
        {"types": types, "name": name},
    )
