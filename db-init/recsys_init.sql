-- SQL Template to create tables for recsys database 
CREATE DATABASE IF NOT EXISTS recsys; 
USE recsys;

-- Table: chat_log 
CREATE TABLE IF NOT EXISTS chat_log ( 
    id INT(11) NOT NULL AUTO_INCREMENT, 
    prompt TEXT NOT NULL, 
    response TEXT NOT NULL, 
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id) 
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: Projects 
CREATE TABLE IF NOT EXISTS Projects (
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
    PRIMARY KEY (_id) 
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: Tags 
CREATE TABLE IF NOT EXISTS Tags (
     _id VARCHAR(255) NOT NULL, 
     name VARCHAR(255) NOT NULL, 
     type VARCHAR(50) DEFAULT NULL, 
     createdAt DATETIME DEFAULT NULL, 
     updatedAt DATETIME DEFAULT NULL, 
     PRIMARY KEY (_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: Users 
CREATE TABLE IF NOT EXISTS Users (
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
    PRIMARY KEY (_id) 
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;