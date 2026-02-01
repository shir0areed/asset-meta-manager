from pathlib import Path
from typing import List
import json
import sqlite3

META_SUFFIX = ".ameta"

class AppState:
    """
    STEP1: identity とインスタンスルートを保持
    STEP2: フォルダスキャン結果（ファイル一覧）を保持
    STEP3: 空 meta の自動生成
    """

    def __init__(self, identity_path: str):
        self.identity_path: Path
        self.instance_root: Path
        self.sibling_folders: List[Path] = []
        self.files: List[Path] = []

        self._load_identity(identity_path)
        self._scan_files()
        self._ensure_meta_files()  # ★ STEP3
        self._init_db()

    def load_schema(self) -> list[str]:
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM folder_schema ORDER BY id")
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows


    def add_schema(self, name: str):
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO folder_schema (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()


    def remove_schema(self, name: str):
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM folder_schema WHERE name = ?", (name,))
        conn.commit()
        conn.close()

    # ------------------------------
    # private methods
    # ------------------------------

    def _load_identity(self, identity: str) -> None:
        identity_path = Path(identity).resolve()

        if not identity_path.exists() or not identity_path.is_file():
            raise FileNotFoundError(f"identity file not found: {identity_path}")

        self.identity_path = identity_path
        self.instance_root = identity_path.parent

        # 同階層のフォルダ一覧を取得
        self.sibling_folders = [
            p for p in self.instance_root.iterdir() if p.is_dir()
        ]

    def _scan_files(self) -> None:
        """
        STEP2: sibling_folders の中だけを再帰スキャン。
        .ameta ファイルはスキャン対象外。
        """
        result: List[Path] = []

        # 同階層フォルダごとに再帰スキャン
        for folder in self.sibling_folders:
            for path in folder.rglob("*"):
                if path.is_file() and not path.suffix == META_SUFFIX:
                    result.append(path)

        self.files = result

    def _ensure_meta_files(self) -> None:
        """
        STEP3: 各ファイルに対して <filename>.ameta を生成する。
        既に存在する場合はスキップ。
        """
        for file_path in self.files:
            meta_path = file_path.with_suffix(file_path.suffix + META_SUFFIX)

            if not meta_path.exists():
                # 空 JSON を書き込む
                meta_path.write_text("{}", encoding="utf-8")

    def _init_db(self):
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()

        # スキーマテーブル
        cur.execute("""
            CREATE TABLE IF NOT EXISTS folder_schema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        conn.commit()
        conn.close()
