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

from fastapi import FastAPI
from pydantic import BaseModel
import sqlchatbot

app = FastAPI()

# Define a Pydantic model class to meet the input requirements for the API
class ChatRequest(BaseModel):
    message: str

# Create an API endpoint that accepts POST requests
@app.post("/api/chatbot")
async def chatbot(request: ChatRequest):
    #return {"response": "Test response"}

    sqlchatbot.main()
    print("test")
    user_message = request.message
    
    # Use the extracted message with your `run_langchain_query` function
    bot_response = sqlchatbot.run_langchain_query(user_message)
    
    # Return the bot response as JSON
    return {"response": bot_response}

