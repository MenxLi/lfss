CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(256) UNIQUE NOT NULL,
    credential VARCHAR(256) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    max_storage INTEGER DEFAULT 1073741824,
    permission INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fmeta (
    url VARCHAR(1024) PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    file_id CHAR(32) NOT NULL,
    file_size INTEGER,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    permission INTEGER DEFAULT 0, 
    external BOOLEAN DEFAULT FALSE, 
    mime_type VARCHAR(256) DEFAULT 'application/octet-stream',
    FOREIGN KEY(owner_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS usize (
    user_id INTEGER PRIMARY KEY,
    size INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fmeta_url ON fmeta(url);

CREATE INDEX IF NOT EXISTS idx_user_username ON user(username);

CREATE INDEX IF NOT EXISTS idx_user_credential ON user(credential);

CREATE TABLE IF NOT EXISTS blobs.fdata (
    file_id CHAR(32) PRIMARY KEY,
    data BLOB
);