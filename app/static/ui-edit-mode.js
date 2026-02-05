let editMode = false;

function updateEditModeUI() {
    const display = editMode ? "block" : "none";

    // カテゴリ列編集
    document.getElementById("category-add-form").style.display = display;
    document.getElementById("category-columns-list").style.display = display;

    // アノテーション列編集
    const annForm = document.getElementById("annotation-add-form");
    const annList = document.getElementById("annotation-columns-list");

    if (annForm) annForm.style.display = display;
    if (annList) annList.style.display = display;
}

document.getElementById("edit-toggle").onclick = () => {
    editMode = !editMode;
    document.getElementById("edit-toggle").textContent =
        editMode ? "編集モード: ON" : "編集モード: OFF";

    updateEditModeUI(); // ★ 列編集 UI の表示切り替え
    load(); // 再描画
};

updateEditModeUI();
