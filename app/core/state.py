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
    STEP6-A: アノテーション列（id + label）の編集
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

    # ============================================================
    # カテゴリ列
    # ============================================================

    def load_category_columns(self) -> list[str]:
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM category_columns ORDER BY id")
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows


    def add_category_columns(self, name: str):
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO category_columns (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()


    def remove_category_columns(self, name: str):
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM category_columns WHERE name = ?", (name,))
        conn.commit()
        conn.close()

    # ============================================================
    # アノテーション列（id + label）
    # ============================================================

    def load_annotation_columns(self) -> list[dict]:
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("SELECT column_id, label FROM annotation_columns ORDER BY id")
        rows = [{"id": r[0], "label": r[1]} for r in cur.fetchall()]
        conn.close()
        return rows

    def add_annotation_column(self, column_id: str, label: str) -> bool:
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()

        # 既存IDチェック
        cur.execute("SELECT COUNT(*) FROM annotation_columns WHERE column_id = ?", (column_id,))
        if cur.fetchone()[0] > 0:
            conn.close()
            return False

        cur.execute(
            "INSERT INTO annotation_columns (column_id, label) VALUES (?, ?)",
            (column_id, label)
        )
        conn.commit()
        conn.close()
        return True

    def remove_annotation_column(self, column_id: str):
        conn = sqlite3.connect(self.identity_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM annotation_columns WHERE column_id = ?", (column_id,))
        conn.commit()
        conn.close()

    # ============================================================
    # STEP6.5-B: meta.json のロード
    # ============================================================
    def load_meta(self, file_path: Path) -> dict:
        meta_path = file_path.with_suffix(file_path.suffix + META_SUFFIX)
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except:
            return {}

    # ============================================================
    # STEP6.5-B: meta.json の保存
    # ============================================================
    def save_meta(self, file_path: Path, meta: dict):
        meta_path = file_path.with_suffix(file_path.suffix + META_SUFFIX)
        if not meta_path.exists():
            return
        try:
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            return


    # ============================================================
    # 名前の更新
    # ============================================================
    def update_name(self, rel_path: str, new_name: str):
        file_path = self.instance_root / rel_path
        meta = self.load_meta(file_path)
        meta["name"] = new_name
        self.save_meta(file_path, meta)

    # ============================================================
    # アノテーションの更新
    # ============================================================
    def update_annotation(self, rel_path: str, column_id: str, value: str):
        file_path = self.instance_root / rel_path
        meta = self.load_meta(file_path)
        if "annotations" not in meta:
            meta["annotations"] = {}
        meta["annotations"][column_id] = value
        self.save_meta(file_path, meta)

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

        # カテゴリ列
        cur.execute("""
            CREATE TABLE IF NOT EXISTS category_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # アノテーション列
        cur.execute("""
            CREATE TABLE IF NOT EXISTS annotation_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_id TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()
