from pathlib import Path
from typing import Optional, List


class AppState:
    """
    STEP1: identity とインスタンスルートを保持
    STEP2: フォルダスキャン結果（ファイル一覧）を保持
    """

    def __init__(self, identity_path: str):
        self.identity_path: Optional[Path] = None
        self.instance_root: Optional[Path] = None
        self.sibling_folders: List[Path] = []
        
        # STEP2: スキャン結果
        self.files: List[Path] = []

        self.load_identity(identity_path)
        self.scan_files()

    def load_identity(self, identity: str) -> None:
        identity_path = Path(identity).resolve()

        if not identity_path.exists() or not identity_path.is_file():
            raise FileNotFoundError(f"identity file not found: {identity_path}")

        self.identity_path = identity_path
        self.instance_root = identity_path.parent

        # 同階層のフォルダ一覧を取得
        self.sibling_folders = [
            p for p in self.instance_root.iterdir() if p.is_dir()
        ]

    def scan_files(self) -> None:
        """
        STEP2: インスタンスルートと同階層のフォルダ（sibling_folders）だけを
        再帰的にスキャンし、ファイル一覧を self.files に格納する。
        identity と同階層の直下ファイルはスキャンしない。
        """
        if self.instance_root is None:
            raise RuntimeError("identity not loaded")

        result: List[Path] = []

        # 同階層フォルダごとに再帰スキャン
        for folder in self.sibling_folders:
            for path in folder.rglob("*"):
                if path.is_file():
                    result.append(path)

        self.files = result

