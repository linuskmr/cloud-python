import argparse
import os
from pathlib import Path
from typing import Optional
import csv

from markdown import markdown
import uvicorn as uvicorn
from fastapi import FastAPI, Request, Response, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials


api = FastAPI(title="Cloud API")
auth = HTTPBasic()

data_path = Path("data/")

# HTML templates
templates = Jinja2Templates(directory="templates")


@api.get("/{relative_path:path}")
async def hallo(
    request: Request,
    relative_path: Path,
    # credentials: HTTPBasicCredentials = Depends(auth),
    download: Optional[str] = None,
):
    # TODO: Optional query parameter, with which the user can select the preview (md, txt, ...)

    title = "Dateien" if str(relative_path) == '.' else relative_path

    download = download is not None
    absolute_path = data_path / relative_path  # TODO: Prevent path traversal attacks

    # Split path into parts for breadcrumb navigation
    path_list = [{"name": "Dateien", "path": "/"}]
    for part in relative_path.parts:
        path_list.append(
            {"name": part, "path": os.path.join(path_list[-1]["path"], part)}
        )

    if not absolute_path.exists():
        return "404 - Not Found"

    if absolute_path.is_dir():
        files = os.listdir(absolute_path)
        files = list(
            map(lambda path: {"path": path, "size": (absolute_path / path).stat().st_size}, files)
        )

        return templates.TemplateResponse(
            "directory.html",
            {
                "request": request,
                "files": files,
                "empty_directory": len(files) == 0,
                "title": title,
                "path_list": path_list,
            },
        )

    # Path is a file

    if download:
        return Response(content=absolute_path.read_bytes())

    if absolute_path.suffix in [".txt", ".css", ".html", ".js", ".rs", ".py"]:
        # Show text file
        return templates.TemplateResponse(
            "text_file.html",
            {
                "request": request,
                "title": title,
                "path_list": path_list,
                "content": absolute_path.read_text(),
            },
        )
    elif absolute_path.suffix == ".md":
        # Show markdown file preview
        return templates.TemplateResponse(
            "markdown_file.html",
            {
                "request": request,
                "title": title,
                "path_list": path_list,
                "content": markdown(
                    absolute_path.read_text(), extensions=["fenced_code"]
                ),
            },
        )
    elif absolute_path.suffix == ".csv":
        # Show csv file preview
        csv_text = absolute_path.read_text()
        csv_reader = csv.reader(csv_text.split("\n"))
        table = [row for row in csv_reader]
        return templates.TemplateResponse(
            "csv_file.html",
            {
                "request": request,
                "title": title,
                "path_list": path_list,
                "table": table,
            },
        )
    else:
        # Byte-like data, e.g. jpg, png, ...
        return Response(content=absolute_path.read_bytes())


def main():
    args = parse_args()
    print(args)
    if args.command == "dev":
        start_dev_server(args.port)
    elif args.command == "production":
        start_production_server(args.port)
    else:
        raise ValueError(
            f"Command {args.command} unknown. Use '--help' to see available subcommands"
        )


def parse_args() -> argparse.Namespace:
    """Parses command line arguments on application startup."""

    parser = argparse.ArgumentParser(
        description="Cloud API",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,  # show default values
    )
    # Generic arguments that apply to all subcommands
    parser.add_argument(
        "--port", type=int, default=8192, help="Port on which the API should run"
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    parser_dev = subparsers.add_parser(
        "dev", help="Start development server with auto-reloading on file-save"
    )
    parser_production = subparsers.add_parser(
        "production", help="Start production server with maximum performance"
    )
    return parser.parse_args()


def start_dev_server(port: int):
    """Starts a development server with auto-reloading on port."""

    # Host="0.0.0.0" makes the application accessible from other IPs. Necessary when running inside docker
    uvicorn.run("main:api", reload=True, port=port, host="0.0.0.0")


def start_production_server(port: int):
    """Starts a production, i.e. performance-optimized server on port."""

    # Host="0.0.0.0" makes the application accessible from other IPs. Necessary when running inside docker
    uvicorn.run("main:api", port=port, host="0.0.0.0")


if __name__ == "__main__":
    main()
