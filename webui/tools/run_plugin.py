"""Run one upstream plugin (plugins/<id>/fetch.py) against a webui job folder instead of the repo's game/.

Usage:  python webui/tools/run_plugin.py <job_dir> <plugin_id> <deck_path_or_url> <format> [options...]

Every fetch.py keeps its output folders in module globals (front_directory, double_sided_directory, ...) that
point at <repo>/game/...; the cli reads them at call time, so re-pointing them here is enough — upstream code is
not modified.

Before the plugin is imported, webui/capture.py puts a persistent HTTP cache in front of requests (nothing is
downloaded twice) and keeps every JSON answer in <job_dir>/raw/ for the card catalog.
"""
import importlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'webui'))


def main() -> None:
    job, plugin, *args = sys.argv[1:]
    import capture
    capture.install(job)
    game = os.path.join(REPO, 'game')
    mod = importlib.import_module(f'plugins.{plugin}.fetch')
    for name, value in vars(mod).items():
        if name.endswith('_directory') and isinstance(value, str) and os.path.abspath(value).startswith(game):
            setattr(mod, name, os.path.join(job, os.path.relpath(os.path.abspath(value), game)))

    from utilities import configure_console_encoding
    configure_console_encoding()
    mod.cli.main(args=args, prog_name=f'{plugin}/fetch.py', standalone_mode=True)


if __name__ == '__main__':
    main()
