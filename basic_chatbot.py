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

# This basic chatbot has no data synchronization with the database but only accesses the local SQL database. 

import pymysql
import json
import os
import sys
import langdetect
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase

# Datenbankverbindungskonfiguration
connection = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='recsys',
    cursorclass=pymysql.cursors.DictCursor
)

# Funktion zum Speichern des Chats in der Datenbank
def save_chat_to_db(prompt, response):
    try:
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

# Funktion, die den LangChain-Query ausführt
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
    lang = langdetect.detect(prompt)
    
    if lang == 'de':
        specific_prompt = """
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

Außerdem gib nur den Output zurück; nichts vom Input.
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

    # Den Originalprompt mit dem spezifischen Prompt kombinieren
    query = specific_prompt + "\n\n" + prompt
    agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)
    result = agent_executor.invoke(query)

    if 'output' not in result:
        raise ValueError("Kein 'output' Schlüssel im Ergebnis gefunden.")

    try:
        output_data = json.loads(result['output'])
    except json.JSONDecodeError:
        print("Fehler beim Parsen des JSON-Outputs.")
        print("Output:", result['output'])
        raise

    formatted_output = json.dumps(output_data, ensure_ascii=False, separators=(',', ':'))

    # Speichere den Chat in der Datenbank
    save_chat_to_db(prompt, output_data)

    return formatted_output

def main():
    try:
        prompt = sys.argv[1] if len(sys.argv) > 1 else input("Prompt: ")
        print(run_langchain_query(prompt))
    except pymysql.MySQLError as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
