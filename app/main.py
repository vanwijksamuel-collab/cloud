from wsgiref.simple_server import make_server

from . import create_app


app = create_app()


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    with make_server(host, port, app) as server:
        print(f"ProSync running on http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    run()
