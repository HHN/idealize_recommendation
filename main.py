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

from fastapi import FastAPI, Query
from pydantic import BaseModel
import sqlchatbot
import rag_chatbot
from contextlib import asynccontextmanager
from typing import Optional
from bearer_token import TOKEN
import jwt

# Old sql agent 
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     try:
#         # once ETL sync at startup
#         ok = sqlchatbot.insert_data_from_api()
#         print(f"Initial sync: {ok}")
#     except Exception as e:
#         print(f"Initial sync failed: {e}")
#     yield


# app = FastAPI(lifespan=lifespan)
# End old sql agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Try to sync data from API, but continue even if it fails
    try:
        ok = rag_chatbot.insert_data_from_api()
        print(f"✅ Data sync successful: {ok}")
    except Exception as e:
        print(f"⚠️ Data sync failed (will use existing database): {e}")
    
    # Initialize RAG chatbot (allow startup even if no data exists yet)
    try:
        print("🔄 Initializing RAG chatbot...")
        rag_chatbot.initialize_chatbot()
        print("✅ RAG chatbot initialized and ready")
    except Exception as e:
        print(f"⚠️ WARNING: Chatbot initialization failed: {e}")
        print(f"   Server will start but chatbot may not work until database is populated")
        import traceback
        traceback.print_exc()
        # Don't raise - allow server to start for debugging
    
    yield

app = FastAPI(lifespan=lifespan)

# Define a Pydantic model class to meet the input requirements for the API
class ChatRequest(BaseModel):
    message: str

@app.post("/api/chatbot")
async def chatbot(
    request: ChatRequest,
):
    user_id = get_user_id_from_token(TOKEN)
    if user_id:
        print(f"Request from user: {user_id}")
    else:
        print("No user ID provided, showing all projects")
    
    # Use RAG chatbot to process the query
    bot_response = rag_chatbot.query_projects(request.message, user_id=user_id)

    # Return the bot response as JSON
    return {"response": bot_response}

# @app.post("/api/sqlchatbot")
# async def sql_chatbot(
#     request: ChatRequest,
# ):
    
#     user_id = get_user_id_from_token(TOKEN)
#     if user_id:
#         print(f"Request from user: {user_id}")
#     else:
#         print("No user ID provided, showing all projects")
    
#     # Use sql chatbot to process the query
#     bot_response = sqlchatbot.run_langchain_query(request.message, user_id=user_id) # Old with sqlagent 

#     # Return the bot response as JSON
#     return {"response": bot_response}


def get_user_id_from_token(token: str) -> str:
    """
    Decode JWT token and extract user ID.
    
    Args:
        token: JWT bearer token
        
    Returns:
        User ID string
    """
    try:
        # Decode without verification (if you don't have the secret key)
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get('userId')
    except jwt.DecodeError:
        return None

