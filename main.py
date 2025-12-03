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
    
    # Initialize RAG chatbot (required - will fail startup if this fails)
    try:
        print("🔄 Initializing RAG chatbot...")
        rag_chatbot.initialize_chatbot()
        print("✅ RAG chatbot initialized and ready")
    except Exception as e:
        print(f"❌ CRITICAL: Chatbot initialization failed: {e}")
        import traceback
        traceback.print_exc()
        # Re-raise to prevent server from starting with broken chatbot
        raise
    
    yield

app = FastAPI(lifespan=lifespan)

# Define a Pydantic model class to meet the input requirements for the API
class ChatRequest(BaseModel):
    message: str

# Create an API endpoint that accepts POST requests with user_id as URL parameter
@app.post("/api/chatbot")
async def chatbot(
    request: ChatRequest,
    id: Optional[str] = Query(None, description="User ID to exclude own projects")
):
    # bot_response = sqlchatbot.run_langchain_query(request.message) # Old with sqlagent  
    if id:
        print(f"Request from user: {id}")
    else:
        print("No user ID provided, showing all projects")
    
    # Use RAG chatbot to process the query
    bot_response = rag_chatbot.query_projects(request.message, user_id=id)

    # Return the bot response as JSON
    return {"response": bot_response}

