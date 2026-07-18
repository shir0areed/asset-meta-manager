function openLightBox(src) {
    const lb = document.getElementById("lightbox");
    const img = document.getElementById("lightbox-img");

    img.onload = () => {
        const vw = window.innerWidth * 0.9;
        const vh = window.innerHeight * 0.9;

        const naturalW = img.naturalWidth;
        const naturalH = img.naturalHeight;

        // 90% に達するための拡大率を計算
        const scaleW = vw / naturalW;
        const scaleH = vh / naturalH;

        // 幅・高さどちらかが 90% に達するまで拡大
        const scale = Math.min(scaleW, scaleH);

        img.style.transform = `scale(${scale})`;
    };

    img.src = src;
    lb.style.display = "flex";
}

document.getElementById("lightbox").addEventListener("click", () => {
    document.getElementById("lightbox").style.display = "none";
});
