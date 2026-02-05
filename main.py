from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from routes import todos, chatbot, auth, dashboard
from models import Base
from database import engine

load_dotenv()

app = FastAPI()

# CORS configuration
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
    "nestlyflow.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the To-Do Application API!"}

app.include_router(todos.router, prefix="/crud", tags=["todos"])
app.include_router(chatbot.router, prefix="/chat", tags=["chatbot"])
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])

# You can add more configurations or startup events here if needed.
# For example, if you wanted to create tables at startup (though task T005 says they already exist):
@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
