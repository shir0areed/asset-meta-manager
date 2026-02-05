import argparse
from fastapi import FastAPI, Query, Form
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from app.core.state import AppState


app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
async def startup_event():
    state = app.state.manager
    print("Scanned files:")
    for f in state.files:
        print(" -", f)

@app.get("/")
def root():
    return RedirectResponse(url="/ui")

@app.get("/instance-info")
def instance_info():
    """
    STEP1 の動作確認用エンドポイント。
    UI 実装前でもブラウザで確認できる。
    """
    state = app.state.manager
    return {
        "identity": str(state.identity_path),
        "instance_root": str(state.instance_root),
        "sibling_folders": [str(p) for p in state.sibling_folders],
    }


@app.get("/scan-result")
def scan_result():
    """
    STEP2 の動作確認用エンドポイント。
    スキャンされたファイル一覧を返す。
    """
    state = app.state.manager
    root = state.instance_root  # identity の親フォルダ
    category_columns = state.load_category_columns()
    annotation_columns = state.load_annotation_columns()

    result = []

    for p in state.files:
        # identity からの相対パス（Path）
        rel = p.relative_to(root)
        
        # UI 用に POSIX 文字列へ
        rel_posix = rel.as_posix()

        # ★ meta.json をロード
        meta = state.load_meta(p)

        # ★ 名前（meta に name があれば優先）
        name = meta.get("name", p.stem)

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

        result.append({
            "path": rel_posix,
            "name": name,
            "thumbnail": thumbnail,
            "categories": categories,
            "annotations": annotations,
        })

    return {
        "category_columns": category_columns,
        "annotation_columns": annotation_columns,
        "files": result,
    }


@app.get("/ui")
def ui():
    html_path = Path(__file__).parent / "static" / "ui.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/file")
def download_file(path: str = Query(..., description="Relative POSIX path from identity root")):
    """
    STEP4: ファイルダウンロード用エンドポイント。
    path は絶対パスで渡す。
    """
    state = app.state.manager
    root = state.instance_root

    # 相対 POSIX パスを Path に戻す
    abs_path = (root / Path(path)).resolve()

    return FileResponse(abs_path, filename=abs_path.name)

@app.get("/category_columns")
def get_category_columns():
    state = app.state.manager
    return {"category_columns": state.load_category_columns()}


@app.post("/category_columns/add")
def add_category_columns(name: str = Form(...)):
    state = app.state.manager
    state.add_category_columns(name)
    return {"ok": True}


@app.post("/category_columns/remove")
def remove_category_columns(name: str = Form(...)):
    state = app.state.manager
    state.remove_category_columns(name)
    return {"ok": True}


@app.get("/annotation_columns")
def get_annotation_columns():
    state = app.state.manager
    return {"annotation_columns": state.load_annotation_columns()}


@app.post("/annotation_columns/add")
def add_annotation_column(column_id: str = Form(...), label: str = Form(...)):
    state = app.state.manager
    ok = state.add_annotation_column(column_id, label)
    return {"ok": ok}


@app.post("/annotation_columns/remove")
def remove_annotation_column(column_id: str = Form(...)):
    state = app.state.manager
    state.remove_annotation_column(column_id)
    return {"ok": True}


@app.post("/meta/update-name")
def update_name(path: str = Form(...), value: str = Form(...)):
    app.state.manager.update_name(path, value)
    return {"ok": True}


@app.post("/meta/update-annotation")
def update_annotation(path: str = Form(...), column_id: str = Form(...), value: str = Form(...)):
    app.state.manager.update_annotation(path, column_id, value)
    return {"ok": True}


@app.post("/meta/update-thumbnail")
def update_thumbnail(path: str = Form(...), value: str = Form(...)):
    app.state.manager.update_thumbnail(path, value)
    return {"ok": True}


@app.post("/meta/delete-thumbnail")
def delete_thumbnail(path: str = Form(...)):
    app.state.manager.update_thumbnail(path, None)
    return {"ok": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", required=True, help="Path to identity file")
    args = parser.parse_args()

    # identity をロード
    app.state.manager = AppState(identity_path=args.identity)

    # uvicorn 起動
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
