
import { createFloatingWindow, showPopup } from "./popup.js";

/**
 * @import { store } from "./state.js";
 * @import { UserRecord } from "./api.js";
 * 
 * Shows the login panel if necessary.
 * @param {store} store - The store object.
 * @returns {Promise<UserRecord>} - The user record.
 */
export async function maybeShowLoginPanel(
    store, 
    forceShowup = false
){
    if (!forceShowup){
        try {
            const user = await store.conn.whoami();
            if (user.id !== 0){
                return user;
            }
        }
        catch (e) {
            console.error(e);
        }
    }

    const innerHTML = `
    <div id="login-container">
        <div class="input-group" style="min-width: 300px;">
            <label for="endpoint-input" class="login-lbl">Endpoint</label>
            <input type="text" id="endpoint-input" placeholder="http://localhost:8000" autocomplete="off">
        </div>
        <div class="input-group" style="min-width: 300px;">
            <label for="token-input" class="login-lbl">Token</label>
            <input type="text" id="token-input" placeholder="" autocomplete="off">
        </div>

        <button id="login-btn">Login</button>
    </div>
    `

    const [win, closeWin] = createFloatingWindow(innerHTML, {
        padding: '2rem',
    });

    const endpointInput = document.getElementById("endpoint-input");
    const tokenInput = document.getElementById("token-input");
    const loginBtn = document.getElementById("login-btn");

    endpointInput.value = store.endpoint;
    tokenInput.value = store.token;

    endpointInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter'){ loginBtn.click(); }
    });
    tokenInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter'){ loginBtn.click(); }
    });
    endpointInput.addEventListener('input', () => {
        store.endpoint = endpointInput.value;
    });
    tokenInput.addEventListener('input', () => {
        store.token = tokenInput.value;
    });

    loginBtn.focus();

    return new Promise((resolve, reject) => {
        loginBtn.addEventListener('click', async () => {
            try {
                const user = await store.conn.whoami();
                closeWin();
                resolve(user);
            }
            catch (e) {
                showPopup('Login failed: ' + e.message, {
                    level: 'error',
                });
            }
        });
    });
}