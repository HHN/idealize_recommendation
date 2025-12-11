-- =============================================================================
-- SQL Template to create tables for recsys database with Vector Embeddings
-- =============================================================================
-- This schema extends the base recsys database with vector embedding support
-- for RAG (Retrieval Augmented Generation) functionality.
--
-- Key Features:
-- - Vector embeddings stored as JSON arrays (1536 dimensions for OpenAI)
-- - Automatic tracking of embedding model version and update timestamps
-- - Flags to indicate when embeddings need regeneration
-- - Optimized indexes for embedding queries
-- - Triggers to invalidate embeddings when content changes
--
-- Created: November 29, 2025
-- Based on: recsys_init.sql
-- =============================================================================

CREATE DATABASE IF NOT EXISTS recsys; 
USE recsys;

-- =============================================================================
-- Table: chat_log
-- =============================================================================
-- Stores all chat interactions for analytics and debugging
-- No changes from original schema
CREATE TABLE IF NOT EXISTS chat_log ( 
    id INT(11) NOT NULL AUTO_INCREMENT, 
    prompt TEXT NOT NULL, 
    response TEXT NOT NULL, 
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id) 
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Add index for timestamp-based queries (useful for analytics)
CREATE INDEX idx_chat_timestamp ON chat_log(timestamp);


-- =============================================================================
-- Table: Projects (Extended with Vector Embeddings)
-- =============================================================================
-- Core table for project data with integrated vector embeddings for semantic search
CREATE TABLE IF NOT EXISTS Projects (
    -- Original fields
    _id VARCHAR(255) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    description TEXT DEFAULT NULL, 
    tags LONGTEXT DEFAULT NULL, 
    owner_id VARCHAR(255) DEFAULT NULL, 
    isDraft TINYINT(1) DEFAULT NULL, 
    links LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(links)), 
    attachments LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(attachments)), 
    createdAt DATETIME DEFAULT NULL, 
    updatedAt DATETIME DEFAULT NULL,
    
    -- Vector Embedding fields (NEW)
    -- -------------------------
    -- embedding: JSON array of 1536 float values (OpenAI text-embedding-3-small)
    -- Stores the vector representation of the project for semantic similarity search
    embedding JSON DEFAULT NULL,
    
    -- embedding_model: Tracks which model generated the embedding (e.g., 'text-embedding-3-small')
    -- Important for versioning and debugging
    embedding_model VARCHAR(100) DEFAULT NULL,
    
    -- embedding_created_at: Timestamp when the embedding was first generated
    embedding_created_at DATETIME DEFAULT NULL,
    
    -- embedding_updated_at: Timestamp of the last embedding update
    -- Used to determine if embeddings need regeneration
    embedding_updated_at DATETIME DEFAULT NULL,
    
    -- needs_embedding_update: Flag to indicate content changed and embedding is stale
    -- Set to TRUE by triggers when title/description/tags change
    -- Set to FALSE after embedding is regenerated
    needs_embedding_update TINYINT(1) DEFAULT 1,
    
    PRIMARY KEY (_id),
    
    -- Check constraint to ensure embedding is valid JSON if present
    CHECK (embedding IS NULL OR JSON_VALID(embedding))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Indexes for optimized queries
-- ------------------------------
-- Index for finding projects that need embedding updates
CREATE INDEX idx_projects_needs_embedding ON Projects(needs_embedding_update);

-- Index for draft status (commonly filtered)
CREATE INDEX idx_projects_draft ON Projects(isDraft);

-- Composite index for common query pattern: non-draft projects
CREATE INDEX idx_projects_search_ready ON Projects(isDraft, needs_embedding_update);


-- =============================================================================
-- Table: Users (Extended with Vector Embeddings)
-- =============================================================================
-- User data with embeddings for user-project matching and recommendations
CREATE TABLE IF NOT EXISTS Users (
    -- Original fields
    _id VARCHAR(255) NOT NULL, 
    firstName VARCHAR(100) DEFAULT NULL, 
    lastName VARCHAR(100) DEFAULT NULL, 
    email VARCHAR(255) NOT NULL, 
    username VARCHAR(100) NOT NULL, 
    status TINYINT(1) DEFAULT NULL, 
    userType VARCHAR(50) DEFAULT NULL, 
    interestedTags LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(interestedTags)), 
    interestedCourses LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(interestedCourses)), 
    studyPrograms LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(studyPrograms)), 
    isBlockedByAdmin TINYINT(1) DEFAULT NULL, 
    createdAt DATETIME DEFAULT NULL, 
    updatedAt DATETIME DEFAULT NULL,
    
    -- Vector Embedding fields (NEW)
    -- -------------------------
    -- Embedding based on user's interests, tags, and preferences
    -- Used for finding projects that match user interests
    embedding JSON DEFAULT NULL,
    embedding_model VARCHAR(100) DEFAULT NULL,
    embedding_created_at DATETIME DEFAULT NULL,
    embedding_updated_at DATETIME DEFAULT NULL,
    
    -- Flag to indicate user profile changed and embedding needs update
    needs_embedding_update TINYINT(1) DEFAULT 1,
    
    PRIMARY KEY (_id),
    CHECK (embedding IS NULL OR JSON_VALID(embedding))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Indexes for Users table
-- -----------------------
CREATE INDEX idx_users_needs_embedding ON Users(needs_embedding_update);
CREATE INDEX idx_users_email ON Users(email);
CREATE INDEX idx_users_username ON Users(username);


-- =============================================================================
-- Table: Tags
-- =============================================================================
-- No changes from original schema
-- Tags don't need embeddings as they're used within project/user embeddings
CREATE TABLE IF NOT EXISTS Tags (
    _id VARCHAR(255) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    type VARCHAR(50) DEFAULT NULL, 
    createdAt DATETIME DEFAULT NULL, 
    updatedAt DATETIME DEFAULT NULL, 
    PRIMARY KEY (_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE INDEX idx_tags_name ON Tags(name);
CREATE INDEX idx_tags_type ON Tags(type);


-- =============================================================================
-- TRIGGERS: Automatic Embedding Invalidation
-- =============================================================================
-- These triggers automatically mark embeddings as needing update when
-- relevant content changes. This ensures embeddings stay synchronized with data.
--
-- Note: Actual embedding generation must be done by the Python application
-- (rag_chatbot.py) as it requires OpenAI API calls. These triggers only
-- set the flag to indicate regeneration is needed.
-- =============================================================================

-- Trigger: Projects - Mark embedding as stale on content updates
-- ---------------------------------------------------------------
DELIMITER $$

CREATE TRIGGER projects_before_update
BEFORE UPDATE ON Projects
FOR EACH ROW
BEGIN
    -- Check if any content that affects embeddings has changed
    IF (OLD.title != NEW.title 
        OR OLD.description != NEW.description 
        OR OLD.tags != NEW.tags) THEN
        
        -- Mark embedding as needing update
        SET NEW.needs_embedding_update = 1;
        
        -- Update the general updatedAt timestamp
        SET NEW.updatedAt = NOW();
    END IF;
END$$

DELIMITER ;


-- Trigger: Projects - Initialize flags for new projects
-- -------------------------------------------------------
DELIMITER $$

CREATE TRIGGER projects_before_insert
BEFORE INSERT ON Projects
FOR EACH ROW
BEGIN
    -- New projects need embedding generation
    SET NEW.needs_embedding_update = 1;
    
    -- Initialize timestamps if not provided
    IF NEW.createdAt IS NULL THEN
        SET NEW.createdAt = NOW();
    END IF;
    
    IF NEW.updatedAt IS NULL THEN
        SET NEW.updatedAt = NOW();
    END IF;
END$$

DELIMITER ;


-- Trigger: Users - Mark embedding as stale on profile updates
-- ------------------------------------------------------------
DELIMITER $$

CREATE TRIGGER users_before_update
BEFORE UPDATE ON Users
FOR EACH ROW
BEGIN
    -- Check if any profile data that affects embeddings has changed
    IF (OLD.interestedTags != NEW.interestedTags 
        OR OLD.interestedCourses != NEW.interestedCourses 
        OR OLD.studyPrograms != NEW.studyPrograms
        OR OLD.firstName != NEW.firstName
        OR OLD.lastName != NEW.lastName) THEN
        
        -- Mark embedding as needing update
        SET NEW.needs_embedding_update = 1;
        
        -- Update the general updatedAt timestamp
        SET NEW.updatedAt = NOW();
    END IF;
END$$

DELIMITER ;


-- Trigger: Users - Initialize flags for new users
-- ------------------------------------------------
DELIMITER $$

CREATE TRIGGER users_before_insert
BEFORE INSERT ON Users
FOR EACH ROW
BEGIN
    -- New users need embedding generation
    SET NEW.needs_embedding_update = 1;
    
    -- Initialize timestamps if not provided
    IF NEW.createdAt IS NULL THEN
        SET NEW.createdAt = NOW();
    END IF;
    
    IF NEW.updatedAt IS NULL THEN
        SET NEW.updatedAt = NOW();
    END IF;
END$$

DELIMITER ;


-- =============================================================================
-- STORED PROCEDURES: Helper Functions for Embedding Management
-- =============================================================================

-- Procedure: Mark embedding as updated
-- -------------------------------------
-- Call this after successfully generating and storing an embedding
DELIMITER $$

CREATE PROCEDURE mark_project_embedding_updated(
    IN project_id VARCHAR(255),
    IN model_name VARCHAR(100)
)
BEGIN
    UPDATE Projects
    SET needs_embedding_update = 0,
        embedding_model = model_name,
        embedding_updated_at = NOW(),
        embedding_created_at = COALESCE(embedding_created_at, NOW())
    WHERE _id = project_id;
END$$

CREATE PROCEDURE mark_user_embedding_updated(
    IN user_id VARCHAR(255),
    IN model_name VARCHAR(100)
)
BEGIN
    UPDATE Users
    SET needs_embedding_update = 0,
        embedding_model = model_name,
        embedding_updated_at = NOW(),
        embedding_created_at = COALESCE(embedding_created_at, NOW())
    WHERE _id = user_id;
END$$

DELIMITER ;


-- Procedure: Get projects needing embedding updates
-- --------------------------------------------------
DELIMITER $$

CREATE PROCEDURE get_projects_needing_embeddings()
BEGIN
    SELECT _id, title, description, tags, createdAt
    FROM Projects
    WHERE needs_embedding_update = 1
      AND isDraft = 0
    ORDER BY createdAt DESC;
END$$

CREATE PROCEDURE get_users_needing_embeddings()
BEGIN
    SELECT _id, firstName, lastName, interestedTags, 
           interestedCourses, studyPrograms
    FROM Users
    WHERE needs_embedding_update = 1
      AND isBlockedByAdmin = 0
    ORDER BY createdAt DESC;
END$$

DELIMITER ;


-- Procedure: Get embedding statistics
-- ------------------------------------
-- Useful for monitoring and debugging
DELIMITER $$

CREATE PROCEDURE get_embedding_statistics()
BEGIN
    SELECT 
        'Projects' as entity_type,
        COUNT(*) as total_count,
        SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embeddings,
        SUM(CASE WHEN needs_embedding_update = 1 THEN 1 ELSE 0 END) as needs_update,
        SUM(CASE WHEN embedding IS NOT NULL AND needs_embedding_update = 0 THEN 1 ELSE 0 END) as up_to_date
    FROM Projects
    WHERE isDraft = 0
    
    UNION ALL
    
    SELECT 
        'Users' as entity_type,
        COUNT(*) as total_count,
        SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embeddings,
        SUM(CASE WHEN needs_embedding_update = 1 THEN 1 ELSE 0 END) as needs_update,
        SUM(CASE WHEN embedding IS NOT NULL AND needs_embedding_update = 0 THEN 1 ELSE 0 END) as up_to_date
    FROM Users
    WHERE isBlockedByAdmin = 0;
END$$

DELIMITER ;


-- =============================================================================
-- VIEWS: Convenient access to embedding-related data
-- =============================================================================

-- View: Projects ready for semantic search
-- -----------------------------------------
CREATE OR REPLACE VIEW projects_with_embeddings AS
SELECT 
    _id,
    title,
    description,
    tags,
    owner_id,
    createdAt,
    updatedAt,
    embedding_model,
    embedding_updated_at,
    JSON_LENGTH(embedding) as embedding_dimension
FROM Projects
WHERE isDraft = 0
  AND embedding IS NOT NULL
  AND needs_embedding_update = 0;


-- View: Users ready for recommendations
-- --------------------------------------
CREATE OR REPLACE VIEW users_with_embeddings AS
SELECT 
    _id,
    firstName,
    lastName,
    email,
    username,
    interestedTags,
    embedding_model,
    embedding_updated_at,
    JSON_LENGTH(embedding) as embedding_dimension
FROM Users
WHERE isBlockedByAdmin = 0
  AND embedding IS NOT NULL
  AND needs_embedding_update = 0;


-- =============================================================================
-- USAGE EXAMPLES AND DOCUMENTATION
-- =============================================================================

/*
USAGE EXAMPLES:
===============

1. After generating embeddings in Python, mark them as updated:
   
   CALL mark_project_embedding_updated('673f4a1e2c1b3a001f8d9e21', 'text-embedding-3-small');

2. Get list of projects that need embedding updates:
   
   CALL get_projects_needing_embeddings();

3. Check embedding statistics:
   
   CALL get_embedding_statistics();

4. Query projects with valid embeddings:
   
   SELECT * FROM projects_with_embeddings;

5. Manually force embedding regeneration for a project:
   
   UPDATE Projects SET needs_embedding_update = 1 WHERE _id = 'project_id';


INTEGRATION WITH rag_chatbot.py:
=================================

The Python application should:

1. After syncing from MongoDB API:
   - Check which projects/users have needs_embedding_update = 1
   - Generate embeddings for those entries
   - Store embeddings in the embedding column
   - Call mark_project_embedding_updated() or mark_user_embedding_updated()

2. On startup:
   - Load projects/users with embeddings using the views
   - Skip embedding generation for entries where needs_embedding_update = 0

3. Handle updates:
   - Triggers automatically set needs_embedding_update = 1 when content changes
   - Background job or next sync can regenerate stale embeddings


PERFORMANCE NOTES:
==================

- Embeddings are 1536 floats = ~12KB per project as JSON
- For 10,000 projects: ~120MB of embedding data
- Consider periodic cleanup of old embeddings if using multiple model versions
- For >100k projects, consider migrating to specialized vector database (Pinecone, Weaviate, etc.)


MIGRATION FROM EXISTING DATABASE:
==================================

If you already have a recsys database without embeddings:

ALTER TABLE Projects 
ADD COLUMN embedding JSON DEFAULT NULL,
ADD COLUMN embedding_model VARCHAR(100) DEFAULT NULL,
ADD COLUMN embedding_created_at DATETIME DEFAULT NULL,
ADD COLUMN embedding_updated_at DATETIME DEFAULT NULL,
ADD COLUMN needs_embedding_update TINYINT(1) DEFAULT 1;

-- Then run the CREATE INDEX and CREATE TRIGGER statements above
*/

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
