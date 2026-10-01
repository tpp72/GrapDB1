// Crypto Coin Recommendation
// Parameters: $name, $limit

// 1) 3 hops through HOLDS: me -> my coins -> users holding the same coins -> new coins
//    score = number of paths that reach the coin
MATCH (me:User {name: $name})-[:HOLDS]->(:Coin)<-[:HOLDS]-(other:User)-[:HOLDS]->(rec:Coin)
WHERE other <> me
  AND NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
RETURN rec.symbol AS coin,
       count(*) AS score,
       collect(DISTINCT other.name) AS via_users
ORDER BY score DESC, coin
LIMIT $limit;

// 2) 2 hops through FRIEND_OF: me -> friends -> coins my friends hold
//    weighted_score = sum of FRIEND_OF.weight, equal to the 3-hop score
MATCH (me:User {name: $name})-[f:FRIEND_OF]-(friend:User)-[:HOLDS]->(rec:Coin)
WHERE NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
RETURN rec.symbol AS coin,
       count(DISTINCT friend) AS friend_score,
       sum(f.weight) AS weighted_score,
       collect(friend.name) AS from_friends
ORDER BY weighted_score DESC, friend_score DESC, coin
LIMIT $limit;

// 3) Cold start: other coins in the categories of the coins I hold
MATCH (me:User {name: $name})-[:HOLDS]->(:Coin)-[:IN_CATEGORY]->(k:Category)<-[:IN_CATEGORY]-(rec:Coin)
WHERE NOT EXISTS { MATCH (me)-[:HOLDS]->(rec) }
RETURN rec.symbol AS coin,
       count(*) AS score,
       collect(DISTINCT k.name) AS categories
ORDER BY score DESC, coin
LIMIT $limit;
