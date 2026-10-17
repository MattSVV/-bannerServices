"""
Render every built-in template with the reference cover to PNG files (visual evidence, see docs/testing.md).

    QT_QPA_PLATFORM=offscreen ../openlp/.venv/bin/python scripts/render_samples.py [output_dir]

The output dir defaults to docs/img. Prints one line per template: size, overflow report and sampled pixels.
"""
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main():
    # The plugin is a package named ``contrib.plugins.portadas`` inside OpenLP: link it the same way here.
    data_dir = Path(tempfile.mkdtemp(prefix='portadas-samples-'))
    (data_dir / 'contrib' / 'plugins').mkdir(parents=True)
    (data_dir / 'contrib' / 'plugins' / 'portadas').symlink_to(REPO / 'portadas', target_is_directory=True)
    sys.path.insert(0, str(data_dir))

    from contrib.plugins.portadas.adapters.qt_renderer import QtCoverRenderer
    from contrib.plugins.portadas.application.icon_catalog import IconCatalog
    from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
    from contrib.plugins.portadas.domain.cover import Cover
    from contrib.plugins.portadas.domain.templating import render_cover
    from PyQt5 import QtCore, QtGui, QtWebEngineWidgets, QtWidgets  # noqa: F401  (WebEngine before QApplication)

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv[:1])  # noqa: F841
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / 'docs' / 'img'
    out.mkdir(parents=True, exist_ok=True)
    catalog, icons, renderer = TemplateCatalog(), IconCatalog(), QtCoverRenderer()
    for manifest in catalog.list():
        cover = Cover.from_raw(
            'Resistir', title_accent='al diablo', subtitle='Firmes en la batalla de la mente:\nun corazón guardado',
            key_verse='Efesios 6:11', readings=['Efesios 6:11-12', 'Romanos 8:1 · 12:1-2'], template_id=manifest.id)
        template = catalog.load(manifest.id)
        html = render_cover(template.html, cover, icons.svg('shield-heart'), required=template.manifest.required)
        result = renderer.render(html, catalog.root / manifest.id)
        target = out / f'cover-{manifest.id}.png'
        target.write_bytes(result.png_bytes)
        image = QtGui.QImage.fromData(result.png_bytes)
        corner = image.pixelColor(4, 4)
        print(f'{target.name}: {image.width()}x{image.height()} overflow={list(result.overflow)} '
              f'pixel(4,4)=#{corner.red():02x}{corner.green():02x}{corner.blue():02x}')
    renderer.close()


if __name__ == '__main__':
    main()
