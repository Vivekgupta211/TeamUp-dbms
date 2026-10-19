DROP DATABASE IF EXISTS team_matching_system;
CREATE DATABASE team_matching_system;
USE team_matching_system;
CREATE TABLE STUDENT (
    Student_id INT AUTO_INCREMENT PRIMARY KEY,
    Student_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    Branch VARCHAR(100),
    Current_Year INT,
    Availability_Status VARCHAR(50) NOT NULL DEFAULT 'Available',
    Team_id INT NULL,
    CONSTRAINT chk_current_year CHECK (Current_Year BETWEEN 1 AND 6),
    CONSTRAINT chk_availability CHECK (Availability_Status IN ('Available', 'In Team', 'Busy'))
);

CREATE TABLE PROJECT (
    Project_id INT AUTO_INCREMENT PRIMARY KEY,
    Project_name VARCHAR(150) NOT NULL,
    Description TEXT,
    Category VARCHAR(100),
    Status VARCHAR(50) NOT NULL DEFAULT 'Open',
    Timeline VARCHAR(100),
    Is_official BOOLEAN NOT NULL DEFAULT FALSE,
    Created_by_student_id INT NULL,
    CONSTRAINT fk_project_creator
        FOREIGN KEY (Created_by_student_id) REFERENCES STUDENT(Student_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT chk_project_status CHECK (Status IN ('Open', 'In Progress', 'Closed'))
);

DELIMITER $$
CREATE TRIGGER trg_project_official_consistency_ins
BEFORE INSERT ON PROJECT
FOR EACH ROW
BEGIN
    IF NEW.Is_official = TRUE AND NEW.Created_by_student_id IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Official projects must not have a Created_by_student_id.';
    END IF;
    IF NEW.Is_official = FALSE AND NEW.Created_by_student_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Student-proposed projects must have a Created_by_student_id.';
    END IF;
END$$

CREATE TRIGGER trg_project_official_consistency_upd
BEFORE UPDATE ON PROJECT
FOR EACH ROW
BEGIN
    IF NEW.Is_official = TRUE AND NEW.Created_by_student_id IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Official projects must not have a Created_by_student_id.';
    END IF;
    IF NEW.Is_official = FALSE AND NEW.Created_by_student_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Student-proposed projects must have a Created_by_student_id.';
    END IF;
END$$
DELIMITER ;

CREATE TABLE TEAM (
    Team_id INT AUTO_INCREMENT PRIMARY KEY,
    Team_name VARCHAR(150) NOT NULL,
    team_status VARCHAR(50) NOT NULL DEFAULT 'Forming',
    max_members INT NOT NULL DEFAULT 5,
    Project_id INT NOT NULL,
    CONSTRAINT fk_team_project
        FOREIGN KEY (Project_id) REFERENCES PROJECT(Project_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT chk_max_members CHECK (max_members BETWEEN 1 AND 20),
    CONSTRAINT chk_team_status CHECK (team_status IN ('Forming', 'Active', 'Full', 'Closed'))
);

ALTER TABLE STUDENT
    ADD CONSTRAINT fk_student_team
        FOREIGN KEY (Team_id) REFERENCES TEAM(Team_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE;

CREATE TABLE SKILL (
    Skill_id INT AUTO_INCREMENT PRIMARY KEY,
    Skill_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE STUDENT_SKILL (
    Student_id INT NOT NULL,
    Skill_id INT NOT NULL,
    PRIMARY KEY (Student_id, Skill_id),
    CONSTRAINT fk_ss_student FOREIGN KEY (Student_id) REFERENCES STUDENT(Student_id) ON DELETE CASCADE,
    CONSTRAINT fk_ss_skill FOREIGN KEY (Skill_id) REFERENCES SKILL(Skill_id) ON DELETE CASCADE
);

CREATE TABLE TEAM_SKILL (
    Team_id INT NOT NULL,
    Skill_id INT NOT NULL,
    PRIMARY KEY (Team_id, Skill_id),
    CONSTRAINT fk_ts_team FOREIGN KEY (Team_id) REFERENCES TEAM(Team_id) ON DELETE CASCADE,
    CONSTRAINT fk_ts_skill FOREIGN KEY (Skill_id) REFERENCES SKILL(Skill_id) ON DELETE CASCADE
);

CREATE TABLE REQUEST_TO_JOIN (
    Request_id INT AUTO_INCREMENT PRIMARY KEY,
    Student_id INT NOT NULL,
    Team_id INT NOT NULL,
    Request_status VARCHAR(50) NOT NULL DEFAULT 'Pending',   -- Pending / Approved / Rejected
    Request_date DATE DEFAULT (CURRENT_DATE),
    CONSTRAINT fk_request_student FOREIGN KEY (Student_id) REFERENCES STUDENT(Student_id) ON DELETE CASCADE,
    CONSTRAINT fk_request_team FOREIGN KEY (Team_id) REFERENCES TEAM(Team_id) ON DELETE CASCADE,
    CONSTRAINT chk_request_status CHECK (Request_status IN ('Pending', 'Approved', 'Rejected'))
);

CREATE INDEX idx_student_team    ON STUDENT(Team_id);
CREATE INDEX idx_team_project    ON TEAM(Project_id);
CREATE INDEX idx_request_student ON REQUEST_TO_JOIN(Student_id);
CREATE INDEX idx_request_team    ON REQUEST_TO_JOIN(Team_id);
CREATE INDEX idx_project_creator ON PROJECT(Created_by_student_id);

DELIMITER $$
CREATE TRIGGER trg_no_duplicate_pending
BEFORE INSERT ON REQUEST_TO_JOIN
FOR EACH ROW
BEGIN
    DECLARE existing_pending INT;
    IF NEW.Request_status = 'Pending' THEN
        SELECT COUNT(*) INTO existing_pending
        FROM REQUEST_TO_JOIN
        WHERE Student_id = NEW.Student_id
          AND Team_id = NEW.Team_id
          AND Request_status = 'Pending';
        IF existing_pending > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'A pending request already exists for this student and team.';
        END IF;
    END IF;
END$$

-- No duplicate pending request on UPDATE
CREATE TRIGGER trg_no_duplicate_pending_upd
BEFORE UPDATE ON REQUEST_TO_JOIN
FOR EACH ROW
BEGIN
    IF NEW.Request_status = 'Pending' AND OLD.Request_status <> 'Pending' THEN
        IF EXISTS (
            SELECT 1
            FROM REQUEST_TO_JOIN
            WHERE Student_id = NEW.Student_id
              AND Team_id = NEW.Team_id
              AND Request_status = 'Pending'
              AND Request_id <> NEW.Request_id
        ) THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'A pending request already exists for this student and team.';
        END IF;
    END IF;
END$$

-- Puts the student on the team (checks team change, duplicate membership, capacity)
CREATE PROCEDURE sp_apply_approval(IN p_student_id INT, IN p_team_id INT)
BEGIN
    DECLARE current_members INT;
    DECLARE team_cap INT;
    DECLARE student_current_team INT;

    SELECT Team_id INTO student_current_team
    FROM STUDENT
    WHERE Student_id = p_student_id;

    IF student_current_team IS NOT NULL AND student_current_team <> p_team_id THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot approve: student already belongs to another team. Remove them first.';
    END IF;

    IF student_current_team = p_team_id THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Student is already a member of this team.';
    END IF;

    SELECT max_members INTO team_cap
    FROM TEAM
    WHERE Team_id = p_team_id
    FOR UPDATE;

    SELECT COUNT(*) INTO current_members
    FROM STUDENT
    WHERE Team_id = p_team_id;

    IF current_members >= team_cap THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot approve: team is already at max_members.';
    END IF;

    UPDATE STUDENT
    SET Team_id = p_team_id,
        Availability_Status = 'In Team'
    WHERE Student_id = p_student_id;

    -- Mark the team as Full when the last seat is taken
    IF current_members + 1 >= team_cap THEN
        UPDATE TEAM SET team_status = 'Full' WHERE Team_id = p_team_id;
    END IF;
END$$

CREATE TRIGGER trg_request_approved_on_update
BEFORE UPDATE ON REQUEST_TO_JOIN
FOR EACH ROW
BEGIN
    IF NEW.Request_status = 'Approved' AND OLD.Request_status <> 'Approved' THEN
        CALL sp_apply_approval(NEW.Student_id, NEW.Team_id);
    END IF;
END$$

CREATE TRIGGER trg_request_approved_on_insert
BEFORE INSERT ON REQUEST_TO_JOIN
FOR EACH ROW
BEGIN
    IF NEW.Request_status = 'Approved' THEN
        CALL sp_apply_approval(NEW.Student_id, NEW.Team_id);
    END IF;
END$$

CREATE TRIGGER trg_request_unapproved
AFTER UPDATE ON REQUEST_TO_JOIN
FOR EACH ROW
BEGIN
    IF OLD.Request_status = 'Approved' AND NEW.Request_status <> 'Approved' THEN
        UPDATE STUDENT
        SET Team_id = NULL,
            Availability_Status = 'Available'
        WHERE Student_id = NEW.Student_id
          AND Team_id = NEW.Team_id;

        UPDATE TEAM
        SET team_status = 'Forming'
        WHERE Team_id = NEW.Team_id
          AND team_status = 'Full';
    END IF;
END$$
DELIMITER ;

-- =========================================================
-- VIEWS (teams with no required skills are now included)
-- =========================================================

CREATE VIEW v_skill_match_detail AS
SELECT
    st.Student_id,
    t.Team_id,
    sk.Skill_name AS required_skill,
    CASE
        WHEN tsk.Skill_id IS NULL THEN 'No skills required'
        WHEN ss.Skill_id IS NOT NULL THEN 'Have'
        ELSE 'Missing'
    END AS status
FROM STUDENT st
CROSS JOIN TEAM t
LEFT JOIN TEAM_SKILL tsk ON tsk.Team_id = t.Team_id
LEFT JOIN SKILL sk ON sk.Skill_id = tsk.Skill_id
LEFT JOIN STUDENT_SKILL ss ON ss.Student_id = st.Student_id AND ss.Skill_id = tsk.Skill_id;

CREATE VIEW v_skill_match_summary AS
SELECT
    st.Student_id,
    t.Team_id,
    COUNT(DISTINCT tsk.Skill_id) AS total_required,
    COUNT(DISTINCT ss.Skill_id) AS matched,
    IF(COUNT(DISTINCT tsk.Skill_id) = 0,
       100.0,
       ROUND(COUNT(DISTINCT ss.Skill_id) / COUNT(DISTINCT tsk.Skill_id) * 100, 1)) AS match_percent
FROM STUDENT st
CROSS JOIN TEAM t
LEFT JOIN TEAM_SKILL tsk ON tsk.Team_id = t.Team_id
LEFT JOIN STUDENT_SKILL ss ON ss.Student_id = st.Student_id AND ss.Skill_id = tsk.Skill_id
GROUP BY st.Student_id, t.Team_id;

INSERT INTO SKILL (Skill_name) VALUES
('Python'), ('Java'), ('JavaScript'), ('React'), ('Node.js'),
('SQL'), ('Machine Learning'), ('UI/UX Design'), ('C++'), ('Figma'),
('Flutter'), ('Data Analysis'), ('Cloud (AWS/Azure)'), ('DevOps'), ('Cybersecurity');

INSERT INTO STUDENT (Student_name, email, Branch, Current_Year) VALUES
('Amit Sharma', 'amit123@example.com', 'CSE', 3),
('Priya Verma', 'priya245@example.com', 'EVD', 2),
('Rahul Jain', 'rahul34@example.com', 'CSE', 3),
('Aryan Malik', 'aryan999@example.com', 'ENC', 3);

INSERT INTO PROJECT (Project_name, Description, Category, Status, Timeline, Is_official, Created_by_student_id) VALUES
('Smart India Hackathon - Waste Management', 'Official SIH problem statement', 'Hackathon', 'Open', 'Sep-Nov 2026', TRUE, NULL),
('Campus Food Delivery App', 'Student-proposed idea', 'Web/App', 'Open', 'Flexible', FALSE, 2),
('DBMS Project', 'College project', 'College', 'Open', 'July to December', TRUE, NULL);

INSERT INTO TEAM (Team_name, max_members, Project_id) VALUES
('Code Ninjas', 4, 1),
('Byte Squad', 3, 2),
('Ace', 5, (SELECT Project_id FROM PROJECT WHERE Project_name = 'DBMS Project')),
('Solo Squad', 1, 3);   -- one-seat team, used to demo the "team is full" rule

INSERT INTO TEAM_SKILL (Team_id, Skill_id)
SELECT 1, Skill_id FROM SKILL WHERE Skill_name IN ('Python', 'Machine Learning', 'SQL');
INSERT INTO TEAM_SKILL (Team_id, Skill_id)
SELECT 2, Skill_id FROM SKILL WHERE Skill_name IN ('React', 'Node.js', 'UI/UX Design');

-- Student skills
INSERT INTO STUDENT_SKILL (Student_id, Skill_id)
SELECT 1, Skill_id FROM SKILL WHERE Skill_name IN ('Python', 'SQL');        
INSERT INTO STUDENT_SKILL (Student_id, Skill_id)
SELECT 2, Skill_id FROM SKILL WHERE Skill_name IN ('React', 'JavaScript'); 
INSERT INTO STUDENT_SKILL (Student_id, Skill_id)
SELECT 3, Skill_id FROM SKILL WHERE Skill_name IN ('Machine Learning');    

INSERT INTO REQUEST_TO_JOIN (Student_id, Team_id, Request_status) VALUES (1, 1, 'Pending');
UPDATE REQUEST_TO_JOIN SET Request_status = 'Approved' WHERE Student_id = 1 AND Team_id = 1;   -- Amit joins Code Ninjas

INSERT INTO REQUEST_TO_JOIN (Student_id, Team_id, Request_status) VALUES (3, 2, 'Rejected');   -- Rahul rejected by Byte Squad

INSERT INTO REQUEST_TO_JOIN (Student_id, Team_id, Request_status) VALUES (4, 4, 'Pending');
UPDATE REQUEST_TO_JOIN SET Request_status = 'Approved' WHERE Student_id = 4 AND Team_id = 4;   -- Aryan fills Solo Squad

INSERT INTO REQUEST_TO_JOIN (Student_id, Team_id, Request_status) VALUES (3, 4, 'Pending');    