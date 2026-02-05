import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from database import Base, get_db
from models import Todo, User

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency to use the test database
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Create the tables in the test database
    Base.metadata.create_all(bind=engine)
    yield
    # Drop the tables after the tests are done
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def auth_headers():
    client.post("/auth/signup", json={"username": "testuser", "email": "test@test.com", "password": "password"})
    response = client.post("/auth/login", data={"username": "testuser", "password": "password"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_todo(auth_headers):
    response = client.post("/crud/todos", json={"title": "Test Todo", "description": "Test Description"}, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "Test Description"
    assert data["id"] is not None
    # Check if the owner_id is correct
    user_response = client.get("/auth/users/me", headers=auth_headers)
    user_id = user_response.json()["id"]
    assert data["owner_id"] == user_id


def test_read_todos(auth_headers):
    client.post("/crud/todos", json={"title": "Test Todo 1"}, headers=auth_headers)
    client.post("/crud/todos", json={"title": "Test Todo 2"}, headers=auth_headers)
    
    response = client.get("/crud/todos", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_read_todo(auth_headers):
    # First create a todo to read
    response = client.post("/crud/todos", json={"title": "Test Todo 2", "description": "Test Description 2"}, headers=auth_headers)
    assert response.status_code == 201
    todo_id = response.json()["id"]

    response = client.get(f"/crud/todos/{todo_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Todo 2"
    assert data["id"] == todo_id

def test_read_todo_not_found(auth_headers):
    response = client.get("/crud/todos/999", headers=auth_headers)
    assert response.status_code == 404

def test_update_todo(auth_headers):
    # First create a todo to update
    response = client.post("/crud/todos", json={"title": "Test Todo 3", "description": "Test Description 3"}, headers=auth_headers)
    assert response.status_code == 201
    todo_id = response.json()["id"]

    response = client.put(f"/crud/todos/{todo_id}", json={"title": "Updated Title", "completed": True}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["completed"] is True

def test_update_todo_not_found(auth_headers):
    response = client.put("/crud/todos/999", json={"title": "Updated Title"}, headers=auth_headers)
    assert response.status_code == 404

def test_delete_todo(auth_headers):
    # First create a todo to delete
    response = client.post("/crud/todos", json={"title": "Test Todo 4", "description": "Test Description 4"}, headers=auth_headers)
    assert response.status_code == 201
    todo_id = response.json()["id"]

    response = client.delete(f"/crud/todos/{todo_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's deleted
    response = client.get(f"/crud/todos/{todo_id}", headers=auth_headers)
    assert response.status_code == 404

def test_delete_todo_not_found(auth_headers):
    response = client.delete("/crud/todos/999", headers=auth_headers)
    assert response.status_code == 404
