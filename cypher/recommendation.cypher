// Crypto Coin Recommendation
// Parameters: $name, $limit
// Every query returns `paths`: the routes that were counted, so the app can draw why a coin scored.

// 1) 3 hops through HOLDS: me -> my coins -> users holding the same coins -> new coins
//    score = number of paths that reach the coin
MATCH (me:User {name: $name})-[:HOLDS]->(via:Coin)<-[:HOLDS]-(other:User)-[:HOLDS]->(rec:Coin)
WHERE other <> me
  AND NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
WITH rec, via, other ORDER BY via.symbol, other.name
RETURN rec.symbol AS coin,
       count(*) AS score,
       collect({coin: via.symbol, user: other.name}) AS paths
ORDER BY score DESC, coin
LIMIT $limit;

// 2) 2 hops through FRIEND_OF: me -> friends -> coins my friends hold
//    weighted_score = sum of FRIEND_OF.weight, equal to the 3-hop score
MATCH (me:User {name: $name})-[f:FRIEND_OF]-(friend:User)-[:HOLDS]->(rec:Coin)
WHERE NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
WITH rec, friend, f ORDER BY f.weight DESC, friend.name
RETURN rec.symbol AS coin,
       count(DISTINCT friend) AS friend_score,
       sum(f.weight) AS weighted_score,
       collect({user: friend.name, weight: f.weight}) AS paths
ORDER BY weighted_score DESC, friend_score DESC, coin
LIMIT $limit;

// 3) Cold start: other coins in the categories of the coins I hold
MATCH (me:User {name: $name})-[:HOLDS]->(via:Coin)-[:IN_CATEGORY]->(k:Category)<-[:IN_CATEGORY]-(rec:Coin)
WHERE NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
WITH rec, via, k ORDER BY via.symbol, k.name
RETURN rec.symbol AS coin,
       count(*) AS score,
       collect({coin: via.symbol, category: k.name}) AS paths
ORDER BY score DESC, coin
LIMIT $limit;
