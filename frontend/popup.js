

export function createFloatingWindow(innerHTML = '',  {
    onClose = () => {},
    width = "auto",
    height = "auto",
    padding = "20px",
} = {}){
    const blocker = document.createElement("div");
    blocker.classList.add("floating-window", "blocker");

    const floatingWindow = document.createElement("div");
    floatingWindow.classList.add("floating-window", "window");
    floatingWindow.id = "floatingWindow";
    floatingWindow.innerHTML = innerHTML;
    floatingWindow.style.width = width;
    floatingWindow.style.height = height;
    floatingWindow.style.padding = padding;

    const container = document.createElement("div");
    container.classList.add("floating-window", "container");

    document.body.appendChild(blocker);
    document.body.appendChild(floatingWindow);

    function closeWindow(){
        onClose();
        if (blocker.parentNode) document.body.removeChild(blocker);
        if (floatingWindow.parentNode) document.body.removeChild(floatingWindow);
        window.removeEventListener("keydown", excapeEvListener);
    }
    blocker.onclick = closeWindow;

    const excapeEvListener = (event) => {
        event.stopPropagation();
        if (event.key === "Escape") closeWindow();
    }
    window.addEventListener("keydown", excapeEvListener);

    return [floatingWindow, closeWindow];
}

/* select can be "last-filename" */
export function showFloatingWindowLineInput(onSubmit = (v) => {}, {
    text = "",
    placeholder = "Enter text",
    value = "",
    select = ""
} = {}){
    const [floatingWindow, closeWindow] = createFloatingWindow(`
        <div style="margin-bottom: 0.5rem;width: 100%;text-align: left;">${text}</div>
        <div style="display: flex; flex-direction: row; gap: 0.25rem;">
            <input type="text" placeholder="${placeholder}" id="floatingWindowInput" value="${value}" style="min-width: 300px;"/>
            <button id="floatingWindowSubmit">OK</button>
        </div>
    `);

    /** @type {HTMLInputElement} */
    const input = document.getElementById("floatingWindowInput");
    const submit = document.getElementById("floatingWindowSubmit");

    input.focus();
    input.addEventListener("keydown", event => {
        if(event.key === "Enter" && input.value && event.isComposing === false){
            submit.click();
        }
    });

    submit.onclick = () => {
        onSubmit(input.value);
        closeWindow();
    };

    if (select === "last-filename") {
        const inputVal = input.value;
        let lastSlash = inputVal.lastIndexOf("/");
        if (lastSlash === -1) {
            lastSlash = 0;
        }
        const fname = inputVal.slice(lastSlash + 1);
        let lastDot = fname.lastIndexOf(".");
        if (lastDot === -1) {
            lastDot = fname.length;
        }
        input.setSelectionRange(lastSlash + 1, lastSlash + lastDot + 1);
    }

    return [floatingWindow, closeWindow];
}