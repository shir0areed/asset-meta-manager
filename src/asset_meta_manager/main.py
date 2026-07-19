import argparse
from fastapi import FastAPI, Query, Form, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import tomllib
from pathlib import Path
import uvicorn
from urllib.parse import quote, unquote

from .core.state import AppState, get_supported_formats, get_default_version


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup_event():
    state = app.state.manager
    if state is None:
        print("No database loaded.")
        return

    print("Scanned files:")
    for f in state.files:
        print(" -", f)


@app.get("/")
def root():
    return RedirectResponse(url="/static/ui.html")


@app.get("/instance-info")
def instance_info():
    """
    STEP1 の動作確認用エンドポイント。
    UI 実装前でもブラウザで確認できる。
    """
    state = app.state.manager
    if state is None:
        return {
            "database": None,
            "instance_root": None,
            "sibling_folders": [],
            "format": None,
        }

    return {
        "database": str(state.database_path),
        "instance_root": str(state.instance_root),
        "sibling_folders": [str(p) for p in state.sibling_folders],
        "format": state.get_format(),
    }


@app.get("/databases")
def list_databases():
    """
    database の一覧を返す。
    database が 0 個でも空リストを返す。
    """
    managers = app.state.managers
    current = app.state.manager

    # current の index を求める
    current_index = None
    if current is not None:
        for i, m in enumerate(managers):
            if m is current:
                current_index = i
                break

    return {
        "current": current_index,
        "databases": [
            {
                "index": i,
                "database_path": str(m.database_path),
                "instance_root": str(m.instance_root),
                "format": m.get_format(),
            }
            for i, m in enumerate(managers)
        ]
    }


@app.post("/set-database")
def set_database(index: int = Form(...)):
    """
    UI が選択した database を manager に設定する。
    """
    managers = app.state.managers

    if index < 0 or index >= len(managers):
        return {"ok": False, "error": "Invalid index"}

    app.state.manager = managers[index]
    return {"ok": True}


@app.get("/scan-result")
def scan_result():
    """
    STEP2 の動作確認用エンドポイント。
    スキャンされたファイル一覧を返す。
    """
    state = app.state.manager
    if state is None:
        return {
            "category_columns": [],
            "annotation_columns": [],
            "files": [],
            "format": None,
        }

    root = state.instance_root  # database の親フォルダ
    category_columns = state.load_category_columns()
    annotation_columns = state.load_annotation_columns()

    result = []

    for p in state.files:
        # database からの相対パス（Path）
        rel = p.relative_to(root)
        
        # UI 用に POSIX 文字列へ
        rel_posix = rel.as_posix()

        # ★ meta.json をロード
        meta = state.load_meta(p)
        thumbnail = meta.get("thumbnail", None)

        # 相対パスを分解してフォルダ部分を抽出
        parts = rel_posix.split("/")          # ["foo","bar","buzz","data.zip"]
        folder_parts = parts[:-1]             # ["foo","bar","buzz"]
        
        # ★ STEP5-B：カテゴリ列にフォルダ名を割り当てる
        categories = [
            folder_parts[i] if i < len(folder_parts) else ""
            for i in range(len(category_columns))
        ]

        # ★ アノテーション列（配列で返す）
        ann_dict = meta.get("annotations", {})
        annotations = [
            ann_dict.get(col["id"], "")
            for col in annotation_columns
        ]

        # --- 追加: 固定カテゴリを計算（ユーザー定義カテゴリ数を渡す） ---
        fixed = _compute_fixed_categories_from_rel_with_usercats(rel_posix, len(category_columns))
        vendor = fixed["vendor"]
        artifact = fixed["artifact"]
        version = fixed["version"]

        # name フィールドには artifact を入れる（フロントは name を表示するため）
        name = artifact

        result.append({
            "path": rel_posix,
            "name": name,
            "thumbnail": thumbnail,
            "categories": categories,
            "annotations": annotations,
            "vendor": vendor,
            "artifact": artifact,
            "version": version,
        })

    # ここで format を付与（UI が追加の API 呼び出しなしに判定できるようにする）
    return {
        "category_columns": category_columns,
        "annotation_columns": annotation_columns,
        "files": result,
        "format": state.get_format(),
    }


@app.get("/file")
def download_file(path: str = Query(..., description="Relative POSIX path from database root")):
    """
    STEP4: ファイルダウンロード用エンドポイント。
    path は相対 POSIX パスで渡す。
    既存のダウンロード挙動はそのまま維持する（Content-Disposition は attachment 相当）。
    """
    state = app.state.manager
    if state is None:
        return FileResponse(None)  # 実際には UI 側で呼ばれない

    abs_path = _resolve_path_from_rel(state.instance_root, path)

    # FileResponse はデフォルトでダウンロード向けの挙動になる（ブラウザ依存）
    return FileResponse(abs_path, filename=abs_path.name)


@app.get("/category_columns")
def get_category_columns():
    state = app.state.manager
    if state is None:
        return {"category_columns": []}
    return {"category_columns": state.load_category_columns()}


@app.post("/category_columns/add")
def add_category_columns(name: str = Form(...)):
    state = app.state.manager
    if state is None:
        return {"ok": False}
    state.add_category_columns(name)
    return {"ok": True}


@app.post("/category_columns/remove")
def remove_category_columns(name: str = Form(...)):
    state = app.state.manager
    if state is None:
        return {"ok": False}  # 実際には UI 側で呼ばれない
    state.remove_category_columns(name)
    return {"ok": True}


@app.get("/annotation_columns")
def get_annotation_columns():
    state = app.state.manager
    if state is None:
        return {"annotation_columns": []}
    return {"annotation_columns": state.load_annotation_columns()}


@app.post("/annotation_columns/add")
def add_annotation_column(column_id: str = Form(...), label: str = Form(...), type: str = Form(...)):
    state = app.state.manager
    if state is None:
        return {"ok": False}
    ok = state.add_annotation_column(column_id, label, type)
    return {"ok": ok}


@app.post("/annotation_columns/remove")
def remove_annotation_column(column_id: str = Form(...)):
    state = app.state.manager
    if state is None:
        return {"ok": False}  # 実際には UI 側で呼ばれない
    state.remove_annotation_column(column_id)
    return {"ok": True}


@app.post("/meta/update-name")
def update_name(path: str = Form(...), value: str = Form(...)):
    return {"ok": False}


@app.post("/meta/update-annotation")
def update_annotation(path: str = Form(...), column_id: str = Form(...), value: str | None = Form("")):
    state = app.state.manager
    if state is None:
        return {"ok": False}  # 実際には UI 側で呼ばれない
    state.update_annotation(path, column_id, value or "")
    return {"ok": True}


@app.post("/meta/update-thumbnail")
def update_thumbnail(path: str = Form(...), value: str = Form(...)):
    state = app.state.manager
    if state is None:
        return {"ok": False}  # 実際には UI 側で呼ばれない
    state.update_thumbnail(path, value)
    return {"ok": True}


@app.post("/meta/delete-thumbnail")
def delete_thumbnail(path: str = Form(...)):
    state = app.state.manager
    if state is None:
        return {"ok": False}  # 実際には UI 側で呼ばれない
    state.update_thumbnail(path, None)
    return {"ok": True}


@app.get("/preview")
def preview(path: str = Query(..., description="Relative POSIX path from database root")):
    """
    プレビュー用エンドポイント（最小実装）。
    download_file と重複しないよう、ファイル解決は共通ヘルパーを使う。
    返却時に Content-Disposition を inline にしてブラウザで開かせる。
    """
    state = app.state.manager
    if state is None:
        raise HTTPException(status_code=404, detail="No database selected")

    abs_path = _resolve_path_from_rel(state.instance_root, path)

    # inline 指定の Content-Disposition を付けて返す
    fname = abs_path.name
    # ASCII フォールバック（ASCII に変換して空なら 'file'）
    ascii_fname = fname.encode("ascii", "ignore").decode("ascii") or "file"
    # UTF-8 を URL エンコードした filename*
    encoded = quote(fname, safe='')
    content_disposition = f'inline; filename="{ascii_fname}"; filename*=UTF-8\'\'{encoded}'

    headers = {"Content-Disposition": content_disposition}
    return FileResponse(abs_path, filename=abs_path.name, headers=headers)


@app.get("/formats")
def get_formats():
    """
    サポートしているフォーマット一覧を返す。
    """
    return {"formats": get_supported_formats()}


@app.post("/set-format")
def set_format(fmt: str = Form(...)):
    """
    選択されたフォーマットを現在選択中の database に適用する。
    フォーマットがサポート外の場合はエラーを返す。
    """
    state = app.state.manager
    if state is None:
        return {"ok": False, "error": "No database selected"}

    # set_format は AppState 側でサポートチェックを行い、True/False を返す想定
    ok = state.set_format(fmt)
    if not ok:
        return {
            "ok": False,
            "error": "Unsupported format",
            "supported": get_supported_formats()
        }
    return {"ok": True, "format": state.get_format()}


def _resolve_path_from_rel(root: Path, rel_posix: str) -> Path:
    """
    相対 POSIX パス文字列を受け取り、instance_root の下にある実ファイルの絶対パスを返す。
    見つからない / instance_root の外に出る場合は HTTPException(404) を投げる。
    共通化して download_file と preview で使う。
    （Python 3.9 以上を前提に is_relative_to を使う実装）
    """
    # URL デコードして Path に戻す
    rel = Path(unquote(rel_posix))
    abs_path = (root / rel).resolve()

    # 安全チェック: instance_root の外に出ないこと
    if not abs_path.is_file() or not abs_path.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Not found")

    return abs_path


# --- 追加ユーティリティ: パス分解（カテゴリ列を考慮した固定カテゴリ割当） ---
def _compute_fixed_categories_from_rel_with_usercats(rel_posix: str, user_cat_count: int):
    """
    rel_posix: 'foo/bar/buzz/hoge/piyo.zip' のような POSIX 相対パス（先頭に / があっても可）
    user_cat_count: category_columns の数（ユーザー定義カテゴリ列数）
    戻り値: dict with keys 'vendor','artifact','version'
    割当ルール: remaining の長さで左寄せ/右寄せを切り替える（詳細は既存仕様）
    """
    p = rel_posix.lstrip("/")
    parts = [x for x in p.split("/") if x != ""] if p != "" else []

    # ファイル名と拡張子除去
    filename = parts[-1] if len(parts) >= 1 else ""
    if "." in filename:
        name_without_ext = filename.rsplit(".", 1)[0]
    else:
        name_without_ext = filename

    folder_parts = parts[:-1]  # フォルダ部分
    # remaining はユーザー定義カテゴリを除いた残り
    remaining = folder_parts[user_cat_count:] if user_cat_count < len(folder_parts) else []
    r = len(remaining)

    vendor = ""
    artifact = ""
    version = None  # デフォルトは None にして最後に一度だけフォールバック

    if r >= 4:
        # 右寄せ: last 3 を vendor/artifact/version に割当
        vendor = remaining[r - 3]
        artifact = remaining[r - 2]
        version = remaining[r - 1]
    elif r == 3:
        # 左寄せ: 先頭->vendor, 次->artifact, 次->version
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


def load_databases_from_toml(toml_path: Path):
    if not toml_path.exists():
        raise FileNotFoundError(f"TOML not found: {toml_path}")

    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    # TOML の仕様:
    # [[database]]
    # path = "/path/to/db"
    db_entries = data.get("database", [])

    managers = []
    for entry in db_entries:
        p = Path(entry["path"])
        managers.append(AppState(database_path=p))

    return managers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "database_toml",
        nargs="?",
        default="databases.toml",
        help="TOML file listing databases"
    )
    args = parser.parse_args()

    toml_path = Path(args.database_toml)

    # database をロード
    managers = load_databases_from_toml(toml_path)
    app.state.managers = managers
    app.state.manager = managers[0] if managers else None

    # uvicorn 起動
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
