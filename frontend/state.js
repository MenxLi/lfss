
import Connector from './api.js';

function loadPersistedState(key, defaultValue) {
    const persistedValue = window.localStorage.getItem(key);
    return persistedValue ? persistedValue : defaultValue;
}

function setPersistedState(key, value) {
    window.localStorage.setItem(key, value);
}

export const store = {
    conn: new Connector(),

    init() {
        this.conn.config.token = this.token;
        this.conn.config.endpoint = this.endpoint;
    },

    get token() {
        return loadPersistedState('token', '');
    },
    set token(t) {
        setPersistedState('token', t);
        this.conn.config.token = t;
    },

    get endpoint() {
        return loadPersistedState('endpoint', 'http://localhost:8000');
    },
    set endpoint(url) {
        setPersistedState('endpoint', url);
        this.conn.config.endpoint = url;
    }, 

    get dirpath() {
        return loadPersistedState('dirpath', '/');
    },
    set dirpath(pth) {
        setPersistedState('dirpath', pth);
    },

    get orderby () {
        return loadPersistedState('orderby', 'none');
    }, 
    set orderby (sb) {
        setPersistedState('orderby', sb);
    }, 

    get sortorder () {
        return loadPersistedState('sortorder', 'asc');
    },
    set sortorder (so) {
        setPersistedState('sortorder', so);
    },

    get pagenum () {
        return parseInt(loadPersistedState('pagenum', '1'));
    },
    set pagenum (pn) {
        setPersistedState('pagenum', pn.toString());
    },

    get pagelim () {
        return parseInt(loadPersistedState('pagelim', '100'));
    },
    set pagelim (ps) {
        setPersistedState('pagelim', ps.toString());
    },

};
