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
#   limitations under the License.*/

import requests
import pymysql
import json
import os
import sys
import langdetect
from datetime import datetime
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase

# Database connection configuration
connection = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='recsys',
    cursorclass=pymysql.cursors.DictCursor
)

def convert_iso_to_mysql_datetime(iso_str):
    try:
        return datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

# Function to save chat into the database
def save_chat_to_db(prompt, response):
    try:
        # Convert the response (which might be a dict) to a JSON string
        response_str = json.dumps(response, ensure_ascii=False)
        
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_log (prompt, response)
                VALUES (%s, %s)
                """,
                (prompt, response_str)
            )
        connection.commit()
    except pymysql.MySQLError as e:
        print(f"Error saving chat to the database: {e}")

def insert_data_from_api():
    import bearer_token
    
    base_url = 'http://localhost:3000/api/'

    headers = {
        'Authorization': f'Bearer {bearer_token.TOKEN}',
        'Content-Type': 'application/json'
    }

    response_projects = requests.get(base_url + 'projects', headers=headers)
    response_users = requests.get(base_url + 'users', headers=headers)
    response_tags = requests.get(base_url + 'tags', headers=headers)

    if response_projects.status_code != 200 or response_users.status_code != 200 or response_tags.status_code != 200:
        print("Failed to fetch data from the API")
        return False

    projects = response_projects.json().get('projects', [])
    users = response_users.json()
    tags = response_tags.json()

    with connection.cursor() as cursor:
        # Leeren der bisherigen Tabellen
        # --------------------------------
        # Achtung: Project_Tags gibt es ja nicht mehr
        cursor.execute("""DELETE FROM Tags""")
        cursor.execute("""DELETE FROM Projects""")
        cursor.execute("""DELETE FROM Users""")
        
        # Tags einfügen
        # --------------------------------
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

        # Users einfügen
        # --------------------------------
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

        # Projects einfügen — jetzt mit "tags" als longtext-Feld
        # --------------------------------
        for project in projects:
            created_at = convert_iso_to_mysql_datetime(project['createdAt'])
            updated_at = convert_iso_to_mysql_datetime(project['updatedAt'])

            owner_id = None
            if isinstance(project['owner'], dict) and '_id' in project['owner']:
                owner_id = project['owner']['_id']

            # Anstatt über Project_Tags zu iterieren, speichern wir hier die Tags als JSON
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

        connection.commit()
        return True


import json

def run_langchain_query(prompt):
    db_config = {
        "host": "127.0.0.1",
        "user": "root",
        "password": "",
        "database": "recsys",
        "port": 3306
    }

    import apikey
    os.environ["OPENAI_API_KEY"] = apikey.APIKEY

    db = SQLDatabase.from_uri(
        f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )

    llm = ChatOpenAI(model="gpt-4-turbo")
    # Erkenne die Sprache des Prompts
    lang = langdetect.detect(prompt)
    agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)
    if lang == 'de':
            specific_prompt ="""
       Ich möchte, dass du nur bestimmte Felder aus der Datenbank extrahierst und in deiner Antwort zurückgibst. Bitte beachte folgende Anforderungen:
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
        }
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

    Verwende keine vertraulichen Daten wie Passwörter, E-Mail-Adressen oder Codes in der Antwort.
    """

    else:
        specific_prompt = """
        I want you to extract only specific fields from the database and return them in your response. Please consider the following requirements:
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

    Always answer in the same language as the following request:
    """
    # Combine the original prompt with the specific prompt
    query = specific_prompt + "\n\n" + prompt
    result = agent_executor.invoke(query)

    if 'output' not in result:
        raise ValueError("Kein 'output' Schlüssel im Ergebnis gefunden.")

    try:
        output_data = json.loads(result['output'])
    except json.JSONDecodeError:
        print("Fehler beim Parsen des JSON-Outputs.")
        print("Output:", result['output'])
        raise

    # Process the result to a correct JSON object without '\n' and other unwanted characters
    formatted_output = json.dumps(output_data, ensure_ascii=False, separators=(',', ':'))

    # Save the interaction to the database
    save_chat_to_db(prompt, output_data)

    return formatted_output


def main():
    try:
        if insert_data_from_api():
            prompt = sys.argv[1] if len(sys.argv) > 1 else input("Prompt: ")
            print(run_langchain_query(prompt))
    except pymysql.MySQLError as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()