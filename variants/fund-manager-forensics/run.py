#!/usr/bin/env python3
"""Repository shortcut to the same runner shipped in the installed Skill."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
from pathlib import Path
import argparse
import sys
import webbrowser
from html import escape
from urllib.parse import quote

runtime = import_module("skills.fund-manager-forensics.scripts.fund_case")
merge_agent_review = runtime.merge_agent_review
ROOT = Path(__file__).resolve().parent


def write_library(base):
    entries = []
    for manifest in sorted(base.glob("*/case.json")):
        if manifest.parent.is_symlink():
            continue
        m = runtime.read(manifest)
        for stem, mode in [("report","深度"),("quick","快报")]:
            if not (manifest.parent / (stem + ".html")).is_file():
                continue
            entries.append(f'<li><a href="{quote(manifest.parent.name)}/{stem}.html">'
                           f'{escape(m["fund"]["short_name"])} · {escape(m["fund"]["code"])}</a>'
                           f'<small>{escape(m["subject"])}　/　{mode}　/　{escape(m["as_of"])}</small></li>')
    runtime.save(base/"index.html",'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>基金研究档案</title><style>body{font:18px/1.6 system-ui;color:#203e32;background:#f5f2e9;max-width:760px;margin:8vh auto;padding:20px}h1{border-top:8px solid;padding-top:20px}li{border-bottom:1px solid #baae97;padding:18px 0;list-style:none}ul{padding:0}a{color:inherit;font-weight:750}small{display:block;color:#585b53}</style><h1>基金研究档案</h1><ul>'+''.join(entries)+'</ul></html>')


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    opts, args = parser.parse_known_args(argv)
    result = runtime.main(args, default_root=ROOT / "cases")
    if not result and not any(a.split("=")[0] in {"--init","--workspace","--output","--collect-nav","--collect-prices","--collect-holdings"} for a in args):
        write_library(ROOT / "cases")
    if result or not opts.serve:
        return result
    lookup = argparse.ArgumentParser(add_help=False)
    lookup.add_argument("fund_code")
    lookup.add_argument("--case")
    lookup.add_argument("--workspace", type=Path, default=ROOT / "cases")
    lookup.add_argument("--mode", default="deep")
    lookup.add_argument("--output", type=Path)
    query, _ = lookup.parse_known_args(args)
    folder = runtime.case_path(query.workspace,query.fund_code,query.case)
    path = query.output.with_suffix(".html") if query.output else folder / ("report.html" if query.mode=="deep" else "quick.html")
    if not path.is_file():
        print("当前动作未生成网页。",file=sys.stderr)
        return 1
    handler = partial(SimpleHTTPRequestHandler,directory=str(path.parent))
    try:
        with ThreadingHTTPServer(("127.0.0.1",opts.port),handler) as server:
            url = f"http://127.0.0.1:{server.server_port}/{quote(path.name)}"
            print(url,flush=True)
            if "--no-browser" not in args:
                webbrowser.open(url)
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(str(exc),file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
