"""End-to-end tests. They need PostgreSQL with pgvector (docker compose up -d db)."""

LETTER = (b"Bonavista, July 1892. The cod fishery this season has been poor and many families "
          b"are worried about the winter. The schooner Mary Ann returned from the Labrador coast.")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_admin_pages_need_login(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


def test_wrong_password(client):
    r = client.post("/admin/login", data={"password": "nope"})
    assert r.status_code == 401


def test_upload_process_search_and_ask(admin_client):
    r = admin_client.post("/admin/upload", files=[("files", ("letter_1892.txt", LETTER, "text/plain"))],
                          data={"source": "Test collection"}, follow_redirects=False)
    assert r.status_code == 303

    docs = admin_client.get("/api/documents").json()
    assert len(docs) == 1
    doc = docs[0]
    assert doc["status"] == "done", doc["error"]
    assert doc["date"] == "1892"
    assert doc["type"] == "Text"
    assert doc["source"] == "Test collection"

    found = admin_client.get("/api/search", params={"q": "Bonavista cod"}).json()
    assert found["count"] == 1
    assert found["results"][0]["id"] == doc["id"]

    assert admin_client.get("/api/search", params={"q": "Bonavista", "year_from": "1900"}).json()["count"] == 0

    answer = admin_client.post("/api/ask", json={"question": "How was the cod fishery in Bonavista?"}).json()
    assert answer["sources"][0]["document_id"] == doc["id"]

    page = admin_client.get(f"/item/{doc['id']}")
    assert page.status_code == 200 and "Bonavista" in page.text


def test_duplicate_and_unsupported_files(admin_client):
    for _ in range(2):
        admin_client.post("/admin/upload", files=[("files", ("a.txt", LETTER, "text/plain"))])
    admin_client.post("/admin/upload", files=[("files", ("bad.exe", b"MZ...", "application/octet-stream"))])
    assert len(admin_client.get("/api/documents").json()) == 1


def test_archivist_can_correct_metadata(admin_client):
    admin_client.post("/admin/upload", files=[("files", ("a.txt", LETTER, "text/plain"))])
    doc_id = admin_client.get("/api/documents").json()[0]["id"]
    admin_client.post(f"/admin/item/{doc_id}", data={"title": "Letter from Bonavista", "subject": "fishery; Labrador"})
    doc = admin_client.get(f"/api/documents/{doc_id}").json()
    assert doc["title"] == "Letter from Bonavista"
    assert doc["subject"] == ["fishery", "Labrador"]


def test_ask_rejects_empty_question(client):
    assert client.post("/api/ask", json={"question": "  "}).status_code == 400
