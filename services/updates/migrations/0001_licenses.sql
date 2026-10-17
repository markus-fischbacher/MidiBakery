-- MidiBakery licenses. Keys are stored only as SHA-256 of the normalized key (MB-XXXX-XXXX-XXXX-XXXX);
-- computers only as the app's salted machine hash.
CREATE TABLE licenses (
  key_hash      TEXT PRIMARY KEY,
  id            TEXT NOT NULL UNIQUE,           -- shown in tokens and support mails, e.g. L-2026-0001
  name          TEXT NOT NULL DEFAULT '',       -- licensee as shown in the app
  email         TEXT NOT NULL DEFAULT '',
  seats         INTEGER NOT NULL DEFAULT 2,
  updates_until TEXT NOT NULL,                  -- ISO date; renewals move it
  created       TEXT NOT NULL,
  revoked       INTEGER NOT NULL DEFAULT 0,     -- refunds, chargebacks
  source        TEXT NOT NULL DEFAULT ''        -- order id at the merchant of record
);

CREATE TABLE activations (
  key_hash   TEXT NOT NULL REFERENCES licenses(key_hash),
  machine    TEXT NOT NULL,
  activated  TEXT NOT NULL,
  last_seen  TEXT NOT NULL,
  PRIMARY KEY (key_hash, machine)
);

CREATE TABLE trials (
  machine  TEXT PRIMARY KEY,
  started  TEXT NOT NULL
);
