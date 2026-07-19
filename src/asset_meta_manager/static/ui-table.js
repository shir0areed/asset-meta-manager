// -----------------------------
// STEP8: フィルタ／ソート状態
// -----------------------------
let cachedData = null;
let filterValues = {};   // {colKey: "text" }
let sortColumn = null;   // "name", "cat_0", "ann_1" など
let sortAsc = true;

let currentPage = 1;
const pageSize = 10;

// -----------------------------
// データ取得
// -----------------------------
const loadingOverlay = document.getElementById("loading-overlay");

function bindHeaderRowHandlers() {
    const headerRow = document.getElementById("header-row");
    const filterRow = document.getElementById("filter-row");

    if (!headerRow || !filterRow) return;

    headerRow.addEventListener("click", event => {
        const th = event.target.closest(".sortable");
        if (!th) return;

        const col = th.dataset.col;
        if (sortColumn === col) {
            sortAsc = !sortAsc;
        } else {
            sortColumn = col;
            sortAsc = true;
        }

        document.querySelectorAll(".sort-arrow").forEach(span => {
            span.textContent = "";
        });

        const arrow = sortAsc ? "▲" : "▼";
        th.querySelector(".sort-arrow").textContent = arrow;

        renderRows();
    });

    filterRow.addEventListener("input", event => {
        const input = event.target;
        if (!input.matches(".filter-input")) return;

        const col = input.dataset.col;
        filterValues[col] = input.value;
        renderRows();
    });
}

function bindPaginationHandlers() {
    const pag = document.getElementById("pagination");
    if (!pag) return;

    pag.addEventListener("click", event => {
        const button = event.target.closest("button");
        if (!button) return;

        if (button.id === "page-prev") {
            currentPage--;
            renderRows();
        }

        if (button.id === "page-next") {
            currentPage++;
            renderRows();
        }
    });
}

function bindTableRowHandlers() {
    const tbody = document.getElementById("file-table");
    if (!tbody) return;

    tbody.addEventListener("keydown", event => {
        const input = event.target;
        if (!input.matches(".edit-cell")) return;

        if (event.key === "Enter") {
            saveValue(input.dataset.path, input.dataset.column, input.value);
            input.dataset.original = input.value;
            input.blur();
        }

        if (event.key === "Escape") {
            input.value = input.dataset.original;
            input.blur();
        }
    });

    tbody.addEventListener("focusout", event => {
        const input = event.target;
        if (!input.matches(".edit-cell")) return;

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

    tbody.addEventListener("click", async event => {
        const deleteBtn = event.target.closest(".thumb-delete-btn");
        if (deleteBtn) {
            const path = deleteBtn.dataset.path;
            await fetch("/meta/delete-thumbnail", {
                method: "POST",
                body: new URLSearchParams({ path })
            });
            load();
            return;
        }

        const thumbImg = event.target.closest(".thumb-img");
        if (thumbImg) {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = "image/*";
            input.onchange = async () => {
                const file = input.files[0];
                if (!file) return;

                const reader = new FileReader();
                reader.onload = () => {
                    saveThumbnail(thumbImg.dataset.path, reader.result);
                };
                reader.readAsDataURL(file);
            };
            input.click();
            return;
        }

        const thumbView = event.target.closest(".thumb-view");
        if (thumbView && !editMode) {
            openLightBox(thumbView.src);
        }
    });

    tbody.addEventListener("contextmenu", async event => {
        const thumbImg = event.target.closest(".thumb-img");
        if (!thumbImg) return;

        event.preventDefault();
        try {
            const clipboardItems = await navigator.clipboard.read();
            for (const item of clipboardItems) {
                for (const type of item.types) {
                    if (type.startsWith("image/")) {
                        const blob = await item.getType(type);
                        const reader = new FileReader();
                        reader.onload = () => {
                            saveThumbnail(thumbImg.dataset.path, reader.result);
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
}

async function load() {
    loadingOverlay.style.display = "flex";
    const res = await fetch("/scan-result");
    cachedData = await res.json();

    const count = document.getElementById("count");
    count.textContent = cachedData.files.length;

    // ★ identity 表示を更新
    updateIdentityDisplay();
    
    initTableHeaders();

    renderRows();
    loadingOverlay.style.display = "none";
}

function initTableHeaders() {
    const data = cachedData;
    const headerRow = document.getElementById("header-row");
    const filterRow = document.getElementById("filter-row");

    // ヘッダ生成
    let headerHtml = `
        <th class="sortable" data-col="name">名前 <span class="sort-arrow"></span></th>
        <th>サムネイル</th>
    `;
    let filterHtml = `
        <td><input class="filter-input" data-col="name"></td>
        <td></td>
    `;

    data.category_columns.forEach((c, i) => {
        headerHtml += `<th class="sortable" data-col="cat_${i}">${c} <span class="sort-arrow"></span></th>`;
        filterHtml += `<td><input class="filter-input" data-col="cat_${i}"></td>`;
    });

    data.annotation_columns.forEach((a, i) => {
        headerHtml += `<th class="sortable" data-col="ann_${i}">${a.label} <span class="sort-arrow"></span></th>`;

        if (a.type === "url") {
            // ★ URL 型は検索ボックスなし
            filterHtml += `<td></td>`;
        } else {
            filterHtml += `<td><input class="filter-input" data-col="ann_${i}"></td>`;
        }
    });

    headerHtml += `<th>ファイル</th>`;
    filterHtml += `<td></td>`;

    headerRow.innerHTML = headerHtml;
    filterRow.innerHTML = filterHtml;
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

    // -----------------------------
    // ページネーション処理
    // -----------------------------
    const totalPages = Math.ceil(rows.length / pageSize);

    // 現在ページが範囲外なら補正
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    // ページに応じて rows を切り出す
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    const pageRows = rows.slice(start, end);

    // 行生成
    tbody.innerHTML = "";
    pageRows.forEach(item => {
        const tr = document.createElement("tr");

        let html = "";

        // ★ 名前列
        if (editMode) {
            html += `
            <td>
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
            html += `
            <td>
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

    // -----------------------------
    // ページネーション UI
    // -----------------------------
    const pag = document.getElementById("pagination");
    pag.innerHTML = `
        <button ${currentPage <= 1 ? "disabled" : ""} id="page-prev">前へ</button>
        <span> ${currentPage} / ${totalPages} </span>
        <button ${currentPage >= totalPages ? "disabled" : ""} id="page-next">次へ</button>
    `;
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

function initTableInteractions() {
    bindHeaderRowHandlers();
    bindPaginationHandlers();
    bindTableRowHandlers();
}

const sidebar = document.getElementById("sidebar");
const spacer = document.createElement("div");
spacer.style.height = sidebar.offsetHeight + "px";
document.body.appendChild(spacer);

initTableInteractions();
load();
