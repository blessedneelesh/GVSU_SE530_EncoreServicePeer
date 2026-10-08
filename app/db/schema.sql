-- -----------------------------------------------------------------------------
-- DDL Query
-- -----------------------------------------------------------------------------

-- 1. roles
CREATE TABLE roles (
    id          VARCHAR(36) PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

-- 2. users
CREATE TABLE users (
    id            VARCHAR(36) PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    bio           TEXT         NOT NULL DEFAULT '',
    joined_date   DATE         NOT NULL DEFAULT CURRENT_DATE,
    last_login_at TIMESTAMP
);

-- 3. user_roles (Junction table connecting users to roles)
CREATE TABLE user_roles (
    user_id     VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     VARCHAR(36) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- 4. refresh_tokens (For maintaining active sessions)
CREATE TABLE refresh_tokens (
    id         VARCHAR(36) PRIMARY KEY,
    user_id    VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP   NOT NULL,
    revoked    BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_agent VARCHAR(255)
);

-- 5. revoked_tokens (Blocklist for logged-out tokens)
CREATE TABLE revoked_tokens (
    jti        VARCHAR(36) PRIMARY KEY,
    user_id    VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP   NOT NULL,
    revoked_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. concerts
CREATE TABLE concerts (
    id             VARCHAR(36) PRIMARY KEY,
    title          VARCHAR(200) NOT NULL,
    venue          VARCHAR(200) NOT NULL,
    city           VARCHAR(100) NOT NULL,
    state          VARCHAR(50)  NOT NULL,
    date           DATE         NOT NULL,
    time           TIME         NOT NULL,
    description    TEXT         NOT NULL,
    genre          VARCHAR(50)  NOT NULL,
    owner_id       VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    capacity       INTEGER      NOT NULL CHECK (capacity > 0),
    reserved_count INTEGER      NOT NULL DEFAULT 0,
    image_url      TEXT,
    cancelled      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at     DATE         NOT NULL DEFAULT CURRENT_DATE,
    mood           VARCHAR(20)  NOT NULL CHECK (mood IN ('Sad', 'Angry', 'Happy')),
    CONSTRAINT chk_reserved_count CHECK (reserved_count >= 0 AND reserved_count <= capacity)
);

-- 7. reservations
CREATE TABLE reservations (
    id         VARCHAR(36) PRIMARY KEY,
    concert_id    VARCHAR(36) NOT NULL REFERENCES concerts(id) ON DELETE CASCADE,
    user_id    VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    seats      INTEGER     NOT NULL CHECK (seats > 0 AND seats <= 4),
    created_at DATE        NOT NULL DEFAULT CURRENT_DATE
);

-- 8. comments
CREATE TABLE comments (
    id         VARCHAR(36) PRIMARY KEY,
    concert_id    VARCHAR(36) NOT NULL REFERENCES concerts(id) ON DELETE CASCADE,
    user_id    VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text       TEXT        NOT NULL,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Indexes (For faster querying)
-- -----------------------------------------------------------------------------
CREATE INDEX idx_user_roles_user_id  ON user_roles(user_id);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_concerts_owner_id   ON concerts(owner_id);
CREATE INDEX idx_concerts_date       ON concerts(date);
CREATE INDEX idx_reservations_concert_id   ON reservations(concert_id);
CREATE INDEX idx_reservations_user_id   ON reservations(user_id);
CREATE INDEX idx_comments_concert_id       ON comments(concert_id);
CREATE INDEX idx_comments_user_id       ON comments(user_id);

-- -----------------------------------------------------------------------------
-- Mock Data Insert Query
-- -----------------------------------------------------------------------------

-- 1. users (Using standard 36-character UUIDs for IDs)
INSERT INTO users (id, name, username, email, password_hash, is_active, bio, joined_date, last_login_at) VALUES
('11111111-1111-1111-1111-111111111111', 'Alice Johnson', 'alicej', 'alice@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoMQ', TRUE, 'Live music lover and part-time promoter.', '2026-01-15', '2026-09-30 18:42:00+00'),
('22222222-2222-2222-2222-222222222222', 'Brian Smith',   'brians', 'brian@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoMg', TRUE, 'Jazz fan. Organizes small club nights.', '2026-02-03', '2026-09-29 21:10:00+00'),
('33333333-3333-3333-3333-333333333333', 'Carla Gomez',   'carlag', 'carla@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoMw', TRUE, 'Comedy nights every month.', '2026-03-21', '2026-10-01 09:05:00+00'),
('44444444-4444-4444-4444-444444444444', 'David Lee',     'davidl', 'david@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoNA', TRUE, 'Classical music and theater.', '2026-05-10', NULL),
('55555555-5555-5555-5555-555555555555', 'Emma Wilson',   'emmaw',  'emma@example.com',  '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoNQ', TRUE, 'Always looking for a good show.', '2026-07-08', '2026-09-28 20:30:00+00');

-- 2. concerts (owner_id maps to user UUIDs, mood column included)
INSERT INTO concerts (id, title, venue, city, state, date, time, description, genre, owner_id, capacity, reserved_count, image_url, cancelled, created_at, mood) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Midnight Riff Live',   'The Roxy Hall',        'Chicago',   'IL', '2026-11-14', '20:00', 'An evening of high-energy rock with local bands.',   'Rock',      '11111111-1111-1111-1111-111111111111', 100, 6, 'https://example.com/images/midnight-riff.jpg',   FALSE, '2026-09-01', 'Happy'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Blue Note Sessions',   'Harbor Jazz Club',     'Milwaukee', 'WI', '2026-11-21', '19:30', 'Intimate jazz night with a live quartet.',           'Jazz',      '11111111-1111-1111-1111-111111111111', 50,  3, 'https://example.com/images/blue-note.jpg',       FALSE, '2026-09-05', 'Sad'),
('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Laugh Out Loud',       'Downtown Comedy Loft', 'Detroit',   'MI', '2026-12-05', '18:00', 'Stand-up comedy featuring five touring comedians.',   'Comedy',    '22222222-2222-2222-2222-222222222222', 200, 2, NULL,                                           FALSE, '2026-09-10', 'Happy'),
('dddddddd-dddd-dddd-dddd-dddddddddddd', 'Winter Symphony Gala', 'Grand Opera House',    'Cleveland', 'OH', '2026-12-12', '21:00', 'Seasonal classical program performed by a full orchestra.', 'Classical', '33333333-3333-3333-3333-333333333333', 80,  1, 'https://example.com/images/winter-symphony.jpg', FALSE, '2026-09-15', 'Sad'),
('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'Stage Lights: Hamlet', 'City Theater',         'Madison',   'WI', '2026-10-25', '19:00', 'Modern staging of the classic play.',                 'Theater',   '44444444-4444-4444-4444-444444444444', 150, 0, NULL,                                           TRUE,  '2026-09-20', 'Angry');

-- 3. reservations (concert_id and user_id map to UUIDs)
INSERT INTO reservations (id, concert_id, user_id, seats, created_at) VALUES
('r1111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '22222222-2222-2222-2222-222222222222', 2, '2026-09-12'),
('r2222222-2222-2222-2222-222222222222', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '33333333-3333-3333-3333-333333333333', 4, '2026-09-14'),
('r3333333-3333-3333-3333-333333333333', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '44444444-4444-4444-4444-444444444444', 3, '2026-09-18'),
('r4444444-4444-4444-4444-444444444444', 'cccccccc-cccc-cccc-cccc-cccccccccccc', '55555555-5555-5555-5555-555555555555', 2, '2026-09-22'),
('r5555555-5555-5555-5555-555555555555', 'dddddddd-dddd-dddd-dddd-dddddddddddd', '11111111-1111-1111-1111-111111111111', 1, '2026-09-25');

-- 4. comments
INSERT INTO comments (id, concert_id, user_id, text, created_at) VALUES
('c1111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '22222222-2222-2222-2222-222222222222', 'Great lineup, cannot wait for this one!',       '2026-09-12 10:15:00+00'),
('c2222222-2222-2222-2222-222222222222', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '33333333-3333-3333-3333-333333333333', 'Is there parking near the venue?',              '2026-09-14 16:40:00+00'),
('c3333333-3333-3333-3333-333333333333', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '44444444-4444-4444-4444-444444444444', 'Loved the quartet last year, booking again.',   '2026-09-18 12:05:00+00'),
('c4444444-4444-4444-4444-444444444444', 'cccccccc-cccc-cccc-cccc-cccccccccccc', '55555555-5555-5555-5555-555555555555', 'Which comedians are on the bill?',              '2026-09-22 19:30:00+00'),
('c5555555-5555-5555-5555-555555555555', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '11111111-1111-1111-1111-111111111111', 'Sad to see this one cancelled. Hope it returns.', '2026-09-26 08:20:00+00');