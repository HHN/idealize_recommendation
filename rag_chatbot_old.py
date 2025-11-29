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
RAG (Retrieval Augmented Generation) Chatbot with SQL Integration
==================================================================
This module implements a RAG-based chatbot that combines the speed of vector search
with the reliability of SQL database storage. It mirrors MongoDB data to SQL,
creates embeddings for semantic search, and logs all interactions.

Key Features:
- MongoDB to SQL database synchronization
- Vector-based semantic search using OpenAI embeddings
- Fast project and user retrieval
- Conversation logging to database
- JSON-formatted responses compatible with existing API structure
"""

import os
import sys
import json
import pathlib
import numpy as np
import pymysql
import requests
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from openai import OpenAI
import apikey

# Initialize OpenAI client for embeddings and chat completions
client = OpenAI(api_key=apikey.APIKEY)

# Database connection (lazy initialization)
# Will be created when needed to avoid connection errors at import time
connection = None


def get_db_connection():
    """
    Get or create database connection (lazy initialization).
    
    Returns:
        pymysql.Connection object
    
    Raises:
        pymysql.MySQLError: If connection cannot be established
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
    """
    Convert ISO 8601 datetime string to MySQL datetime format.
    
    Args:
        iso_str: ISO 8601 formatted datetime string (e.g., '2024-10-21T10:30:00.000Z')
    
    Returns:
        MySQL formatted datetime string (e.g., '2024-10-21 10:30:00') or None if invalid
    """
    try:
        return datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def save_chat_to_db(prompt: str, response: Dict) -> None:
    """
    Save chat interaction to the database for logging and analytics.
    
    Args:
        prompt: User's input query
        response: Dictionary containing the chatbot's response and retrieved data
    
    Note:
        Automatically commits to database. Errors are printed but don't stop execution.
    """
    try:
        conn = get_db_connection()
        # Convert response dictionary to JSON string for storage
        response_str = json.dumps(response, ensure_ascii=False)
        
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_log (prompt, response)
                VALUES (%s, %s)
                """,
                (prompt, response_str)
            )
        conn.commit()
        print("💾 Chat interaction saved to database")
    except pymysql.MySQLError as e:
        print(f"⚠️  Error saving chat to database: {e}")


def insert_data_from_api() -> bool:
    """
    Fetch data from MongoDB backend API and mirror it to SQL database.
    
    This function:
    1. Retrieves projects, users, and tags from the backend API
    2. Clears existing data in SQL tables
    3. Inserts fresh data from MongoDB into SQL
    
    Returns:
        True if data sync was successful, False otherwise
    
    Note:
        Requires bearer_token module for API authentication.
        Uses Docker detection to determine correct API endpoint.
    """
    import bearer_token
    
    # Detect if running in Docker container to use correct host
    in_docker = pathlib.Path("/.dockerenv").exists()
    base_url = "http://host.docker.internal:3000/" if in_docker else "http://localhost:3000/"

    headers = {
        'Authorization': f'Bearer {bearer_token.TOKEN}',
        'Content-Type': 'application/json'
    }

    print(f"🔄 Fetching data from API: {base_url}")
    
    # Fetch all required data from API endpoints
    response_projects = requests.get(base_url + 'projects', headers=headers)
    response_users = requests.get(base_url + 'users', headers=headers)
    response_tags = requests.get(base_url + 'tags', headers=headers)

    # Validate all API responses
    if response_projects.status_code != 200 or response_users.status_code != 200 or response_tags.status_code != 200:
        print(f"❌ Failed to fetch data from API (Base URL: {base_url})")
        print(f"   Projects: {response_projects.status_code}")
        print(f"   Users: {response_users.status_code}")
        print(f"   Tags: {response_tags.status_code}")
        return False

    # Parse JSON responses
    projects = response_projects.json().get('projects', [])
    users = response_users.json()
    tags = response_tags.json()
    
    print(f"✅ Fetched {len(projects)} projects, {len(users)} users, {len(tags)} tags")

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Clear existing data to ensure fresh sync
        # Order matters due to potential foreign key constraints
        cursor.execute("DELETE FROM Tags")
        cursor.execute("DELETE FROM Projects")
        cursor.execute("DELETE FROM Users")
        print("🗑️  Cleared existing SQL data")
        
        # Insert Tags
        # -----------
        for tag in tags:
            created_at = convert_iso_to_mysql_datetime(tag['createdAt'])
            updated_at = convert_iso_to_mysql_datetime(tag['updatedAt'])

            cursor.execute(  
                """
                INSERT INTO Tags (_id, name, type, createdAt, updatedAt)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    name = VALUES(name),
                    type = VALUES(type),
                    createdAt = VALUES(createdAt),
                    updatedAt = VALUES(updatedAt)
                """,
                (tag['_id'], tag['name'], tag['type'], created_at, updated_at)
            )

        # Insert Users
        # ------------
        for user in users:
            created_at = convert_iso_to_mysql_datetime(user['createdAt'])
            updated_at = convert_iso_to_mysql_datetime(user['updatedAt'])

            cursor.execute(
                """
                INSERT INTO Users (_id, firstName, lastName, email, username, status, userType, 
                                   interestedTags, interestedCourses, studyPrograms, 
                                   isBlockedByAdmin, createdAt, updatedAt)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    firstName = VALUES(firstName),
                    lastName = VALUES(lastName),
                    email = VALUES(email),
                    username = VALUES(username),
                    status = VALUES(status),
                    userType = VALUES(userType), 
                    interestedTags = VALUES(interestedTags), 
                    interestedCourses = VALUES(interestedCourses), 
                    studyPrograms = VALUES(studyPrograms),
                    isBlockedByAdmin = VALUES(isBlockedByAdmin),
                    createdAt = VALUES(createdAt), 
                    updatedAt = VALUES(updatedAt)
                """,
                (user['_id'],
                 user['firstName'],
                 user['lastName'],
                 user['email'],
                 user['username'],
                 user['status'],
                 user['userType'],
                 json.dumps(user['interestedTags']),
                 json.dumps(user['interestedCourses']),
                 json.dumps(user['studyPrograms']),
                 user['isBlockedByAdmin'],
                 created_at,
                 updated_at)
            )

        # Insert Projects
        # ---------------
        # Tags are stored as JSON array in the 'tags' field
        for project in projects:
            created_at = convert_iso_to_mysql_datetime(project['createdAt'])
            updated_at = convert_iso_to_mysql_datetime(project['updatedAt'])

            # Extract owner ID from nested object structure
            owner_id = None
            if isinstance(project['owner'], dict) and '_id' in project['owner']:
                owner_id = project['owner']['_id']

            cursor.execute(
                """
                INSERT INTO Projects (_id, title, description, tags, owner_id, isDraft, links, attachments, createdAt, updatedAt)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    description = VALUES(description),
                    tags = VALUES(tags),
                    owner_id = VALUES(owner_id),
                    isDraft = VALUES(isDraft),
                    links = VALUES(links),
                    attachments = VALUES(attachments),
                    createdAt = VALUES(createdAt),
                    updatedAt = VALUES(updatedAt)
                """,
                (
                    project['_id'],
                    project['title'],
                    project['description'],
                    json.dumps(project['tags']),
                    owner_id,
                    project['isDraft'],
                    json.dumps(project['links']),
                    json.dumps(project['attachments']),
                    created_at,
                    updated_at
                )
            )

        conn.commit()
        print("✅ Data successfully synced to SQL database")
        return True


# =============================================================================
# DATA MODELS
# =============================================================================

class ProjectDocument:
    """
    Represents a single project document with all relevant metadata.
    
    This class encapsulates project data for vector search and retrieval operations.
    """
    
    def __init__(self, project_id: str, title: str, description: str, 
                 tags: List[str], created: str, owner: str):
        """
        Initialize a project document.
        
        Args:
            project_id: Unique MongoDB ObjectID
            title: Project title
            description: Detailed project description
            tags: List of associated tags/keywords
            created: Creation timestamp
            owner: Owner name or ID
        """
        self.project_id = project_id
        self.title = title
        self.description = description
        self.tags = tags
        self.created = created
        self.owner = owner
        
    def to_text(self) -> str:
        """
        Convert project to searchable text representation.
        
        This text format is used for creating embeddings and semantic search.
        Includes all relevant fields that should influence search relevance.
        
        Returns:
            Formatted string containing all project information
        """
        tags_str = ", ".join(self.tags)
        return f"""Project: {self.title}
Description: {self.description}
Tags: {tags_str}
Created: {self.created}
Owner: {self.owner}"""

    def to_dict(self) -> Dict:
        """
        Convert project to dictionary for JSON serialization.
        
        Returns:
            Dictionary with all project fields
        """
        return {
            "_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "createdAt": self.created,
            "owner": self.owner
        }


class UserDocument:
    """
    Represents a single user document with all relevant metadata.
    
    This class encapsulates user data for vector search and matching operations.
    """
    
    def __init__(self, user_id: str, first_name: str, last_name: str,
                 interested_tags: List[str], interested_courses: List[str],
                 study_programs: List[str], created: str):
        """
        Initialize a user document.
        
        Args:
            user_id: Unique MongoDB ObjectID
            first_name: User's first name
            last_name: User's last name
            interested_tags: List of tags the user is interested in
            interested_courses: List of courses the user is interested in
            study_programs: List of study programs
            created: Creation timestamp
        """
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.interested_tags = interested_tags
        self.interested_courses = interested_courses
        self.study_programs = study_programs
        self.created = created
    
    def to_text(self) -> str:
        """
        Convert user to searchable text representation.
        
        Returns:
            Formatted string containing all user information
        """
        tags_str = ", ".join(self.interested_tags) if self.interested_tags else "None"
        courses_str = ", ".join(self.interested_courses) if self.interested_courses else "None"
        programs_str = ", ".join(self.study_programs) if self.study_programs else "None"
        
        return f"""User: {self.first_name} {self.last_name}
Interested Tags: {tags_str}
Interested Courses: {courses_str}
Study Programs: {programs_str}"""
    
    def to_dict(self) -> Dict:
        """
        Convert user to dictionary for JSON serialization.
        
        Returns:
            Dictionary with all user fields
        """
        return {
            "_id": self.user_id,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "interestedTags": self.interested_tags,
            "interestedCourses": self.interested_courses,
            "studyPrograms": self.study_programs,
            "createdAt": self.created
        }


class RAGChatbot:
    """
    RAG-based chatbot for fast project and user retrieval.
    
    This chatbot combines:
    - Vector embeddings for semantic search
    - SQL database for reliable data storage
    - GPT-4 for natural language response generation
    
    Workflow:
    1. Sync MongoDB data to SQL (optional, on initialization)
    2. Load projects/users from SQL database
    3. Create vector embeddings for semantic search
    4. Process queries using cosine similarity
    5. Generate contextual responses with GPT-4
    6. Log all interactions to database
    """
    
    def __init__(self, sync_from_api: bool = False, use_cached_embeddings: bool = True):
        """
        Initialize the RAG chatbot.
        
        Args:
            sync_from_api: If True, sync MongoDB data to SQL before loading
            use_cached_embeddings: If True, load embeddings from DB (faster)
        """
        self.projects: List[ProjectDocument] = []
        self.users: List[UserDocument] = []
        self.project_embeddings: np.ndarray = None
        self.user_embeddings: np.ndarray = None
        
        # Optionally sync data from MongoDB API
        if sync_from_api:
            print("🔄 Syncing data from MongoDB to SQL...")
            if not insert_data_from_api():
                print("⚠️  Warning: API sync failed, continuing with existing SQL data")
        
        # Load projects and users from database
        self.load_projects_from_sql()
        self.load_users_from_sql()
        
        # Load or generate embeddings
        if use_cached_embeddings:
            # Try to load from database first
            projects_loaded = self.load_project_embeddings_from_db()
            users_loaded = self.load_user_embeddings_from_db()
            
            # Generate missing embeddings
            if not projects_loaded:
                print("🔄 No cached project embeddings found, generating...")
                self.create_project_embeddings()
                self.store_project_embeddings_in_db()
            
            if not users_loaded:
                print("🔄 No cached user embeddings found, generating...")
                self.create_user_embeddings()
                self.store_user_embeddings_in_db()
        else:
            # Force regeneration
            print("🔄 Force generating all embeddings...")
            self.create_project_embeddings()
            self.create_user_embeddings()
            self.store_project_embeddings_in_db()
            self.store_user_embeddings_in_db()
    
    def load_projects_from_sql(self) -> None:
        """
        Load projects from SQL database.
        
        Fetches all projects with their associated data and converts them
        to ProjectDocument objects for vector search operations.
        """
        print("📁 Loading projects from SQL database...")
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT _id, title, description, tags, createdAt, owner_id
                FROM Projects
                WHERE isDraft = 0
                ORDER BY createdAt DESC
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                # Parse tags from JSON string
                tags_list = []
                if row['tags']:
                    try:
                        tags_data = json.loads(row['tags'])
                        # Tags can be array of strings or array of objects with 'name' field
                        if isinstance(tags_data, list):
                            tags_list = [
                                tag['name'] if isinstance(tag, dict) else str(tag)
                                for tag in tags_data
                            ]
                    except json.JSONDecodeError:
                        print(f"⚠️  Warning: Invalid JSON in tags for project {row['_id']}")
                
                # Get owner name if available (optional enhancement)
                owner_name = row['owner_id'] or "Unknown"
                
                project = ProjectDocument(
                    project_id=row['_id'],
                    title=row['title'],
                    description=row['description'] or "",
                    tags=tags_list,
                    created=str(row['createdAt']) if row['createdAt'] else "",
                    owner=owner_name
                )
                self.projects.append(project)
        
        print(f"✅ Loaded {len(self.projects)} projects from database")
    
    def load_users_from_sql(self) -> None:
        """
        Load users from SQL database.
        
        Fetches all active users with their interests and converts them
        to UserDocument objects for vector search operations.
        """
        print("📁 Loading users from SQL database...")
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT _id, firstName, lastName, interestedTags, 
                       interestedCourses, studyPrograms, createdAt
                FROM Users
                WHERE isBlockedByAdmin = 0
                ORDER BY createdAt DESC
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                # Parse JSON fields
                interested_tags = []
                interested_courses = []
                study_programs = []
                
                if row['interestedTags']:
                    try:
                        interested_tags = json.loads(row['interestedTags'])
                    except json.JSONDecodeError:
                        pass
                
                if row['interestedCourses']:
                    try:
                        interested_courses = json.loads(row['interestedCourses'])
                    except json.JSONDecodeError:
                        pass
                
                if row['studyPrograms']:
                    try:
                        study_programs = json.loads(row['studyPrograms'])
                    except json.JSONDecodeError:
                        pass
                
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
        
        print(f"✅ Loaded {len(self.users)} users from database")
    
    def create_project_embeddings(self) -> None:
        """
        Create vector embeddings for all projects.
        
        Uses OpenAI's text-embedding-3-small model to convert project text
        into 1536-dimensional vectors for semantic similarity search.
        Processes in batches for efficiency.
        
        Note:
            This is the bottleneck for initialization. For production,
            consider caching embeddings in the database (see documentation below).
        """
        print("🔄 Creating embeddings for semantic search...")
        
        if not self.projects:
            print("⚠️  No projects to embed")
            return
        
        texts = [project.to_text() for project in self.projects]
        
        # Batch processing for API efficiency and cost reduction
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
        
        self.embeddings = np.array(embeddings)
        print(f"✅ Embeddings created: {self.embeddings.shape}")
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Cosine similarity measures the angle between vectors, ranging from -1 to 1.
        Higher values indicate more similar embeddings (more semantically related).
        
        Args:
            a: First embedding vector
            b: Second embedding vector
        
        Returns:
            Similarity score between -1 and 1
        """
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def retrieve_relevant_projects(self, query: str, top_k: int = 5) -> List[Tuple[ProjectDocument, float]]:
        """
        Find the most relevant projects for a given query using semantic search.
        
        This is the "Retrieval" part of RAG. It uses vector similarity to find
        projects that are semantically related to the user's query, even if they
        don't share exact keywords.
        
        Args:
            query: User's search query in natural language
            top_k: Number of top results to return
            
        Returns:
            List of (project, similarity_score) tuples, sorted by relevance
        """
        # Create embedding for the query
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = np.array(response.data[0].embedding)
        
        # Calculate similarities with all project embeddings
        similarities = []
        for i, project_embedding in enumerate(self.embeddings):
            similarity = self.cosine_similarity(query_embedding, project_embedding)
            similarities.append((self.projects[i], similarity))
        
        # Sort by similarity (descending) and return top K
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def generate_response(self, query: str, relevant_projects: List[Tuple[ProjectDocument, float]]) -> Dict:
        """
        Generate natural language response based on retrieved projects.
        
        This is the "Generation" part of RAG. It uses GPT-4 to create a contextual,
        helpful response based on the semantically similar projects found.
        
        Args:
            query: User's original query
            relevant_projects: List of (project, similarity_score) tuples from retrieval
            
        Returns:
            Dictionary containing:
                - message: Natural language response from GPT-4
                - projects: List of relevant projects with metadata
        """
        # Build context from relevant projects for GPT
        context = "The following relevant projects were found:\n\n"
        for i, (project, score) in enumerate(relevant_projects, 1):
            context += f"{i}. {project.title}\n"
            context += f"   Description: {project.description}\n"
            context += f"   Tags: {', '.join(project.tags)}\n"
            context += f"   Relevance Score: {score:.3f}\n\n"
        
        # Create prompts for GPT-4
        system_prompt = """You are a helpful assistant that helps users find relevant projects. 
        Answer the user's question based on the provided project information. 
        Be precise, helpful, and mention the most relevant projects."""
        
        user_prompt = f"""Based on these projects:

{context}

Answer the following question: {query}

Provide a helpful, natural language response and mention the most relevant projects."""

        # Generate response with GPT-4
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        answer = completion.choices[0].message.content
        
        # Create structured response matching sqlchatbot.py format
        result = {
            "message": answer,
            "projects": [
                {
                    "_id": project.project_id,
                    "title": project.title,
                    "createdAt": project.created,
                    "relevance_score": float(score)
                }
                for project, score in relevant_projects
            ]
        }
        
        return result
    
    def query(self, question: str, top_k: int = 5) -> str:
        """
        Main query method combining retrieval and generation.
        
        This orchestrates the full RAG pipeline:
        1. Retrieve relevant projects using vector similarity
        2. Generate contextual response using GPT-4
        3. Save interaction to database for logging
        
        Args:
            question: User's natural language query
            top_k: Number of projects to consider for context
            
        Returns:
            JSON string containing response and relevant projects
        """
        print(f"\n🔍 Searching for: '{question}'")
        print("-" * 60)
        
        # Step 1: Retrieval - Find semantically similar projects
        relevant_projects = self.retrieve_relevant_projects(question, top_k)
        
        print(f"📊 Top {len(relevant_projects)} relevant projects found:")
        for project, score in relevant_projects:
            print(f"  - {project.title} (Score: {score:.3f})")
        
        # Step 2: Generation - Create natural language response
        print("\n🤖 Generating response with GPT-4...")
        response = self.generate_response(question, relevant_projects)
        
        # Step 3: Logging - Save to database for analytics
        save_chat_to_db(question, response)
        
        return json.dumps(response, ensure_ascii=False, indent=2)


def main():
    """
    Main function for CLI usage.
    
    Supports two modes:
    1. SQL mode (default): Load from database, optionally sync from API first
    2. File mode: Load from sample.txt for testing
    
    Usage:
        python rag_chatbot.py "Your question here"
        python rag_chatbot.py --sync "Your question"  # Sync from API first
        python rag_chatbot.py --file "Your question"  # Use sample.txt
    """
    print("=" * 60)
    print("🚀 RAG Chatbot - Fast Project Retrieval with SQL Integration")
    print("=" * 60)
    
    # Parse command line arguments
    sync_from_api = False
    data_source = "sql"
    query_args = []
    
    for arg in sys.argv[1:]:
        if arg == "--sync":
            sync_from_api = True
        elif arg == "--file":
            data_source = "file"
        else:
            query_args.append(arg)
    
    # Initialize RAG system
    try:
        chatbot = RAGChatbot(data_source=data_source, sync_from_api=sync_from_api)
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
        print("Please ensure the required files are in the same directory.")
        return
    except pymysql.MySQLError as e:
        print(f"❌ Database error: {e}")
        print("Please ensure MySQL is running and the recsys database exists.")
        return
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Get query from command line or interactive input
    if query_args:
        query = " ".join(query_args)
    else:
        query = input("\n💬 Your question: ")
    
    if not query.strip():
        print("❌ No query provided!")
        return
    
    # Process query
    try:
        result = chatbot.query(query)
        print("\n" + "=" * 60)
        print("📤 RESULT:")
        print("=" * 60)
        print(result)
    except Exception as e:
        print(f"\n❌ Processing error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
