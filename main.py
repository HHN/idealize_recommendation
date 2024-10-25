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

    sqlchatbot.main()
    print("test")
    user_message = request.message
    
    # Use the extracted message with your `run_langchain_query` function
    bot_response = sqlchatbot.run_langchain_query(user_message)
    
    # Return the bot response as JSON
    return {"response": bot_response}

