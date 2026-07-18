async function loadAnnotationColumns() {
    const res = await fetch("/annotation_columns");
    const data = await res.json();

    const ul = document.getElementById("annotation-columns-list");
    ul.innerHTML = "";

    data.annotation_columns.forEach(col => {
        const li = document.createElement("li");
        li.textContent = `${col.label} (${col.id}: ${col.type}) `;

        const btn = document.createElement("button");
        btn.textContent = "削除";
        btn.onclick = async () => {
            await fetch("/annotation_columns/remove", {
                method: "POST",
                body: new URLSearchParams({ column_id: col.id })
            });
            loadAnnotationColumns();
            load(); // ファイル一覧も更新
        };

        li.appendChild(btn);
        ul.appendChild(li);
    });
}

document.getElementById("annotation-add-form").onsubmit = async (e) => {
    e.preventDefault();

    const label = document.getElementById("annotation-label").value;
    const column_id = document.getElementById("annotation-id").value;
    const type = document.getElementById("annotation-type").value;

    await fetch("/annotation_columns/add", {
        method: "POST",
        body: new URLSearchParams({ label, column_id, type })
    });

    document.getElementById("annotation-label").value = "";
    document.getElementById("annotation-id").value = "";

    loadAnnotationColumns();
    load(); // ファイル一覧も更新
};

loadAnnotationColumns();
