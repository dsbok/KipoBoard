import streamlit as st
import requests
import urllib.parse
import json
import re
from PIL import Image
import io

st.set_page_config(
    page_title="KipoBoard", layout="wide", initial_sidebar_state="collapsed"
)

st.iframe(
    """
<script>
    const parentDoc = window.parent.document;

    if (!parentDoc.getElementById('custom-lightbox')) {
        const style = parentDoc.createElement('style');
        style.innerHTML = `
            #custom-lightbox {
                display: none;
                position: fixed;
                z-index: 999999;
                left: 0;
                top: 0;
                width: 100vw;
                height: 100vh;
                background-color: rgba(10, 10, 10, 0.95);
                backdrop-filter: blur(10px);
                align-items: center;
                justify-content: center;
                flex-direction: column;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            #custom-lightbox.active {
                display: flex;
                opacity: 1;
            }
            #lightbox-img {
                max-width: 90vw;
                max-height: 80vh;
                border-radius: 8px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.8);
                object-fit: contain;
            }
            .lightbox-controls {
                margin-top: 25px;
                display: flex;
                gap: 15px;
            }
            .lightbox-btn {
                background: #1a1a1a;
                color: #fff;
                border: 1px solid #333;
                padding: 10px 24px;
                border-radius: 8px;
                cursor: pointer;
                text-decoration: none;
                font-family: system-ui, sans-serif;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s ease;
                display: inline-flex;
                align-items: center;
                justify-content: center;
            }
            .lightbox-btn:hover {
                background: #fff;
                color: #000;
                border-color: #fff;
                transform: translateY(-2px);
            }
            button[title="View fullscreen"] {
                display: none !important;
            }
        `;
        parentDoc.head.appendChild(style);

        const lightbox = parentDoc.createElement('div');
        lightbox.id = 'custom-lightbox';
        
        lightbox.onclick = function(e) {
            if(e.target.id === 'custom-lightbox') {
                lightbox.classList.remove('active');
            }
        };
        
        lightbox.innerHTML = `
            <img id="lightbox-img" src="">
            <div class="lightbox-controls">
                <a id="lightbox-download" class="lightbox-btn" href="" download="kipoboard-image.jpg">
                    <svg style="width:16px;height:16px;margin-right:8px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Download Image
                </a>
                <button class="lightbox-btn" id="lightbox-close">Close</button>
            </div>
        `;
        parentDoc.body.appendChild(lightbox);

        parentDoc.getElementById('lightbox-close').onclick = function() {
            lightbox.classList.remove('active');
        };

        const observer = new MutationObserver(() => {
            const images = parentDoc.querySelectorAll('div[data-testid="stImage"] img:not(.lightbox-bound)');
            images.forEach(img => {
                img.classList.add('lightbox-bound');
                img.style.cursor = 'zoom-in';
                
                img.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const lb = parentDoc.getElementById('custom-lightbox');
                    const lbImg = parentDoc.getElementById('lightbox-img');
                    const lbDl = parentDoc.getElementById('lightbox-download');
                    
                    lbImg.src = img.src;
                    lbDl.href = img.src; 
                    lb.classList.add('active');
                }, true);
            });
        });
        observer.observe(parentDoc.body, { childList: true, subtree: true });
    }
</script>
""",
    height=1,
    width="content",
)

st.markdown(
    """
    <style>
        iframe {
            position: absolute;
            width: 0 !important;
            height: 0 !important;
            border: none;
            visibility: hidden;
        }
        html, body, [data-testid="stAppViewContainer"] { background-color: #0a0a0a !important; }
        
        div[data-testid="stTextInput"] input {
            background-color: #111111 !important; border: 1px solid #222222 !important;
            color: #ffffff !important; border-radius: 8px !important; padding: 12px 16px !important; transition: all 0.3s ease;
        }
        div[data-testid="stTextInput"] input:focus { border-color: #ffffff !important; }

        button[data-testid="baseButton-secondary"] {
            background-color: #111111 !important; border: 1px solid #222222 !important;
            color: #ffffff !important; border-radius: 8px !important; padding: 6px 18px !important; transition: all 0.2s ease !important;
        }
        button[data-testid="baseButton-secondary"]:hover {
            background-color: #ffffff !important; color: #000000 !important; border-color: #ffffff !important;
        }

        div[data-testid="stColumn"] { animation: fadeIn 0.6s ease-in-out; }
        div[data-testid="stImage"] img {
            border-radius: 8px !important;
            transition: transform 0.3s cubic-bezier(0.25, 1, 0.5, 1), filter 0.3s ease !important;
        }
        div[data-testid="stImage"] img:hover { transform: scale(1.02); filter: brightness(0.9); }

        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""",
    unsafe_allow_html=True,
)

for key, default in [
    ("page", 1),
    ("bookmarks", {1: ""}),
    ("csrftokens", {1: ""}),
    ("search_query", ""),
    ("images", []),
    ("has_more", False),
    ("scroll_trigger", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

csrf_regex = re.compile(r"csrftoken=([^;]+)")
api_session = requests.Session()


@st.cache_data(show_spinner=False, ttl=3600)
def proxy_image(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status_code == 200 and res.headers.get("Content-Type", "").startswith(
            "image/"
        ):
            try:
                img = Image.open(io.BytesIO(res.content))
                img.verify()
                return res.content
            except Exception:
                return None
    except Exception:
        pass
    return None


def search_pinterest(q, b="", c=""):
    opts = {"query": q, "scope": "pins"}
    if b:
        opts["bookmarks"] = [b]

    payload = json.dumps({"options": opts, "context": {}})
    target_url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=/search/pins/?q={urllib.parse.quote(q)}&data={urllib.parse.quote(payload)}"

    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Pinterest-AppState": "active",
        "X-Pinterest-PWS-Handler": "www/search/[scope].js",
        "User-Agent": "Mozilla/5.0",
    }

    if c:
        headers["X-CSRFToken"] = c
        headers["Cookie"] = f"csrftoken={c}"

    try:
        res = api_session.get(target_url, headers=headers, timeout=15)
        if "set-cookie" in res.headers:
            m = csrf_regex.search(res.headers["set-cookie"])
            if m:
                c = m.group(1)
        data = res.json()
    except Exception:
        return {"images": [], "bookmark": "", "csrftoken": c}

    imgs = [
        r.get("images", {}).get("orig", {}).get("url", "")
        for r in data.get("resource_response", {}).get("data", {}).get("results", [])
    ]
    imgs = [img for img in imgs if img]

    nb = data.get("resource_response", {}).get("bookmark", "")
    if not nb:
        bookmarks = data.get("resource", {}).get("options", {}).get("bookmarks", [])
        if bookmarks:
            nb = bookmarks[0]

    return {"images": imgs, "bookmark": nb, "csrftoken": c}


def perform_search(reset=False):
    if reset:
        st.session_state.page = 1
        st.session_state.bookmarks = {1: ""}
        st.session_state.csrftokens = {1: ""}

    current_page = st.session_state.page
    q = st.session_state.search_query

    b = st.session_state.bookmarks.get(current_page, "")
    c = st.session_state.csrftokens.get(current_page, "")

    if not q:
        st.session_state.images = []
        return

    res = search_pinterest(q, b, c)
    st.session_state.images = res["images"][:15]

    next_page = current_page + 1
    if res["bookmark"]:
        st.session_state.bookmarks[next_page] = res["bookmark"]
        st.session_state.csrftokens[next_page] = res["csrftoken"]
        st.session_state.has_more = True
    else:
        st.session_state.has_more = False


def do_search():
    st.session_state.search_query = st.session_state.q_input
    st.session_state.scroll_trigger = True
    perform_search(reset=True)


def go_next():
    st.session_state.page += 1
    st.session_state.scroll_trigger = True
    perform_search(reset=False)


def go_prev():
    st.session_state.page -= 1
    st.session_state.scroll_trigger = True
    perform_search(reset=False)


if st.session_state.scroll_trigger:
    st.iframe(
        "<script>window.parent.scrollTo({top: 0, behavior: 'smooth'});</script>",
        height=1,
        width="content",
    )
    st.session_state.scroll_trigger = False

st.markdown(
    "<h1 style='text-align: center; font-weight: 300; letter-spacing: -1px; margin-bottom: 0px;'>KipoBoard</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; margin-bottom: 30px;'><a href='https://github.com/dsbok/KipoBoard' target='_blank' style='color: #666; text-decoration: none; border-bottom: 1px dotted #666; padding-bottom: 2px;'>Source</a></p>",
    unsafe_allow_html=True,
)

col_input, col_btn = st.columns([5, 1])
with col_input:
    st.text_input(
        "Search images...",
        key="q_input",
        label_visibility="collapsed",
        placeholder="What are you looking for?",
        on_change=do_search,
    )
with col_btn:
    st.button("Search", width="stretch", on_click=do_search)

st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

if st.session_state.images:
    cols = st.columns(4, gap="medium")
    for idx, img_url in enumerate(st.session_state.images):
        col_idx = idx % 4
        with cols[col_idx]:
            image_bytes = proxy_image(img_url)
            if image_bytes:
                try:
                    st.image(image_bytes, width="stretch")
                except Exception:
                    pass
elif st.session_state.search_query:
    st.markdown(
        "<p style='text-align: center; color: #666;'>No alternative results found.</p>",
        unsafe_allow_html=True,
    )

if st.session_state.search_query and (
    st.session_state.page > 1 or st.session_state.has_more
):
    st.markdown("<div style='margin-top: 40px;'></div>", unsafe_allow_html=True)
    col_prev, col_page, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.session_state.page > 1:
            st.button("← Previous", width="stretch", on_click=go_prev)

    with col_page:
        st.markdown(
            f"<p style='text-align: center; color: #888; font-size: 14px; margin-top: 8px;'>Page {st.session_state.page}</p>",
            unsafe_allow_html=True,
        )

    with col_next:
        if st.session_state.has_more:
            st.button("Next →", width="stretch", on_click=go_next)
