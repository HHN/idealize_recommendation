# Idealize-Recommendation

This is a project that integrates a chatbot with a MySQL database using Langchain and OpenAI's GPT-4-turbo model. The project is designed to interact with a database of projects, users, and tags, and respond with specific fields based on the user's prompt.

Recommendation system for projects and users:
The recommendation system is an important feature of the project. Tailored recommendations are generated based on the interests, preferences and profile information of the users and the requirements of the projects.
Use case - recommendation system:

The system uses an LLM-based model to understand the user's query. Based on this, the database is searched and suitable projects/users are returned.
Example: A student asks the recommendation system for projects in the field of “data science” and receives suggestions for projects that cover this subject area. At the same time, the system can provide recommendations for professors who have similar interests or are supervised for relevant projects.

## Acknowledgements
This project was developed as part of the InduKo Project, funded by Stiftung Innovation in der Hochschullehre.
We also acknowledge the support from students, faculty and contributors who have been part of this collaborative effort.

For more iniformation about the InduKo research project, visit the official  website: https://www.hs-heilbronn.de/en/projekt-induko-2cab68e84c21b797

For more iniformation about the IdeaLize project platform, visit the official  website: https://www.hs-heilbronn.de/en/idealize-12f73ca0754864df

## License 

This project is licensed under Apache License, Version 2.0. Copyright 2024 Prof. Dr. Mahsa Fischer, Hochschule Heilbronn

## Licenses for Third-Party Libraries
This project includes several third-party libraries under open-source licenses. Key libraries include:

- [FastAPI](https://fastapi.tiangolo.com/) (MIT License)
- [Pydantic](https://pydantic-docs.helpmanual.io/) (MIT License)
- [Requests](https://requests.readthedocs.io/) (Apache 2.0 License)
- [PyMySQL](https://pypi.org/project/PyMySQL/) (MIT License)
- [Uvicorn](https://www.uvicorn.org/) (BSD-3-Clause License)
- [Langchain](https://github.com/langchain-ai/langchain/blob/master/LICENSE) (MIT License)
- [OpenAI](https://github.com/openai/openai-python) (Apache 2.0 License)

## Installation and Setup

### Prerequisites

- You need the idealize_server project running for this project to work
- Python 3.10+
- MySQL or MariaDB installed locally
- MySQL client (`pymysql`)

### Create apikey.py
Create a file named apikey.py in the project root directory and add your OpenAI API key in it:
`APIKEY = 'your-openai-api-key'`

### Create bearer_token.py
Create a file named bearer_token.py in the project root directory and add your bearer_token from your idealize_server in it:
`TOKEN = 'your-bearer-token'`

### Install the requirements
Run the following command to install the necessary Python dependencies:
`pip install -r requirements.txt`


## MySQL Database Setup
Create a new MySQL database with your preferred name.
Use the following SQL to create the necessary tables:


-- SQL Template to create tables for `recsys` database
CREATE DATABASE IF NOT EXISTS `recsys`;
USE `recsys`;

-- Table: chat_log
CREATE TABLE IF NOT EXISTS `chat_log` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `prompt` TEXT NOT NULL,
  `response` TEXT NOT NULL,
  `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: Projects
CREATE TABLE IF NOT EXISTS `Projects` (
  `_id` VARCHAR(255) NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `description` TEXT DEFAULT NULL,
  `tags` LONGTEXT DEFAULT NULL,
  `owner_id` VARCHAR(255) DEFAULT NULL,
  `isDraft` TINYINT(1) DEFAULT NULL,
  `links` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(`links`)),
  `attachments` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(`attachments`)),
  `createdAt` DATETIME DEFAULT NULL,
  `updatedAt` DATETIME DEFAULT NULL,
  PRIMARY KEY (`_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: Tags
CREATE TABLE IF NOT EXISTS `Tags` (
  `_id` VARCHAR(255) NOT NULL,
  `name` VARCHAR(255) NOT NULL,
  `type` VARCHAR(50) DEFAULT NULL,
  `createdAt` DATETIME DEFAULT NULL,
  `updatedAt` DATETIME DEFAULT NULL,
  PRIMARY KEY (`_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: Users
CREATE TABLE IF NOT EXISTS `Users` (
  `_id` VARCHAR(255) NOT NULL,
  `firstName` VARCHAR(100) DEFAULT NULL,
  `lastName` VARCHAR(100) DEFAULT NULL,
  `email` VARCHAR(255) NOT NULL,
  `username` VARCHAR(100) NOT NULL,
  `status` TINYINT(1) DEFAULT NULL,
  `userType` VARCHAR(50) DEFAULT NULL,
  `interestedTags` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(`interestedTags`)),
  `interestedCourses` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(`interestedCourses`)),
  `studyPrograms` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (JSON_VALID(`studyPrograms`)),
  `isBlockedByAdmin` TINYINT(1) DEFAULT NULL,
  `createdAt` DATETIME DEFAULT NULL,
  `updatedAt` DATETIME DEFAULT NULL,
  PRIMARY KEY (`_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

## Run the Application

To run the FastAPI server, use:
`uvicorn main:app --reload`
This will start the server at http://127.0.0.1:8000.

## Docker Setup

### Build the Docker image
Ensure you are in the project directory (where the Dockerfile is located) and run the following command:

`docker build -t idealize-recommendation .`

### Run the Docker container
Start the container with the following command:

`docker run -d -p 8000:8000 --name idealize-recommendation-container idealize-recommendation`

The project will run in the background (-d) and will be accessible at port 8000.
You can adjust the port mapping if necessary.

### Access the API
Once the container is running, you can access the FastAPI application at http://localhost:8000.

### Environment Variables
Ensure that the OpenAI API key is correctly set. You can add the API key directly in the Dockerfile:
```ENV OPENAI_API_KEY="your-openai_key"```

### Database Connection
If you're using an external MySQL database, make sure the container can access it. You can set up the MySQL connection environment variables inside the container or use a docker-compose.yml file to define a connected database service.

## API Usage
POST request to /api/chatbot with JSON body:

{
  "message": "your question here"
}

Example response:

{
  "response": {
    "message": "Your response here",
    "projects": [
      {
        "_id": "project_id",
        "title": "Project title",
        "createdAt": "2024-10-21 10:30:00"
      }
    ],
    "users": [
      {
        "_id": "user_id",
        "firstName": "First",
        "lastName": "Last",
        "interestedTags": ["tag1", "tag2"]
      }
    ]
  }
}