from pathlib import Path
import shutil


def _copy_static_assets(source_dir: Path, output_dir: Path) -> None:
    """Copy static dashboard files (HTML/CSS/JS shell) to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("index.html", "styles.css", "app.js"):
        src = source_dir / filename
        if not src.exists():
            raise FileNotFoundError(f"Missing dashboard static asset: {src}")
        shutil.copy2(src, output_dir / filename)


def generate_dashboard_bundle(
    js_vars: str,
    output_dir: str = "results/dashboard",
    static_dir: str = "src/dashboard/static",
    legacy_html_path: str = "results/dashboard.html",
) -> None:
    """Generate modular dashboard bundle and a legacy redirect HTML file.

    `js_vars` is a JS snippet defining data constants (DATES, SUMMARY, etc.).
    """
    output_dir_path = Path(output_dir)
    static_dir_path = Path(static_dir)
    _copy_static_assets(static_dir_path, output_dir_path)

    data_js_path = output_dir_path / "data.js"
    data_js_path.write_text(js_vars.strip() + "\n", encoding="utf-8")

    # Keep backward compatibility for scripts/users opening results/dashboard.html
    legacy_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url=dashboard/index.html">
    <title>Dashboard Redirect</title>
</head>
<body>
    <p>Redirecting to <a href="dashboard/index.html">dashboard/index.html</a>...</p>
</body>
</html>
"""
    Path(legacy_html_path).write_text(legacy_html, encoding="utf-8")

    print(f"Dashboard bundle generated at {output_dir_path / 'index.html'}")
    print(f"Dashboard data generated at {data_js_path}")
    print(f"Legacy redirect page updated at {legacy_html_path}")
