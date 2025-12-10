#   Copyright 2024 Prof. Dr. Mahsa Fischer, Hochschule Heilbronn
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
RAG (Retrieval Augmented Generation) Chatbot with Database-Stored Embeddings
=============================================================================
This module implements a production-ready RAG chatbot for FastAPI integration that:
- Uses ONLY MariaDB for data storage (no file dependencies)
- Generates fresh embeddings on each request for maximum accuracy
- Supports both project and user retrieval
- Logs all interactions

Key Features:
- MongoDB to SQL database synchronization
- Semantic search for projects and users
- Real-time embedding generation
- Conversation logging
- FastAPI-ready JSON response format

Usage:
    Called from main.py FastAPI endpoint:
    result = rag_chatbot.query_projects(message)
"""

import os
import json
import pathlib
import numpy as np
import pymysql
import requests
import langdetect
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from openai import OpenAI
import apikey
import bearer_token

# Initialize OpenAI client
client = OpenAI(api_key=apikey.APIKEY)

# Database connection (lazy initialization)
connection = None


def get_db_connection():
    """
    Get or create database connection (lazy initialization).
    
    Returns:
        pymysql.Connection object
    """
    global connection
    if connection is None or not connection.open:
        connection = pymysql.connect(
            host='127.0.0.1',
            user='root',
            password='',
            database='recsys',
            cursorclass=pymysql.cursors.DictCursor
        )
    return connection


# =============================================================================
# DATABASE UTILITY FUNCTIONS
# =============================================================================

def convert_iso_to_mysql_datetime(iso_str: str) -> Optional[str]:
    """Convert ISO 8601 datetime to MySQL format."""
    try:
        return datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def save_chat_to_db(prompt: str, response: Dict) -> None:
    """Save chat interaction to database for logging."""
    try:
        conn = get_db_connection()
        response_str = json.dumps(response, ensure_ascii=False)
        
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_log (prompt, response) VALUES (%s, %s)",
                (prompt, response_str)
            )
        conn.commit()
        print(" Chat interaction saved to database")
    except pymysql.MySQLError as e:
        print(f"⚠️  Error saving chat: {e}")


def insert_data_from_api() -> bool:
    """
    Fetch data from MongoDB backend API and mirror to SQL database.
    
    Returns:
        True if sync was successful
    """
    
    in_docker = pathlib.Path("/.dockerenv").exists()
    
    if in_docker:
        # Try multiple connection methods in Docker
        urls_to_try = [
            "http://backend-ai:7000/",  # Container name in same network
            "http://idealize_server_ai-backend-ai:7000/",  # Full container name
            "http://172.22.0.2:7000/",  # Container IP
            "http://host.docker.internal:7000/",  # Host machine
        ]
    else:
        urls_to_try = ["http://localhost:7000/"]

    headers = {
        'Authorization': f'Bearer {bearer_token.TOKEN}',
        'Content-Type': 'application/json'
    }

    response_projects = None
    response_users = None
    response_tags = None
    successful_url = None
    
    # Try each URL until one works
    for base_url in urls_to_try:
        try:
            print(f"🔄 Trying: {base_url}")
            response_projects = requests.get(base_url + 'projects', headers=headers, timeout=5)
            response_users = requests.get(base_url + 'users', headers=headers, timeout=5)
            response_tags = requests.get(base_url + 'tags', headers=headers, timeout=5)
            
            if response_projects.status_code == 200 and response_users.status_code == 200 and response_tags.status_code == 200:
                successful_url = base_url
                print(f"✅ Connected to: {base_url}")
                break
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Failed {base_url}: {str(e)[:100]}")
            continue
    
    if not successful_url or response_projects.status_code != 200:
        print(f"❌ Failed to fetch data from API")
        return False

    projects = response_projects.json().get('projects', [])
    users = response_users.json()
    tags = response_tags.json()
    
    print(f"✅ Fetched {len(projects)} projects, {len(users)} users, {len(tags)} tags")

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM Tags")
        cursor.execute("DELETE FROM Projects")
        cursor.execute("DELETE FROM Users")
        print("  Cleared existing SQL data")
        
        # Insert Tags
        for tag in tags:
            created_at = convert_iso_to_mysql_datetime(tag['createdAt'])
            updated_at = convert_iso_to_mysql_datetime(tag['updatedAt'])
            cursor.execute(
                """INSERT INTO Tags (_id, name, type, createdAt, updatedAt)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE name = VALUES(name), type = VALUES(type)""",
                (tag['_id'], tag['name'], tag['type'], created_at, updated_at)
            )

        # Insert Users
        for user in users:
            created_at = convert_iso_to_mysql_datetime(user['createdAt'])
            updated_at = convert_iso_to_mysql_datetime(user['updatedAt'])
            cursor.execute(
                """INSERT INTO Users (_id, firstName, lastName, email, username, status, userType, 
                   interestedTags, interestedCourses, studyPrograms, isBlockedByAdmin, createdAt, updatedAt)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE firstName = VALUES(firstName), lastName = VALUES(lastName)""",
                (user['_id'], user['firstName'], user['lastName'], user['email'], user['username'],
                 user['status'], user['userType'], json.dumps(user['interestedTags']),
                 json.dumps(user['interestedCourses']), json.dumps(user['studyPrograms']),
                 user['isBlockedByAdmin'], created_at, updated_at)
            )

        # Insert Projects
        for project in projects:
            created_at = convert_iso_to_mysql_datetime(project['createdAt'])
            updated_at = convert_iso_to_mysql_datetime(project['updatedAt'])
            owner_id = project['owner']['_id'] if isinstance(project.get('owner'), dict) else None
            
            cursor.execute(
                """INSERT INTO Projects (_id, title, description, tags, owner_id, isDraft, links, attachments, createdAt, updatedAt)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE title = VALUES(title), description = VALUES(description)""",
                (project['_id'], project['title'], project['description'], json.dumps(project['tags']),
                 owner_id, project['isDraft'], json.dumps(project['links']),
                 json.dumps(project['attachments']), created_at, updated_at)
            )

        conn.commit()
        print("✅ Data successfully synced to SQL database")
        return True


# =============================================================================
# DATA MODELS
# =============================================================================

class ProjectDocument:
    """Represents a project for vector search operations."""
    
    def __init__(self, project_id: str, title: str, description: str, 
                 tags: List[str], created: str, owner: str):
        self.project_id = project_id
        self.title = title
        self.description = description
        self.tags = tags
        self.created = created
        self.owner = owner
        
    def to_text(self) -> str:
        """Convert project to searchable text for embedding generation."""
        tags_str = ", ".join(self.tags)
        return f"""Project: {self.title}
Description: {self.description}
Tags: {tags_str}
Created: {self.created}
Owner: {self.owner}"""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON output."""
        return {
            "_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "createdAt": self.created,
            "owner": self.owner
        }


class UserDocument:
    """Represents a user for vector search operations."""
    
    def __init__(self, user_id: str, first_name: str, last_name: str,
                 interested_tags: List[str], interested_courses: List[str],
                 study_programs: List[str], created: str):
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.interested_tags = interested_tags
        self.interested_courses = interested_courses
        self.study_programs = study_programs
        self.created = created
    
    def to_text(self) -> str:
        """Convert user to searchable text for embedding generation."""
        # Handle tags that might be dicts with 'name' field or simple strings
        def extract_names(items):
            if not items:
                return "None"
            names = []
            for item in items:
                if isinstance(item, dict):
                    names.append(item.get('name', str(item)))
                else:
                    names.append(str(item))
            return ", ".join(names) if names else "None"
        
        tags_str = extract_names(self.interested_tags)
        courses_str = extract_names(self.interested_courses)
        programs_str = extract_names(self.study_programs)
        
        return f"""User: {self.first_name} {self.last_name}
Interested Tags: {tags_str}
Interested Courses: {courses_str}
Study Programs: {programs_str}"""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON output."""
        return {
            "_id": self.user_id,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "interestedTags": self.interested_tags,
            "createdAt": self.created
        }


# =============================================================================
# RAG CHATBOT CLASS
# =============================================================================

class RAGChatbot:
    """
    RAG-based chatbot with database-cached embeddings.
    
    Features:
    - Loads embeddings from database (fast startup)
    - Generates missing embeddings automatically
    - Supports project and user retrieval
    - Stores embeddings back to database
    """
    
    def __init__(self, exclude_user_id: str = None):
        """
        Initialize RAG chatbot.
        Loads ALL projects and users from database and generates embeddings once.
        User filtering is done at query time, not at initialization.
        
        Args:
            exclude_user_id: Deprecated - filtering now done at query time
        """
        self.projects: List[ProjectDocument] = []
        self.users: List[UserDocument] = []
        self.project_embeddings: np.ndarray = None
        self.user_embeddings: np.ndarray = None
        
        # Load ALL data from database (no filtering at init)
        self.load_projects_from_sql()
        self.load_users_from_sql()
        
        # Generate embeddings once for all data
        print("🔄 Generating embeddings for all projects and users...")
        self.create_project_embeddings()
        self.create_user_embeddings()
    
    def load_projects_from_sql(self) -> None:
        """Load ALL projects from SQL database (filtering done at query time)."""
        print("📁 Loading all projects from database...")
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT _id, title, description, tags, createdAt, owner_id
                FROM Projects
                WHERE isDraft = 0
                ORDER BY createdAt DESC
            """)
            
            for row in cursor.fetchall():
                tags_list = []
                if row['tags']:
                    try:
                        tags_data = json.loads(row['tags'])
                        if isinstance(tags_data, list):
                            tags_list = [tag['name'] if isinstance(tag, dict) else str(tag) for tag in tags_data]
                    except json.JSONDecodeError:
                        pass
                
                project = ProjectDocument(
                    project_id=row['_id'],
                    title=row['title'],
                    description=row['description'] or "",
                    tags=tags_list,
                    created=str(row['createdAt']) if row['createdAt'] else "",
                    owner=row['owner_id'] or "Unknown"
                )
                self.projects.append(project)
        
        print(f"✅ Loaded {len(self.projects)} projects")
    
    def load_users_from_sql(self) -> None:
        """Load ALL users from SQL database (filtering done at query time)."""
        print("📁 Loading all users from database...")
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT _id, firstName, lastName, interestedTags, 
                       interestedCourses, studyPrograms, createdAt
                FROM Users
                WHERE isBlockedByAdmin = 0
                ORDER BY createdAt DESC
            """)
            
            for row in cursor.fetchall():
                interested_tags = json.loads(row['interestedTags']) if row['interestedTags'] else []
                interested_courses = json.loads(row['interestedCourses']) if row['interestedCourses'] else []
                study_programs = json.loads(row['studyPrograms']) if row['studyPrograms'] else []
                
                user = UserDocument(
                    user_id=row['_id'],
                    first_name=row['firstName'] or "",
                    last_name=row['lastName'] or "",
                    interested_tags=interested_tags,
                    interested_courses=interested_courses,
                    study_programs=study_programs,
                    created=str(row['createdAt']) if row['createdAt'] else ""
                )
                self.users.append(user)
        
        print(f"✅ Loaded {len(self.users)} users")
    

    def create_project_embeddings(self) -> None:
        """Generate embeddings for all projects using OpenAI API."""
        print("🔄 Creating project embeddings...")
        
        if not self.projects:
            print("⚠️  No projects to embed")
            return
        
        texts = [project.to_text() for project in self.projects]
        embeddings = []
        batch_size = 20
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
        
        self.project_embeddings = np.array(embeddings)
        print(f"✅ Created project embeddings: {self.project_embeddings.shape}")
    
    def create_user_embeddings(self) -> None:
        """Generate embeddings for all users using OpenAI API."""
        print("🔄 Creating user embeddings...")
        
        if not self.users:
            print("⚠️  No users to embed")
            return
        
        texts = [user.to_text() for user in self.users]
        embeddings = []
        batch_size = 20
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
        
        self.user_embeddings = np.array(embeddings)
        print(f"✅ Created user embeddings: {self.user_embeddings.shape}")
    

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def retrieve_relevant_projects(self, query: str, exclude_user_id: str = None, top_k: int = 5) -> List[Tuple[ProjectDocument, float]]:
        """
        Find most relevant projects using semantic search.
        
        Args:
            query: Search query
            exclude_user_id: Optional user ID to exclude their projects
            top_k: Number of results to return
            
        Returns:
            List of (project, similarity_score) tuples
        """
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = np.array(response.data[0].embedding)
        
        similarities = []
        for i, project_embedding in enumerate(self.project_embeddings):
            project = self.projects[i]
            
            # Skip projects owned by the excluded user
            if exclude_user_id and project.owner == exclude_user_id:
                continue
                
            similarity = self.cosine_similarity(query_embedding, project_embedding)
            similarities.append((project, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def retrieve_relevant_users(self, query: str, exclude_user_id: str = None, top_k: int = 5) -> List[Tuple[UserDocument, float]]:
        """
        Find most relevant users using semantic search.
        
        Args:
            query: Search query
            exclude_user_id: Optional user ID to exclude from results
            top_k: Number of results to return
            
        Returns:
            List of (user, similarity_score) tuples
        """
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = np.array(response.data[0].embedding)
        
        similarities = []
        for i, user_embedding in enumerate(self.user_embeddings):
            user = self.users[i]
            
            # Skip the excluded user
            if exclude_user_id and user.user_id == exclude_user_id:
                continue
                
            similarity = self.cosine_similarity(query_embedding, user_embedding)
            similarities.append((user, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def generate_response(self, query: str, relevant_projects: List[Tuple[ProjectDocument, float]], 
                         relevant_users: List[Tuple[UserDocument, float]] = None) -> Dict:
        """
        Generate natural language response using GPT-4-turbo with language detection.
        
        Args:
            query: User's query
            relevant_projects: Retrieved projects
            relevant_users: Retrieved users (optional)
            
        Returns:
            Dictionary with message and retrieved items in sqlchatbot.py compatible format
        """
        # Detect language
        lang = langdetect.detect(query)
        
        # Build context with retrieved information
        context = "The following relevant projects were found:\n\n"
        for i, (project, score) in enumerate(relevant_projects, 1):
            context += f"{i}. {project.title}\n"
            context += f"   Description: {project.description}\n"
            context += f"   Tags: {', '.join(project.tags)}\n"
            context += f"   Relevance: {score:.3f}\n\n"
        
        if relevant_users:
            context += "\nRelevant users:\n\n"
            for i, (user, score) in enumerate(relevant_users, 1):
                context += f"{i}. {user.first_name} {user.last_name}\n"
                # Extract tag names from interested_tags
                def extract_names(items):
                    if not items:
                        return []
                    names = []
                    for item in items:
                        if isinstance(item, dict):
                            names.append(item.get('name', str(item)))
                        else:
                            names.append(str(item))
                    return names
                
                tag_names = extract_names(user.interested_tags[:5])
                context += f"   Interested in: {', '.join(tag_names)}\n"
                context += f"   Relevance: {score:.3f}\n\n"
        
        # Set system prompt based on detected language
        if lang == 'de':
            specific_prompt = """Ich möchte, dass du nur bestimmte Felder aus der Datenbank extrahierst und in deiner Antwort zurückgibst. Bitte beachte folgende Anforderungen:
                            - Wenn in der Anfrage nach Projekten gefragt wird, gib nur das Feld _id, title und das Feld createdAt für jedes Projekt zurück.
                            - Wenn in der Anfrage nach Personen gefragt wird, gib nur die Felder _id, firstName, lastName und interestedTags für jede Person zurück.
                            - In deiner Antwort erwarte ich EXAKT folgendes JSON-Format:

                            {
                            "message": "Dein Antworttext",
                            "projects": [
                                {
                                "_id": "objectID",
                                "title": "Projektname",
                                "createdAt": "2024-10-21 10:30:00"
                                }<
                            ],
                            "users": [
                                {
                                "_id": "objectID",
                                "firstName": "Vorname",
                                "lastName": "Nachname",
                                "interestedTags": ["Tag1", "Tag2"]
                                }
                            ]
                            }

                            Außerdem gib nur den Output zurück; nichts vom Input
                            Falls keine Projekte oder Personen in der Anfrage relevant sind, lass die entsprechenden Listen leer.

                            Verwende keine vertraulichen Daten wie Passwörter, E-Mail-Adressen oder Codes in der Antwort."""
        else:
            specific_prompt = """I want you to extract only specific fields from the database and return them in your response. Please consider the following requirements:
                            - When the request is about projects, return only the fields _id, title, and createdAt for each project.
                            - When the request is about people, return only the fields _id, firstName, lastName, and interestedTags for each person.
                            - In your response, I expect EXACTLY the following JSON format:

                            {
                            "message": "Your response text",
                            "projects": [
                                {
                                "_id": "objectID",
                                "title": "Project name",
                                "createdAt": "2024-10-21 10:30:00"
                                }
                            ],
                            "users": [
                                {
                                "_id": "objectID",
                                "firstName": "First name",
                                "lastName": "Last name",
                                "interestedTags": ["Tag1", "Tag2"]
                                }
                            ]
                            }

                            Also, only return the output; nothing from the input.
                            If no projects or people are relevant in the request, leave the corresponding lists empty.

                            Do not use confidential data such as passwords, email addresses, or codes in the response.

                            Always answer in the same language as the following request:"""
        
            # Combine specific prompt with context and query
            user_prompt = f"""{specific_prompt}
                        Based on this information:
                        {context}
                        Answer: {query}"""

        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for finding relevant projects and users. Answer based on the provided information. Be precise and helpful."},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        # Parse the JSON response from GPT-4-turbo
        try:
            result = json.loads(completion.choices[0].message.content)
            
            # Ensure the response has the required structure
            if "message" not in result:
                result["message"] = "Response generated successfully"
            if "projects" not in result:
                result["projects"] = []
            if "users" not in result:
                result["users"] = []
                
            return result
            
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse GPT-4 response as JSON: {e}")
            print(f"Raw response: {completion.choices[0].message.content}")
            
            # Fallback: return structured data manually
            def extract_tag_names(items):
                if not items:
                    return []
                names = []
                for item in items:
                    if isinstance(item, dict):
                        names.append(item.get('name', str(item)))
                    else:
                        names.append(str(item))
                return names
            
            result = {
                "message": completion.choices[0].message.content,
                "projects": [
                    {
                        "_id": project.project_id,
                        "title": project.title,
                        "createdAt": project.created
                    }
                    for project, score in relevant_projects
                ],
                "users": [
                    {
                        "_id": user.user_id,
                        "firstName": user.first_name,
                        "lastName": user.last_name,
                        "interestedTags": extract_tag_names(user.interested_tags)
                    }
                    for user, score in relevant_users
                ] if relevant_users else []
            }
            
            return result
    
    def query(self, question: str, user_id: str = None, top_k: int = 5) -> Dict:
        """
        Process user query with RAG pipeline.
        
        Args:
            question: User's question
            user_id: Optional user ID to filter out their own projects and profile
            top_k: Number of results to return
            
        Returns:
            Dictionary with response (compatible with sqlchatbot.py format)
        """
        print(f"\n🔍 Searching for: '{question}'")
        
        # Retrieve relevant projects (filter by user_id if provided)
        relevant_projects = self.retrieve_relevant_projects(question, user_id, top_k)
        print(f"📊 Found {len(relevant_projects)} relevant projects")
        
        # Retrieve users (filter by user_id if provided)
        relevant_users = None
        if len(self.users) > 0:
            relevant_users = self.retrieve_relevant_users(question, user_id, top_k)
            print(f"👥 Found {len(relevant_users)} relevant users")
        
        # Generate response
        print("💬 Generating response with GPT-4...")
        response = self.generate_response(question, relevant_projects, relevant_users)
        
        # Log to database
        save_chat_to_db(question, response)
        
        return response


# =============================================================================
# API ENTRY POINT
# =============================================================================

# Global chatbot instance (initialized once at startup)
_chatbot_instance: Optional[RAGChatbot] = None

def initialize_chatbot() -> None:
    """
    Initialize the global RAG chatbot instance.
    Called once during FastAPI startup to load data and generate embeddings.
    """
    global _chatbot_instance
    _chatbot_instance = RAGChatbot(exclude_user_id=None)
    print(f"Chatbot initialized with {len(_chatbot_instance.projects)} projects and {len(_chatbot_instance.users)} users")


def query_projects(message: str, user_id: str = None) -> str:
    """
    Main entry point for FastAPI integration.
    Uses the global chatbot instance (loaded once at startup).
    
    Args:
        message: User's query message
        user_id: Optional user ID to exclude their own projects and user from results
        
    Returns:
        JSON string with response in sqlchatbot.py compatible format:
        {
            "message": "Response text",
            "projects": [{"_id": "...", "title": "...", "createdAt": "..."}],
            "users": [{"_id": "...", "firstName": "...", "lastName": "...", "interestedTags": [...]}]
        }
    """
    global _chatbot_instance
    
    try:
        if _chatbot_instance is None:
            raise RuntimeError("RAG chatbot not initialized. Call initialize_chatbot() first.")
        
        print("=" * 60)
        print("🚀 RAG Chatbot Query")
        if user_id:
            print(f"🔐 Filtering for user: {user_id}")
        print("=" * 60)
        
        # Process query with user filtering
        result = _chatbot_instance.query(message, user_id=user_id, top_k=5)
        
        print("✅ Query completed successfully")
        print("=" * 60)
        
        # Return as JSON string (like sqlchatbot.py)
        return json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        
    except Exception as e:
        print(f"❌ Error processing query: {e}")
        import traceback
        traceback.print_exc()
        
        # Return error in expected format
        error_response = {
            "message": f"Error: {str(e)}",
            "projects": [],
            "users": []
        }
        return json.dumps(error_response, ensure_ascii=False, separators=(',', ':'))
