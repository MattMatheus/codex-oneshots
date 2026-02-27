from src.dart_board.storage import DartBoardStore


def test_store_user_session_throw_roundtrip(tmp_path):
    db = tmp_path / "test.db"
    store = DartBoardStore(str(db))

    user = store.create_user("u1", "Matt")
    assert user.id == "u1"

    session = store.create_session("s1", "u1", "local-video")
    assert session.user_id == "u1"

    throw = store.add_throw("u1", "s1", 0.5, 0.5, 0.9)
    assert throw.id > 0

    throws = store.list_throws_for_user("u1")
    assert len(throws) == 1
    assert throws[0].x_norm == 0.5
