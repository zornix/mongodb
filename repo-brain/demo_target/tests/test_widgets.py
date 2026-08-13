def test_widgets__list_returns_all(client):
    resp = client.get("/widgets")
    assert resp.status_code == 200
    assert len(resp.json()["widgets"]) == 2


def test_widgets__get_returns_one(client):
    resp = client.get("/widgets/1")
    assert resp.status_code == 200
    assert resp.json()["widget"]["name"] == "flux capacitor"


def test_widgets__missing_id_uses_error_envelope(client):
    resp = client.get("/widgets/99")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "WIDGET_NOT_FOUND"
