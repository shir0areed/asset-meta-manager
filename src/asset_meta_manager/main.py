import argparse
from fastapi import FastAPI, Query, Form, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
import tomllib
import tomli_w
import hashlib
from pathlib import Path
import uvicorn
from urllib.parse import quote, unquote

from .core.state import (
    AppState,
    get_supported_formats,
    compute_fixed_categories,
) 


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

    # current の index を求める（辞書だが UI のため index を返す）
    current_index = None
    if current is not None:
        for i, m in enumerate(managers.values()):
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
            for i, m in enumerate(managers.values())
        ]
    }


@app.post("/set-database")
def set_database(index: int = Form(...)):
    """
    UI が選択した database を manager に設定する。
    """
    managers = app.state.managers
    keys = list(managers.keys())

    if index < 0 or index >= len(keys):
        return {"ok": False, "error": "Invalid index"}

    app.state.manager = managers[keys[index]]
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
        fixed = compute_fixed_categories(rel, len(category_columns))
        vendor = fixed["vendor"]
        artifact = fixed["artifact"]
        version = fixed["version"]

        result.append({
            "path": rel_posix,
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


@app.get("/adira")
def adira_manifest(path: str = Query(..., description="Relative POSIX path from database root")):
    """
    ADIRA マニフェスト追加ファイルを生成して返す。
    path は相対 POSIX パス（他の API と統一）。
    """
    state = app.state.manager
    if state is None:
        raise HTTPException(status_code=404, detail="No database selected")

    # ★ rel_path をそのまま渡す（Path への変換は state 側の責務）
    fragment_dict = state.generate_manifest_fragment(path)

    # TOML に変換
    toml_text = tomli_w.dumps(fragment_dict)

    # 依存IDを取得
    dep_id = list(fragment_dict["dependencies"].keys())[0]
    fname = f"{dep_id}.adira.toml"

    # ★ preview() と同じヘッダ正規化
    ascii_fname = fname.encode("ascii", "ignore").decode("ascii") or "file"
    encoded = quote(fname, safe='')
    content_disposition = (
        f'attachment; filename="{ascii_fname}"; filename*=UTF-8\'\'{encoded}'
    )

    headers = {"Content-Disposition": content_disposition}

    return Response(toml_text, media_type="text/plain", headers=headers)


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


def _decode_hex(s: str) -> str:
    try:
        return bytes.fromhex(s).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid hex string: {s}")


@app.get("/adira/v2/{artifact_hex}/tags/list")
@app.get("/adira/v2/{vendor_hex}/{artifact_hex}/tags/list")
def adira_tags_list(vendor_hex: str = "", artifact_hex: str = ""):
    vendor = _decode_hex(vendor_hex) if vendor_hex else ""
    artifact = _decode_hex(artifact_hex)

    managers = app.state.managers
    if not managers:
        raise HTTPException(status_code=404, detail="No databases loaded")

    tags = []

    for state in managers.values():
        fmt = state.get_format()
        root = state.instance_root
        category_columns = state.load_category_columns()

        for p in state.files:
            rel = p.relative_to(root)
            fixed = compute_fixed_categories(rel, len(category_columns))

            # vendor="" のときは空文字列と比較する（フォールバックしない）
            if fixed["vendor"] == vendor and fixed["artifact"] == artifact:
                version = fixed["version"]
                tag = f"{version}-{fmt}"
                tags.append(tag)

    return {
        "name": artifact_hex if vendor_hex == "" else f"{vendor_hex}/{artifact_hex}",
        "tags": sorted(set(tags)),
    }


@app.get("/adira/v2/{artifact}/manifests/{tag}")
@app.get("/adira/v2/{vendor_hex}/{artifact_hex}/manifests/{tag}")
def adira_manifest_tag(vendor_hex: str = "", artifact_hex: str = "", tag: str = ""):
    vendor = _decode_hex(vendor_hex)
    artifact = _decode_hex(artifact_hex)

    # tag = version-format を分解する（最も右側のハイフン）
    try:
        version, fmt = tag.rsplit("-", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tag format")

    managers = app.state.managers
    if not managers:
        raise HTTPException(status_code=404, detail="No databases loaded")

    # format が一致する manager のみ検索
    candidates = [m for m in managers.values() if m.get_format() == fmt]

    if not candidates:
        raise HTTPException(status_code=404, detail=f"No database with format '{fmt}'")

    for state in candidates:
        root = state.instance_root
        category_columns = state.load_category_columns()

        for p in state.files:
            rel = p.relative_to(root)
            fixed = compute_fixed_categories(rel, len(category_columns))

            if fixed["vendor"] == vendor and fixed["artifact"] == artifact and fixed["version"] == version:
                file_bytes = p.read_bytes()
                digest = "sha256:" + hashlib.sha256(file_bytes).hexdigest()

                return {
                    "schemaVersion": 2,
                    "mediaType": "application/vnd.adira.manifest.v1+json",
                    "layers": [
                        {
                            "mediaType": "application/octet-stream",
                            "digest": digest,
                            "size": len(file_bytes),
                        }
                    ]
                }

    raise HTTPException(status_code=404, detail="Not found")


@app.get("/adira/v2/{artifact}/blobs/{digest}")
@app.get("/adira/v2/{vendor_hex}/{artifact_hex}/blobs/{digest}")
def adira_blob(vendor_hex: str = "", artifact_hex: str = "", digest: str = ""):
    vendor = _decode_hex(vendor_hex)
    artifact = _decode_hex(artifact_hex)

    managers = app.state.managers
    if not managers:
        raise HTTPException(status_code=404, detail="No databases loaded")

    for state in managers.values():
        root = state.instance_root
        category_columns = state.load_category_columns()

        for p in state.files:
            rel = p.relative_to(root)
            fixed = compute_fixed_categories(rel, len(category_columns))

            file_bytes = p.read_bytes()
            file_digest = "sha256:" + hashlib.sha256(file_bytes).hexdigest()

            if fixed["vendor"] == vendor and fixed["artifact"] == artifact and file_digest == digest:
                return FileResponse(p, filename=p.name)

    raise HTTPException(status_code=404, detail="Not found")


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


def load_databases_from_toml(toml_path: Path):
    if not toml_path.exists():
        raise FileNotFoundError(f"TOML not found: {toml_path}")

    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    # TOML の仕様:
    # [databases.<name>]
    # path = "/path/to/db"
    db_entries = data.get("databases", {})

    managers = {}
    for key, entry in db_entries.items():
        p = Path(entry["path"])
        managers[key] = AppState(database_path=p)

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
    app.state.manager = next(iter(managers.values())) if managers else None

    # uvicorn 起動
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
