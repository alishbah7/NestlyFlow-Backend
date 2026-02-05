def test_long_password(clear_tables):
    long_password = "a" * 100
    response = client.post("/auth/signup", json={"username": "testuser", "email": "test@example.com", "password": long_password})
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"

    response = client.post("/auth/login", data={"username": "testuser", "password": long_password})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"