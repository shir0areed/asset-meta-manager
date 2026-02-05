async function loadCategoryColumns() {
    const res = await fetch("/category_columns");
    const data = await res.json();

    const ul = document.getElementById("category-columns-list");
    ul.innerHTML = "";

    data.category_columns.forEach(name => {
        const li = document.createElement("li");
        li.textContent = name + " ";
        const btn = document.createElement("button");
        btn.textContent = "削除";
        btn.onclick = async () => {
            await fetch("/category_columns/remove", {
                method: "POST",
                body: new URLSearchParams({ name })
            });
            loadCategoryColumns();
            load(); // ファイル一覧も更新
        };
        li.appendChild(btn);
        ul.appendChild(li);
    });
}

document.getElementById("category-add-form").onsubmit = async (e) => {
    e.preventDefault();
    const name = document.getElementById("category-columns-name").value;
    await fetch("/category_columns/add", {
        method: "POST",
        body: new URLSearchParams({ name })
    });
    document.getElementById("category-columns-name").value = "";
    loadCategoryColumns();
    load(); // ファイル一覧も更新
};

loadCategoryColumns();
