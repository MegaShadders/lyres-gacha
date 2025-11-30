BEGIN TRANSACTION;
INSERT INTO units (id, rarity)
SELECT 
  json_extract(value, '$.id'), 
  json_extract(value, '$.rarity')
FROM json_each('[
    {"id":6,"rarity":"SSR"},
    {"id":7,"rarity":"SSR"},
    {"id":9,"rarity":"SSR"},
    {"id":10,"rarity":"R"},
    {"id":11,"rarity":"SR"},
    {"id":12,"rarity":"SR"},
    {"id":13,"rarity":"R"},
    {"id":14,"rarity":"R"},
    {"id":15,"rarity":"R"},
    {"id":16,"rarity":"R"},
    {"id":17,"rarity":"SR"},
    {"id":18,"rarity":"R"},
    {"id":19,"rarity":"R"},
    {"id":20,"rarity":"SSR"},
    {"id":21,"rarity":"SR"},
    {"id":22,"rarity":"SSR"},
    {"id":23,"rarity":"SSR"},
    {"id":24,"rarity":"SSR"},
    {"id":25,"rarity":"SR"},
    {"id":27,"rarity":"SR"},
    {"id":30,"rarity":"R"},
    {"id":31,"rarity":"R"},
    {"id":34,"rarity":"R"},
    {"id":37,"rarity":"SR"},
    {"id":38,"rarity":"SR"},
    {"id":40,"rarity":"SR"},
    {"id":41,"rarity":"SR"},
    {"id":45,"rarity":"SSR"},
    {"id":48,"rarity":"SSR"}
]');

INSERT INTO banners (id, active, name)
SELECT 
  json_extract(value, '$.id'), 
  json_extract(value, '$.active'),
  json_extract(value, '$.name')
FROM json_each('[
    {"id":1,"active":1,"name":"standard"},
    {"id":2,"active":1,"name":"limited"}
]');

INSERT INTO banner_units (banner_id, unit_id, rateup)
SELECT 
  json_extract(value, '$.banner_id'), 
  json_extract(value, '$.unit_id'),
  json_extract(value, '$.rateup')
FROM json_each('[
    {"banner_id":1,"unit_id":10,"rateup":0},
    {"banner_id":1,"unit_id":11,"rateup":0},
    {"banner_id":1,"unit_id":12,"rateup":0},
    {"banner_id":1,"unit_id":13,"rateup":0},
    {"banner_id":1,"unit_id":14,"rateup":0},
    {"banner_id":1,"unit_id":15,"rateup":0},
    {"banner_id":1,"unit_id":16,"rateup":0},
    {"banner_id":1,"unit_id":17,"rateup":0},
    {"banner_id":1,"unit_id":21,"rateup":0},
    {"banner_id":1,"unit_id":25,"rateup":0},
    {"banner_id":1,"unit_id":7,"rateup":0},
    {"banner_id":1,"unit_id":9,"rateup":0},
    {"banner_id":1,"unit_id":18,"rateup":0},
    {"banner_id":1,"unit_id":19,"rateup":0},
    {"banner_id":1,"unit_id":20,"rateup":0},
    {"banner_id":1,"unit_id":22,"rateup":0},
    {"banner_id":1,"unit_id":23,"rateup":0},
    {"banner_id":1,"unit_id":24,"rateup":0},
    {"banner_id":1,"unit_id":27,"rateup":0},
    {"banner_id":1,"unit_id":30,"rateup":0},
    {"banner_id":1,"unit_id":31,"rateup":0},
    {"banner_id":1,"unit_id":34,"rateup":0},
    {"banner_id":1,"unit_id":37,"rateup":0},
    {"banner_id":1,"unit_id":38,"rateup":0},
    {"banner_id":1,"unit_id":40,"rateup":0},
    {"banner_id":1,"unit_id":41,"rateup":0},
    {"banner_id":1,"unit_id":45,"rateup":0},
    {"banner_id":1,"unit_id":48,"rateup":0},
    {"banner_id":2,"unit_id":10,"rateup":0},
    {"banner_id":2,"unit_id":11,"rateup":0},
    {"banner_id":2,"unit_id":12,"rateup":0},
    {"banner_id":2,"unit_id":13,"rateup":0},
    {"banner_id":2,"unit_id":14,"rateup":0},
    {"banner_id":2,"unit_id":15,"rateup":0},
    {"banner_id":2,"unit_id":16,"rateup":0},
    {"banner_id":2,"unit_id":17,"rateup":0},
    {"banner_id":2,"unit_id":21,"rateup":0},
    {"banner_id":2,"unit_id":25,"rateup":0},
    {"banner_id":2,"unit_id":7,"rateup":0},
    {"banner_id":2,"unit_id":9,"rateup":0},
    {"banner_id":2,"unit_id":18,"rateup":0},
    {"banner_id":2,"unit_id":19,"rateup":0},
    {"banner_id":2,"unit_id":20,"rateup":0},
    {"banner_id":2,"unit_id":22,"rateup":0},
    {"banner_id":2,"unit_id":23,"rateup":0},
    {"banner_id":2,"unit_id":24,"rateup":0},
    {"banner_id":2,"unit_id":27,"rateup":0},
    {"banner_id":2,"unit_id":30,"rateup":0},
    {"banner_id":2,"unit_id":31,"rateup":0},
    {"banner_id":2,"unit_id":34,"rateup":0},
    {"banner_id":2,"unit_id":37,"rateup":0},
    {"banner_id":2,"unit_id":38,"rateup":0},
    {"banner_id":2,"unit_id":40,"rateup":0},
    {"banner_id":2,"unit_id":41,"rateup":0},
    {"banner_id":2,"unit_id":45,"rateup":0},
    {"banner_id":2,"unit_id":48,"rateup":0},
    {"banner_id":2,"unit_id":6,"rateup":1}
]');

INSERT INTO pity (id, maximum, note, rarity, rateup_exists)
SELECT 
  json_extract(value, '$.id'), 
  json_extract(value, '$.maximum'),
  json_extract(value, '$.note'),
  json_extract(value, '$.rarity'),
  json_extract(value, '$.rateup_exists')
FROM json_each('[
    {"id":1,"maximum":10,"note":"Standard","rarity":"SR","rateup_exists":null},
    {"id":2,"maximum":90,"note":"Standard","rarity":"SSR","rateup_exists":null},
    {"id":3,"maximum":10,"note":"Limited","rarity":"SR","rateup_exists":null},
    {"id":4,"maximum":90,"note":"Limited","rarity":"SSR","rateup_exists":0}
]');

INSERT INTO banner_pity (banner_id, pity_id)
SELECT 
  json_extract(value, '$.banner_id'), 
  json_extract(value, '$.pity_id')
FROM json_each('[
    {"banner_id":1,"pity_id":1},
    {"banner_id":1,"pity_id":2},
    {"banner_id":2,"pity_id":3},
    {"banner_id":2,"pity_id":4}
]');

INSERT INTO currency (id, name)
SELECT 
  json_extract(value, '$.id'), 
  json_extract(value, '$.name')
FROM json_each('[
    {"id":1,"name":"silver fox coin"},
    {"id":2,"name":"gold fox coin"}
]');

INSERT INTO missions (id, description, reward, reset, currency_id)
SELECT 
  json_extract(value, '$.id'), 
  json_extract(value, '$.description'),
  json_extract(value, '$.reward'),
  json_extract(value, '$.reset'),
  json_extract(value, '$.currency_id')
FROM json_each('[
    {"id":1,"description":"Daily Login:","reward":1600, "reset": "Daily", "currency_id":1},
    {"id":2,"description":"Daily Login:","reward":160, "reset": "Daily", "currency_id":2},
    {"id":3,"description":"Daily Offering:","reward":800, "reset": "Daily", "currency_id":1},
    {"id":4,"description":"Daily Offering:","reward":160, "reset": "Daily", "currency_id":2}
]');

PRAGMA user_version = 2;

COMMIT;