// -----------------------------
// STEP8: フィルタ／ソート状態
// -----------------------------
let cachedData = null;
let filterValues = {};   // {colKey: "text" }
let sortColumn = null;   // "name", "cat_0", "ann_1" など
let sortAsc = true;

// -----------------------------
// データ取得
// -----------------------------
async function load() {
    const res = await fetch("/scan-result");
    cachedData = await res.json();

    const count = document.getElementById("count");
    count.textContent = `ファイル数: ${cachedData.files.length}`;

    initTableHeaders();

    renderRows();
}

function initTableHeaders() {
    const data = cachedData;
    const headerRow = document.getElementById("header-row");
    const filterRow = document.getElementById("filter-row");

    // ヘッダ生成
    let headerHtml = `
                                    <th class="sortable" data-col="name">名前</th>
                                    <th>サムネイル</th>
                                `;
    let filterHtml = `
                                    <td><input class="filter-input" data-col="name"></td>
                                    <td></td>
                                `;

    data.category_columns.forEach((c, i) => {
        headerHtml += `<th class="sortable" data-col="cat_${i}">${c}</th>`;
        filterHtml += `<td><input class="filter-input" data-col="cat_${i}"></td>`;
    });

    data.annotation_columns.forEach((a, i) => {
        headerHtml += `<th class="sortable" data-col="ann_${i}">${a.label}</th>`;
        filterHtml += `<td><input class="filter-input" data-col="ann_${i}"></td>`;
    });

    headerHtml += `<th>ファイル</th>`;
    filterHtml += `<td></td>`;

    headerRow.innerHTML = headerHtml;
    filterRow.innerHTML = filterHtml;

    // フィルタ入力イベント
    document.querySelectorAll(".filter-input").forEach(input => {
        const col = input.dataset.col;
        input.addEventListener("input", () => {
            filterValues[col] = input.value;
            renderRows();
        });
    });


    // -----------------------------
    // ソートイベント
    // -----------------------------
    document.querySelectorAll(".sortable").forEach(th => {
        th.addEventListener("click", () => {
            const col = th.dataset.col;
            if (sortColumn === col) {
                sortAsc = !sortAsc;
            } else {
                sortColumn = col;
                sortAsc = true;
            }
            renderRows();
        });
    });
}

function renderRows() {
    const data = cachedData;
    if (!data) return;

    const tbody = document.getElementById("file-table");

    // フィルタ欄の値を反映（値だけ、DOMは触らない）
    document.querySelectorAll(".filter-input").forEach(input => {
        const col = input.dataset.col;
        if (filterValues[col] !== undefined) {
            input.value = filterValues[col];
        }
    });

    // -----------------------------
    // フィルタ処理
    // -----------------------------
    let rows = data.files.filter(item => {
        // 名前
        const fvName = filterValues["name"];
        if (fvName && !item.name.toLowerCase().includes(fvName.toLowerCase())) {
            return false;
        }

        // カテゴリ
        for (let i = 0; i < data.category_columns.length; i++) {
            const key = `cat_${i}`;
            const fv = filterValues[key];
            if (fv && !item.categories[i].toLowerCase().includes(fv.toLowerCase())) {
                return false;
            }
        }

        // アノテーション
        for (let i = 0; i < data.annotation_columns.length; i++) {
            const key = `ann_${i}`;
            const fv = filterValues[key];
            if (fv && !item.annotations[i].toLowerCase().includes(fv.toLowerCase())) {
                return false;
            }
        }

        return true;
    });

    // -----------------------------
    // ソート処理
    // -----------------------------
    if (sortColumn !== null) {
        rows.sort((a, b) => {
            let va = "";
            let vb = "";

            if (sortColumn === "name") {
                va = a.name;
                vb = b.name;
            } else if (sortColumn.startsWith("cat_")) {
                const i = Number(sortColumn.split("_")[1]);
                va = a.categories[i] || "";
                vb = b.categories[i] || "";
            } else if (sortColumn.startsWith("ann_")) {
                const i = Number(sortColumn.split("_")[1]);
                va = a.annotations[i] || "";
                vb = b.annotations[i] || "";
            }

            const cmp = va.localeCompare(vb);
            return sortAsc ? cmp : -cmp;
        });
    }

    // 行生成
    tbody.innerHTML = "";
    rows.forEach(item => {
        const tr = document.createElement("tr");

        let html = "";

        // ★ 名前列
        if (editMode) {
            html += `<td>
                                            <input class="edit-cell"
                                                   data-original="${item.name}"
                                                   data-path="${item.path}"
                                                   data-column="__name__"
                                                   value="${item.name}">
                                        </td>`;
        } else {
            html += `<td>${item.name}</td>`;
        }

        // ★ サムネイル列
        if (editMode) {
            const thumb = item.thumbnail || "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIW2P4//8/AwAI/AL+Z4VHKwAAAABJRU5ErkJggg=="; // 透明1px
            html += `
                                            <td style="white-space:nowrap;">
                                                <img class="thumb-img"
                                                     data-path="${item.path}"
                                                     src="${thumb}"
                                                     style="width:64px;height:64px;object-fit:cover;cursor:pointer;vertical-align:middle;">
                                                <button class="thumb-delete-btn"
                                                        data-path="${item.path}"
                                                        style="margin-left:4px;">×</button>
                                            </td>`;
        } else {
            const thumb = item.thumbnail || "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIW2P4//8/AwAI/AL+Z4VHKwAAAABJRU5ErkJggg==";
            html += `<td>
                                            <img class="thumb-view"
                                                 src="${thumb}"
                                                 style="width:64px;height:64px;object-fit:cover;cursor:pointer;">
                                            </td>`;
        }

        // ★ カテゴリ列（編集不可）
        html += item.categories.map(v => `<td>${v}</td>`).join("");

        // ★ アノテーション列
        if (editMode) {
            html += item.annotations.map((v, i) => `
                                            <td>
                                                <input class="edit-cell"
                                                       data-original="${v}"
                                                       data-path="${item.path}"
                                                       data-column="${data.annotation_columns[i].id}"
                                                       value="${v}">
                                            </td>`).join("");
        } else {
            html += data.annotation_columns.map((col, i) => {
                const v = item.annotations[i] || "";

                if (col.type === "url" && v) {
                    return `
                        <td>
                            <a href="${v}" target="_blank" class="url-icon" title="${v}">
                                🌐
                            </a>
                        </td>`;
                }

                return `<td>${v}</td>`;
            }).join("");
        }

        // ★ ファイル列
        html += `<td><a href="/file?path=${encodeURIComponent(item.path)}" download>Download</a></td>`;

        tr.innerHTML = html;
        tbody.appendChild(tr);
    });

    if (editMode) {
        attachEditHandlers();
    }

    // 非編集モード時のサムネイル拡大
    if (!editMode) {
        document.querySelectorAll(".thumb-view").forEach(img => {
            img.addEventListener("click", () => {
                openLightBox(img.src);
            });
        });
    }
}

// =====================================================
// STEP6.5-A2: 値更新 UI のみ（保存 API はまだ呼ばない）
// =====================================================
function attachEditHandlers() {
    document.querySelectorAll(".edit-cell").forEach(input => {

        // Enter / ESC
        input.addEventListener("keydown", e => {
            if (e.key === "Enter") {
                saveValue(input.dataset.path, input.dataset.column, input.value);

                input.dataset.original = input.value;
                input.blur();
            }
            if (e.key === "Escape") {
                input.value = input.dataset.original;
                input.blur();
            }
        });

        // フォーカスアウト
        input.addEventListener("blur", e => {
            const newValue = input.value;
            if (newValue === input.dataset.original) return;

            const ok = confirm("変更を保存しますか？");
            if (ok) {
                saveValue(input.dataset.path, input.dataset.column, newValue);

                input.dataset.original = input.value;
            } else {
                input.value = input.dataset.original;
            }
        });
    });

    // ★ サムネイル削除ボタン
    document.querySelectorAll(".thumb-delete-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const path = btn.dataset.path;
            await fetch("/meta/delete-thumbnail", {
                method: "POST",
                body: new URLSearchParams({ path })
            });
            load();
        });
    });

    // ★ サムネイル編集
    document.querySelectorAll(".thumb-img").forEach(img => {

        // 左クリック → ファイル選択
        img.addEventListener("click", async () => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = "image/*";
            input.onchange = async () => {
                const file = input.files[0];
                if (!file) return;

                const reader = new FileReader();
                reader.onload = () => {
                    saveThumbnail(img.dataset.path, reader.result);
                };
                reader.readAsDataURL(file);
            };
            input.click();
        });

        // 右クリック → クリップボードから貼り付け
        img.addEventListener("contextmenu", async (e) => {
            e.preventDefault();
            try {
                const clipboardItems = await navigator.clipboard.read();
                for (const item of clipboardItems) {
                    for (const type of item.types) {
                        if (type.startsWith("image/")) {
                            const blob = await item.getType(type);
                            const reader = new FileReader();
                            reader.onload = () => {
                                saveThumbnail(img.dataset.path, reader.result);
                            };
                            reader.readAsDataURL(blob);
                            return;
                        }
                    }
                }
                alert("クリップボードに画像がありません");
            } catch {
                alert("クリップボードから読み取れませんでした");
            }
        });
    });
}

async function saveValue(path, column, value) {
    if (column === "__name__") {
        await fetch("/meta/update-name", {
            method: "POST",
            body: new URLSearchParams({ path, value })
        });
    } else {
        await fetch("/meta/update-annotation", {
            method: "POST",
            body: new URLSearchParams({ path, column_id: column, value })
        });
    }

    load();
}

async function saveThumbnail(path, base64) {
    await fetch("/meta/update-thumbnail", {
        method: "POST",
        body: new URLSearchParams({ path, value: base64 })
    });
    load();
}

load();
