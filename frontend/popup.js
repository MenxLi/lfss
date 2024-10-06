

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

/* select can be "last-filename" or "last-pathname" */
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
        // select the last filename, e.g. "file" in "/path/to/file.txt"
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
    else if (select === "last-pathname") {
        // select the last pathname, e.g. "to" in "/path/to/<filename>"
        const lastSlash = input.value.lastIndexOf("/");
        const secondLastSlash = input.value.lastIndexOf("/", input.value.lastIndexOf("/") - 1);
        if (secondLastSlash !== -1) {
            input.setSelectionRange(secondLastSlash + 1, lastSlash);
        }
        else {
            input.setSelectionRange(0, lastSlash);
        }
    }

    return [floatingWindow, closeWindow];
}

const shownPopups = [];
export function showPopup(content = '',  {
    level = "info",
    width = "auto",
    timeout = 3000, 
    showTime = true
} = {}){
    const popup = document.createElement("div");
    popup.classList.add("popup-window");
    popup.innerHTML = showTime? `<span>[${new Date().toLocaleTimeString()}]</span> ${content}` : content;
    popup.style.width = width;
    const popupHeight = '1rem';
    popup.style.height = popupHeight;
    popup.style.maxHeight = popupHeight;
    popup.style.minHeight = popupHeight;
    const paddingHeight = '1rem';
    popup.style.padding = paddingHeight;

    // traverse shownPopups and update the top position of each popup
    if (shownPopups.length > 0) {
        for (let i = 0; i < shownPopups.length; i++) {
            shownPopups[i].style.top = `${i * (parseInt(popupHeight) + 2*parseInt(paddingHeight))*1.2 + 0.5}rem`;
        }
    }
    popup.style.top = `${shownPopups.length * (parseInt(popupHeight) + 2*parseInt(paddingHeight))*1.2 + 0.5}rem`;

    if (level === "error") popup.style.backgroundColor = "darkred";
    if (level === "warning") popup.style.backgroundColor = "darkorange";
    if (level === "info") popup.style.backgroundColor = "darkblue";
    if (level === "success") popup.style.backgroundColor = "darkgreen";
    document.body.appendChild(popup);
    shownPopups.push(popup);
    window.setTimeout(() => {
        if (popup.parentNode) document.body.removeChild(popup);
        shownPopups.splice(shownPopups.indexOf(popup), 1);
        for (let i = 0; i < shownPopups.length; i++) {
            shownPopups[i].style.top = `${i * (parseInt(popupHeight) + 2*parseInt(paddingHeight))*1.2 + 0.5}rem`;
        }
    }, timeout);
}