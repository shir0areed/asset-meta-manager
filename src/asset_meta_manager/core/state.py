from pathlib import Path
from typing import Dict, List, Tuple
import json
import sqlite3

META_SUFFIX = ".ameta"
FORMATS = ["zip", "raw"]
DEFAULT_FORMAT = FORMATS[0]
DEFAULT_VERSION = "1.0.0"


class AppState:
    """
    STEP1: database とインスタンスルートを保持
    STEP2: フォルダスキャン結果（ファイル一覧）を保持
    STEP3: 空 meta の自動生成
    STEP6-A: アノテーション列（id + label）の編集
    """

    def __init__(self, database_path: str):
        self.database_path: Path
        self.instance_root: Path
        self.sibling_folders: List[Path] = []
        self.files: List[Path] = []
        self.adira_index: Dict[Tuple[str, str], Dict[str, Path]] = {}

        self._load_database(database_path)
        self._scan_files()
        self._ensure_meta_files()  # ★ STEP3
        self._init_db()

    # ============================================================
    # カテゴリ列
    # ============================================================

    def load_category_columns(self) -> list[str]:
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM category_columns ORDER BY id")
            rows = [r[0] for r in cur.fetchall()]
        return rows

    def add_category_columns(self, name: str):
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO category_columns (name) VALUES (?)", (name,))
            conn.commit()

    def remove_category_columns(self, name: str):
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM category_columns WHERE name = ?", (name,))
            conn.commit()

    # ============================================================
    # アノテーション列（id + label）
    # ============================================================

    def load_annotation_columns(self) -> list[dict]:
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT column_id, label, type FROM annotation_columns ORDER BY id")
            rows = [{"id": r[0], "label": r[1], "type": r[2]} for r in cur.fetchall()]
        return rows

    def add_annotation_column(self, column_id: str, label: str, type: str) -> bool:
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()

            # 既存IDチェック
            cur.execute("SELECT COUNT(*) FROM annotation_columns WHERE column_id = ?", (column_id,))
            if cur.fetchone()[0] > 0:
                return False

            cur.execute(
                "INSERT INTO annotation_columns (column_id, label, type) VALUES (?, ?, ?)",
                (column_id, label, type)
            )
            conn.commit()
        return True

    def remove_annotation_column(self, column_id: str):
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM annotation_columns WHERE column_id = ?", (column_id,))
            conn.commit()

    # ============================================================
    # STEP6.5-B: meta.json のロード
    # ============================================================
    def load_meta(self, file_path: Path) -> dict:
        meta_path = file_path.with_suffix(file_path.suffix + META_SUFFIX)
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
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
    # アノテーションの更新
    # ============================================================
    def update_annotation(self, rel_path: str, column_id: str, value: str):
        file_path = self.instance_root / rel_path
        meta = self.load_meta(file_path)
        if "annotations" not in meta:
            meta["annotations"] = {}
        meta["annotations"][column_id] = value
        self.save_meta(file_path, meta)

    # ============================================================
    # サムネイルの更新
    # ============================================================
    def update_thumbnail(self, rel_path: str, base64_data: str | None):
        file_path = self.instance_root / rel_path
        meta = self.load_meta(file_path)

        if base64_data is None:
            # 削除
            meta.pop("thumbnail", None)
        else:
            # 更新
            meta["thumbnail"] = base64_data
        self.save_meta(file_path, meta)

    # ------------------------------
    # private methods
    # ------------------------------

    def _load_database(self, database: str) -> None:
        database_path = Path(database).resolve()

        if not database_path.exists() or not database_path.is_file():
            raise FileNotFoundError(f"database file not found: {database_path}")

        self.database_path = database_path
        self.instance_root = database_path.parent

        # 同階層のフォルダ一覧を取得
        self.sibling_folders = [
            p for p in self.instance_root.iterdir() if p.is_dir()
        ]

    def _scan_files(self) -> None:
        """
        STEP2: sibling_folders の中だけを再帰スキャン。
        .ameta ファイルはスキャン対象外。
        .aignore が置かれたフォルダは無視。
        """
        result: List[Path] = []

        # ★ sibling_folders 配下を再帰的に見て .aignore を探す
        ignore_dirs = set()
        for folder in self.sibling_folders:
            for path in folder.rglob(".aignore"):
                if path.is_file():
                    ignore_dirs.add(path.parent)

        # 同階層フォルダごとに再帰スキャン
        for folder in self.sibling_folders:
            for path in folder.rglob("*"):

                # ★ ignore フォルダ配下はスキップ
                if any(path.is_relative_to(ig) for ig in ignore_dirs):
                    continue

                if path.is_file() and not path.suffix == META_SUFFIX:
                    result.append(path)

        self.files = result

        category_columns = self.load_category_columns()
        user_cat_count = len(category_columns)

        for file_path in self.files:
            rel = file_path.relative_to(self.instance_root)
            fixed = compute_fixed_categories(rel, user_cat_count)

            # _scan_files の最後
            key = (fixed["vendor"], fixed["artifact"])
            version = fixed["version"]

            if key not in self.adira_index:
                self.adira_index[key] = {}

            self.adira_index[key][version] = file_path

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
        with sqlite3.connect(self.database_path) as conn:
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
                    label TEXT NOT NULL,
                    type TEXT NOT NULL
                )
            """)

            # settings テーブル（key/value）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            conn.commit()

    def get_format(self) -> str:
        """
        settings テーブルから format を取得して返す。
        存在しなければ INSERT OR IGNORE で既定値を挿入してから取得する（遅延初期化）。
        """
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()

            # 存在しなければ既定値を挿入する（INSERT OR IGNORE により原子的に存在判定と挿入が行われる）
            cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("format", DEFAULT_FORMAT))
            conn.commit()

            # その後に値を取得する
            cur.execute("SELECT value FROM settings WHERE key = ?", ("format",))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
        return DEFAULT_FORMAT

    def set_format(self, fmt: str):
        """DB に format を保存する（キャッシュは持たない）"""
        fmt = fmt or DEFAULT_FORMAT
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("format", fmt))
            conn.commit()
        return True
    
    # ============================================================
    # ADIRA: マニフェスト追加ファイル生成
    # ============================================================
    def generate_manifest_fragment(self, rel_path: str) -> dict:
        # rel_path を Path に変換
        rel = Path(rel_path)

        # vendor / artifact / version は固定カテゴリから取得
        user_cat_count = len(self.load_category_columns())
        fixed = compute_fixed_categories(rel, user_cat_count)

        vendor = fixed["vendor"]
        artifact = fixed["artifact"]
        version = fixed["version"]

        # ADIRA 仕様では format は常に native
        fmt = "native"

        # 依存IDは vendor-artifact（正規化なし）
        dep_id = f"{vendor}-{artifact}" if vendor else artifact

        # ★ アーカイブ形式の自動判定
        transform = detect_archive_format(rel)

        native_section = {}
        if transform:
            native_section["transform"] = transform
            native_section.setdefault(transform, {})["strip_root"] = True

        dep_entry = {
            "vendor": vendor,
            "artifact": artifact,
            "version": version,
            "format": fmt,
        }

        if native_section:
            dep_entry["native"] = native_section

        return {
            "dependencies": {
                dep_id: dep_entry
            }
        }

def get_supported_formats() -> List[str]:
    """サポートしているフォーマット一覧を返す（順序は重要、デフォルトは先頭要素）。"""
    return list(FORMATS)

def get_default_version() -> str:
    """デフォルトバージョンを返す"""
    return DEFAULT_VERSION

def compute_fixed_categories(rel: Path, user_cat_count: int) -> dict:
    """
    rel: Path オブジェクト（例: Path("foo/bar/buzz/hoge/piyo.zip")）
    user_cat_count: category_columns の数（ユーザー定義カテゴリ列数）

    戻り値: dict with keys 'vendor','artifact','version'
    """
    parts = rel.parts  # ('foo','bar','buzz','hoge','piyo.zip')

    name_without_ext = rel.stem
    folder_parts = parts[:-1]  # フォルダ部分

    # remaining はユーザー定義カテゴリを除いた残り
    remaining = folder_parts[user_cat_count:] if user_cat_count < len(folder_parts) else []
    r = len(remaining)

    vendor = ""
    artifact = ""
    version = None

    if r >= 4:
        vendor = remaining[r - 3]
        artifact = remaining[r - 2]
        version = remaining[r - 1]
    elif r == 3:
        vendor = remaining[0]
        artifact = remaining[1]
        version = remaining[2]
    elif r == 2:
        vendor = remaining[0]
        artifact = remaining[1]
        version = get_default_version()
    elif r == 1:
        vendor = remaining[0]
        artifact = name_without_ext
        version = get_default_version()
    else:  # r == 0
        vendor = ""
        artifact = name_without_ext
        version = get_default_version()

    return {"vendor": vendor, "artifact": artifact, "version": version}

def detect_archive_format(rel: Path) -> str | None:
    # すべて小文字化
    suffix = rel.suffix.lower()
    suffixes = [s.lower() for s in rel.suffixes]

    # 複合拡張子
    if suffixes == [".tar", ".gz"]:
        return "tgz"

    # 単一拡張子
    if suffix == ".zip":
        return "zip"
    if suffix == ".rar":
        return "rar"
    if suffix == ".lzh":
        return "lzh"
    if suffix == ".tgz":
        return "tgz"

    # raw（非アーカイブ）
    return None
