import threading
import webbrowser


HOST = "127.0.0.1"
PORT = 8000


def open_browser():
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "The web UI requires FastAPI and Uvicorn. "
            "Install them with: pip install 'ok-script[web]'"
        ) from exc

    from config import config
    from ok.ui.web import create_web_app

    web_config = dict(config)
    web_config["debug"] = True
    web_config["use_gui"] = False

    browser_timer = threading.Timer(1.0, open_browser)
    browser_timer.daemon = True
    browser_timer.start()

    uvicorn.run(create_web_app(web_config), host=HOST, port=PORT)
