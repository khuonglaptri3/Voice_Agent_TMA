"""SQLite-backed episodic interaction storage."""
class SQLiteEpisodicStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
