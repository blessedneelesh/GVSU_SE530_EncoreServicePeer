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

-- 6. shows
CREATE TABLE shows (
    id             VARCHAR(36) PRIMARY KEY,
    title          VARCHAR(200) NOT NULL,
    venue          VARCHAR(200) NOT NULL,
    city           VARCHAR(100) NOT NULL,
    state          VARCHAR(50)  NOT NULL,
    date           DATE         NOT NULL,
    time           TIME         NOT NULL,
    description    TEXT         NOT NULL,
    genre          VARCHAR(50)  NOT NULL,
    organizer_id   VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
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
    show_id    VARCHAR(36) NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    user_id    VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    seats      INTEGER     NOT NULL CHECK (seats > 0 AND seats <= 4),
    created_at DATE        NOT NULL DEFAULT CURRENT_DATE
);

-- 8. comments
CREATE TABLE comments (
    id         VARCHAR(36) PRIMARY KEY,
    show_id    VARCHAR(36) NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    user_id    VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text       TEXT        NOT NULL,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Indexes (For faster querying)
-- -----------------------------------------------------------------------------
CREATE INDEX idx_user_roles_user_id     ON user_roles(user_id);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_shows_organizer_id     ON shows(organizer_id);
CREATE INDEX idx_shows_date             ON shows(date);
CREATE INDEX idx_reservations_show_id   ON reservations(show_id);
CREATE INDEX idx_reservations_user_id   ON reservations(user_id);
CREATE INDEX idx_comments_show_id       ON comments(show_id);
CREATE INDEX idx_comments_user_id       ON comments(user_id);

-- -------------------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------------------
----------------------------------------------Insert query---------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------------------
-- 1. users (ids 1-5)
INSERT INTO users (name, username, email, password_hash, is_active, bio, joined_date, last_login_at) VALUES
('Alice Johnson', 'alicej', 'alice@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoMQ', TRUE, 'Live music lover and part-time promoter.', '2026-01-15', '2026-09-30 18:42:00+00'),
('Brian Smith',   'brians', 'brian@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoMg', TRUE, 'Jazz fan. Organizes small club nights.', '2026-02-03', '2026-09-29 21:10:00+00'),
('Carla Gomez',   'carlag', 'carla@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoMw', TRUE, 'Comedy nights every month.', '2026-03-21', '2026-10-01 09:05:00+00'),
('David Lee',     'davidl', 'david@example.com', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoNA', TRUE, 'Classical music and theater.', '2026-05-10', NULL),
('Emma Wilson',   'emmaw',  'emma@example.com',  '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$ZHVtbXloYXNoNQ', TRUE, 'Always looking for a good show.', '2026-07-08', '2026-09-28 20:30:00+00');

-- 2. concerts (ids 1-5)
INSERT INTO concerts (title, venue, city, state, date, time, description, genre, owner_id, capacity, reserved_count, image_url, cancelled, created_at) VALUES
('Midnight Riff Live',   'The Roxy Hall',        'Chicago',   'IL', '2026-11-14', '20:00', 'An evening of high-energy rock with local bands.',   'Rock',      1, 100, 6, 'https://example.com/images/midnight-riff.jpg',   FALSE, '2026-09-01'),
('Blue Note Sessions',   'Harbor Jazz Club',     'Milwaukee', 'WI', '2026-11-21', '19:30', 'Intimate jazz night with a live quartet.',            'Jazz',      1,  50, 3, 'https://example.com/images/blue-note.jpg',       FALSE, '2026-09-05'),
('Laugh Out Loud',       'Downtown Comedy Loft', 'Detroit',   'MI', '2026-12-05', '18:00', 'Stand-up comedy featuring five touring comedians.',   'Comedy',    2, 200, 2, NULL,                                            FALSE, '2026-09-10'),
('Winter Symphony Gala', 'Grand Opera House',    'Cleveland', 'OH', '2026-12-12', '21:00', 'Seasonal classical program performed by a full orchestra.', 'Classical', 3,  80, 1, 'https://example.com/images/winter-symphony.jpg', FALSE, '2026-09-15'),
('Stage Lights: Hamlet', 'City Theater',         'Madison',   'WI', '2026-10-25', '19:00', 'Modern staging of the classic play.',                 'Theater',   4, 150, 0, NULL,                                            TRUE,  '2026-09-20');

-- 3. reservations (seats add up to each show's reserved_count)
INSERT INTO reservations (show_id, user_id, seats, created_at) VALUES
(1, 2, 2, '2026-09-12'),
(1, 3, 4, '2026-09-14'),
(2, 4, 3, '2026-09-18'),
(3, 5, 2, '2026-09-22'),
(4, 1, 1, '2026-09-25');

-- 4. comments
INSERT INTO comments (show_id, user_id, text, created_at) VALUES
(1, 2, 'Great lineup, cannot wait for this one!',      '2026-09-12 10:15:00+00'),
(1, 3, 'Is there parking near the venue?',             '2026-09-14 16:40:00+00'),
(2, 4, 'Loved the quartet last year, booking again.',  '2026-09-18 12:05:00+00'),
(3, 5, 'Which comedians are on the bill?',             '2026-09-22 19:30:00+00'),
(5, 1, 'Sad to see this one cancelled. Hope it returns.', '2026-09-26 08:20:00+00');