import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

import uvicorn as uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.security import HTTPBasic
from fastapi.templating import Jinja2Templates
from markdown import markdown

api = FastAPI(title="Cloud")
auth = HTTPBasic()

DATA_PATH = Path("data/")
ROOT_DIR_NAME = "Files"

# HTML templates
templates = Jinja2Templates(directory="templates")


@dataclass
class Breadcrumb:
    name: str
    link: str


def generate_breadcrumbs(http_path: Path) -> List[Breadcrumb]:
    breadcrumbs = [
        Breadcrumb(name=ROOT_DIR_NAME, link="/")
    ]
    parts = http_path.parts
    for i, part_name in enumerate(parts):
        part_path = Path(part_name)

        amount_of_subdirs = len(parts) - i - 1
        breadcrumbs.append(Breadcrumb(
            name=part_name,
            link='../' * amount_of_subdirs,
        ))
    return breadcrumbs


@api.get("/{http_path:path}")
async def serve(
        request: Request,
        http_path: Path,
        # credentials: HTTPBasicCredentials = Depends(auth),
        download: Optional[str] = None,
):
    # TODO: Optional query parameter, with lets the user choose the preview (md, txt, csv)

    # TODO: Prevent path traversal attacks

    # Set page title
    title = ROOT_DIR_NAME if str(http_path) == '.' else http_path

    download = download is not None
    fs_path = DATA_PATH / http_path

    if not fs_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    breadcrumbs = generate_breadcrumbs(http_path)

    if fs_path.is_dir():
        return await handle_dir(
            fs_path=fs_path,
            breadcrumbs=breadcrumbs,
            title=title,
            request=request,
        )
    else:
        return await handle_file(
            breadcrumbs=breadcrumbs,
            download=download,
            fs_path=fs_path,
            title=title,
            request=request,
        )


async def handle_file(
        *,
        breadcrumbs: List[Breadcrumb],
        download: bool,
        fs_path: Path,
        title: str,
        request: Request
):
    if download:
        return Response(content=fs_path.read_bytes())

    if fs_path.suffix in [".txt", ".css", ".html", ".js", ".rs", ".py"]:
        # Show text file
        return templates.TemplateResponse(
            "text_file.html",
            {
                "request": request,
                "title": title,
                "breadcrumbs": breadcrumbs,
                "content": fs_path.read_text(),
            },
        )
    elif fs_path.suffix == ".md":
        # Show markdown file preview
        return templates.TemplateResponse(
            "markdown_file.html",
            {
                "request": request,
                "title": title,
                "breadcrumbs": breadcrumbs,
                "content": markdown(
                    fs_path.read_text(), extensions=["fenced_code"]
                ),
            },
        )
    elif fs_path.suffix == ".csv":
        # Show csv file preview
        csv_text = fs_path.read_text()
        csv_reader = csv.reader(csv_text.split("\n"))
        table = [row for row in csv_reader]
        return templates.TemplateResponse(
            "csv_file.html",
            {
                "request": request,
                "title": title,
                "breadcrumbs": breadcrumbs,
                "table": table,
            },
        )
    else:
        # Byte-like data, e.g. jpg, png, ...
        return Response(content=fs_path.read_bytes())


@dataclass
class DirEntry:
    name: str
    path: str
    size: str

    @staticmethod
    def from_path(path: Path):
        if path.is_dir():
            size = sum(file.stat().st_size for file in path.glob("*/*") if file.is_file())
        else:
            size = path.stat().st_size

        size = DirEntry.human_format(size)
        return DirEntry(name=path.name, path=path.name + "/", size=size)

    @staticmethod
    def human_format(bytes_: int):
        magnitude_value: float = float(bytes_)
        magnitude = 0
        while abs(magnitude_value) >= 1000:
            magnitude += 1
            magnitude_value /= 1000.0
        magnitude_str = ["B", "KB", "MB", "GB", "TB", "PB"][magnitude]
        if magnitude == 0:
            # No decimal places for bytes
            return f"{magnitude_value:.0f} {magnitude_str}"
        else:
            return f"{magnitude_value:.1f} {magnitude_str}"


async def handle_dir(
        *,
        fs_path: Path,
        breadcrumbs: List[Breadcrumb],
        title: str,
        request: Request
):
    dir_entries: List[str] = os.listdir(fs_path)
    dir_entries: List[DirEntry] = [DirEntry.from_path(fs_path / dir_entry) for dir_entry in dir_entries]

    readme: Optional[str] = None
    try:
        readme = (fs_path / "README.md").read_text()
    except FileNotFoundError:
        pass  # No README.md, no problem. Just don't show it, i.e. use default value (None)

    return templates.TemplateResponse(
        "directory.html",
        {
            "readme": readme,
            "request": request,
            "dir_entries": dir_entries,
            "empty_directory": len(dir_entries) == 0,
            "title": title,
            "breadcrumbs": breadcrumbs,
        },
    )


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

    print("Starting development server on port", port)
    # Host="0.0.0.0" makes the application accessible from other IPs. Necessary when running inside docker
    uvicorn.run("main:api", reload=True, port=port, host="0.0.0.0")


def start_production_server(port: int):
    """Starts a production, i.e. performance-optimized server on port."""

    print("Starting production server on port", port)
    # Host="0.0.0.0" makes the application accessible from other IPs. Necessary when running inside docker
    uvicorn.run("main:api", port=port, host="0.0.0.0")


if __name__ == "__main__":
    main()
