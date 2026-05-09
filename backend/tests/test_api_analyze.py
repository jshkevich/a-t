def test_analyze_endpoint_validation(client):
    response = client.post("/analyze", json={"username": "alex", "messages": []})
    assert response.status_code == 400
    assert "Список сообщений пуст" in response.text


def test_semantic_search_endpoint_validation(client):
    response = client.post("/semantic-search", json={"query": "", "messages": ["test"]})
    assert response.status_code == 422

