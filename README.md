# Idealize-Recommendation

This is a project that integrates a chatbot with a MySQL database using Langchain and OpenAI's GPT-4-turbo model. The project is designed to interact with a database of projects, users, and tags, and respond with specific fields based on the user's prompt.

## Acknowledgements
This project was developed as part of the InduKo Project, funded by Stiftung Innovation in der Hochschullehre.
We also acknowledge the support from students, faculty and contributors who have been part of this collaborative effort.

For more iniformation about the InduKo research project, visit the official  website: https://www.hs-heilbronn.de/en/projekt-induko-2cab68e84c21b797

For more iniformation about the IdeaLize project platform, visit the official  website: https://www.hs-heilbronn.de/en/idealize-12f73ca0754864df

## License 

This project is licensed under Apache License, Version 2.0. Copyright 2024 Prof. Dr. Mahsa Fischer, Hochschule Heilbronn

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


```-- Create `chat_log` table
CREATE TABLE `chat_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `prompt` text NOT NULL,
  `response` text NOT NULL,
  `timestamp` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Create `Projects` table
CREATE TABLE `Projects` (
  `_id` varchar(255) NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `owner_id` varchar(255) DEFAULT NULL,
  `isDraft` tinyint(1) DEFAULT NULL,
  `links` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`links`)),
  `attachments` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`attachments`)),
  `createdAt` datetime DEFAULT NULL,
  `updatedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`_id`),
  KEY `owner_id` (`owner_id`),
  CONSTRAINT `projects_ibfk_1` FOREIGN KEY (`owner_id`) REFERENCES `Users` (`_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Create `Tags` table
CREATE TABLE `Tags` (
  `_id` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `type` varchar(50) DEFAULT NULL,
  `createdAt` datetime DEFAULT NULL,
  `updatedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Create `Users` table
CREATE TABLE `Users` (
  `_id` varchar(255) NOT NULL,
  `firstName` varchar(100) DEFAULT NULL,
  `lastName` varchar(100) DEFAULT NULL,
  `email` varchar(255) NOT NULL,
  `username` varchar(100) NOT NULL,
  `status` tinyint(1) DEFAULT NULL,
  `userType` varchar(50) DEFAULT NULL,
  `interestedTags` longtext CHARACTER SET utf8mb4 COLLATE=utf8mb4_bin DEFAULT NULL CHECK (json_valid(`interestedTags`)),
  `interestedCourses` longtext CHARACTER SET utf8mb4 COLLATE=utf8mb4_bin DEFAULT NULL CHECK (json_valid(`interestedCourses`)),
  `studyPrograms` longtext CHARACTER SET utf8mb4 COLLATE=utf8mb4_bin DEFAULT NULL CHECK (json_valid(`studyPrograms`)),
  `isBlockedByAdmin` tinyint(1) DEFAULT NULL,
  `createdAt` datetime DEFAULT NULL,
  `updatedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`_id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Create `Project_Tags` table
CREATE TABLE `Project_Tags` (
  `project_id` varchar(255) NOT NULL,
  `tag_id` varchar(255) NOT NULL,
  PRIMARY KEY (`project_id`,`tag_id`),
  KEY `tag_id` (`tag_id`),
  CONSTRAINT `project_tags_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `Projects` (`_id`) ON DELETE CASCADE,
  CONSTRAINT `project_tags_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `Tags` (`_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;```

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