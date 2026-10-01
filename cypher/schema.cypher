CREATE CONSTRAINT user_name_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.name IS UNIQUE;

CREATE CONSTRAINT coin_symbol_unique IF NOT EXISTS
FOR (c:Coin) REQUIRE c.symbol IS UNIQUE;

CREATE CONSTRAINT category_name_unique IF NOT EXISTS
FOR (k:Category) REQUIRE k.name IS UNIQUE;

// FRIEND_OF is derived from HOLDS: rebuild it whenever HOLDS changes
MATCH (:User)-[f:FRIEND_OF]->(:User) DELETE f;

MATCH (a:User)-[:HOLDS]->(c:Coin)<-[:HOLDS]-(b:User)
WHERE a.name < b.name
WITH a, b, c ORDER BY c.symbol
WITH a, b, collect(c.symbol) AS shared
MERGE (a)-[f:FRIEND_OF]->(b)
SET f.shared_coins = shared, f.weight = size(shared);
