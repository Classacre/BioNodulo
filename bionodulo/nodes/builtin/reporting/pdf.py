"""pdf — reporting node(s). One tool per file (extracted from reporting.py)."""
from __future__ import annotations
import base64
import csv
import html
import json
import mimetypes
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _normalise_file_list(value: Any) -> list[Path]:
    if value is None or value == '':
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [part.strip() for part in str(value).split(',') if part.strip()]
    paths: list[Path] = []
    for item in items:
        path = Path(str(item))
        if not path.exists():
            raise FileNotFoundError(f'Report input file not found: {path}')
        paths.append(path)
    return paths
def _section_names(value: Any) -> list[str]:
    return [part.strip() for part in str(value or '').split(',') if part.strip()]
def _render_text_sections(text_sections: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for index, section in enumerate(str(text_sections or '').split('\n---\n')):
        stripped = section.strip()
        if not stripped:
            continue
        title = f'Text Section {index + 1}'
        lines = stripped.splitlines()
        if lines and lines[0].startswith('#'):
            title = lines[0].lstrip('#').strip() or title
            lines = lines[1:]
        body = '<br>\n'.join((html.escape(line) for line in lines))
        sections.append((title, f'<div class="section-text">{body}</div>'))
    return sections
def _render_image_section(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0]
    if path.suffix.lower() == '.svg':
        mime_type = 'image/svg+xml'
    if mime_type is None:
        mime_type = 'application/octet-stream'
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'<figure class="report-figure"><img src="data:{mime_type};base64,{encoded}" alt="{html.escape(path.stem, quote=True)}"><figcaption>{html.escape(path.name)}</figcaption></figure>'
def _render_table_section(path: Path, max_rows: int) -> str:
    text = path.read_text(encoding='utf-8-sig')
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters='\t,;').delimiter
    except csv.Error:
        delimiter = '\t' if sample.count('\t') >= sample.count(',') else ','
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if not rows:
        return '<div class="table-wrap"><table></table></div>'
    header = rows[0]
    body_rows = rows[1:max(max_rows, 0) + 1]
    thead = ''.join((f'<th>{html.escape(cell)}</th>' for cell in header))
    body = '\n'.join(('<tr>' + ''.join((f'<td>{html.escape(cell)}</td>' for cell in row)) + '</tr>' for row in body_rows))
    return f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table></div>'
def _read_table_lines(path: Path, max_rows: int=50) -> list[str]:
    text = path.read_text(encoding='utf-8-sig')
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters='\t,;').delimiter
    except csv.Error:
        delimiter = '\t' if sample.count('\t') >= sample.count(',') else ','
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    return [' | '.join(row) for row in rows[:max(max_rows, 0) + 1]]
def _optional_qc_file(value: Any) -> Path | None:
    if value is None or value == '':
        return None
    path = Path(str(value))
    if not path.exists():
        raise FileNotFoundError(f'QC dashboard input file not found: {path}')
    return path
def _parse_flagstat_metrics(path: Path) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ' in total' in stripped:
            metrics['Total Reads'] = stripped.split()[0]
        elif ' mapped (' in stripped:
            metrics['Mapped %'] = stripped.split('(', 1)[1].split('%', 1)[0] + '%'
        elif ' properly paired' in stripped and '(' in stripped:
            metrics['Properly Paired'] = stripped.split('(', 1)[1].split('%', 1)[0] + '%'
    return metrics
def _parse_variant_metrics(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        return {}
    metrics: dict[str, str] = {}
    if 'total_variants' in data:
        metrics['Total Variants'] = str(data['total_variants'])
    if 'titv_ratio' in data:
        metrics['Ti/Tv Ratio'] = str(data['titv_ratio'])
    return metrics
def _parse_custom_metrics(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError('Custom QC metrics must be a JSON object')
    return {str(key): str(val) for key, val in data.items()}
def _add_read_retention_metrics(metrics: dict[str, str]) -> None:
    raw = _first_numeric_metric(metrics, 'raw_reads', 'total_reads', 'input_reads', 'reads_before')
    retained = _first_numeric_metric(metrics, 'trimmed_reads', 'filtered_reads', 'retained_reads', 'reads_after')
    if raw is None or retained is None or raw <= 0:
        return
    retained = max(0.0, min(retained, raw))
    retention = retained / raw * 100
    loss = 100 - retention
    metrics.setdefault('Read Retention', f'{retention:.2f}%')
    metrics.setdefault('Read Loss', f'{loss:.2f}%')
def _first_numeric_metric(metrics: dict[str, str], *keys: str) -> float | None:
    normalized = {_metric_key(key): value for key, value in metrics.items()}
    for key in keys:
        value = normalized.get(_metric_key(key))
        if value is None:
            continue
        try:
            return float(str(value).replace(',', ''))
        except ValueError:
            continue
    return None
def _metric_key(key: str) -> str:
    return str(key).strip().lower().replace(' ', '_').replace('-', '_')
def _read_coverage_rows(path: Path, max_rows: int=100) -> list[dict[str, str]]:
    text = path.read_text(encoding='utf-8-sig')
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters='\t,;').delimiter
    except csv.Error:
        delimiter = '\t' if sample.count('\t') >= sample.count(',') else ','
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for row in reader:
        if 'depth' not in row or 'count' not in row:
            continue
        rows.append({'depth': str(row['depth']), 'count': str(row['count'])})
        if len(rows) >= max_rows:
            break
    return rows
def _pdf_escape(text: str) -> str:
    return str(text).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').replace('\r', ' ').replace('\n', ' ')
def _pdf_stream_lines(lines: list[str], *, page_width: int, page_height: int) -> str:
    margin = 56
    y = page_height - margin
    parts = ['BT', '/F1 11 Tf', '14 TL']
    for line in lines:
        if y < margin:
            break
        parts.append(f'1 0 0 1 {margin} {y} Tm')
        parts.append(f'({_pdf_escape(line[:120])}) Tj')
        y -= 16
    parts.append('ET')
    return '\n'.join(parts) + '\n'
def _write_simple_pdf(path: Path, *, lines: list[str], title: str, author: str, page_size: str, orientation: str) -> None:
    sizes = {'a4': (595, 842), 'letter': (612, 792)}
    if page_size not in sizes:
        raise ValueError(f'Unsupported PDF page size: {page_size}')
    if orientation not in {'portrait', 'landscape'}:
        raise ValueError(f'Unsupported PDF orientation: {orientation}')
    width, height = sizes[page_size]
    if orientation == 'landscape':
        width, height = (height, width)
    stream = _pdf_stream_lines(lines, page_width=width, page_height=height)
    objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>', f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}endstream", f'<< /Title ({_pdf_escape(title)}) /Author ({_pdf_escape(author)}) /Producer (BioNodulo) >>']
    chunks = ['%PDF-1.4\n%âãÏÓ\n']
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum((len(chunk.encode('latin-1', errors='replace')) for chunk in chunks)))
        chunks.append(f'{index} 0 obj\n{obj}\nendobj\n')
    xref_offset = sum((len(chunk.encode('latin-1', errors='replace')) for chunk in chunks))
    chunks.append(f'xref\n0 {len(objects) + 1}\n')
    chunks.append('0000000000 65535 f \n')
    for offset in offsets[1:]:
        chunks.append(f'{offset:010d} 00000 n \n')
    chunks.append(f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n')
    path.write_bytes(''.join(chunks).encode('latin-1', errors='replace'))
def _theme_tokens(theme: str) -> dict[str, str]:
    if theme == 'light':
        return {'bg': '#FFFFFF', 'text': '#111827', 'muted': '#475569', 'section': '#F8FAFC', 'border': '#CBD5E1', 'accent': '#2563EB', 'table_alt': '#F1F5F9'}
    if theme == 'dark':
        return {'bg': '#0F172A', 'text': '#E5E7EB', 'muted': '#94A3B8', 'section': '#1E293B', 'border': '#334155', 'accent': '#60A5FA', 'table_alt': '#111827'}
    raise ValueError(f'Unsupported HTML report theme: {theme}')


class PDFReportNode(BaseNode):
    """Generate a simple PDF report from text and tables."""
    NODE_ID = 'pdf_report'
    DISPLAY_NAME = 'PDF Report'
    CATEGORY = 'reporting'
    DESCRIPTION = 'Generate printable PDF reports with text and table summaries.'
    SEARCH_ALIASES = ['pdf report', 'pdf', 'printable report', 'publication', 'document', 'static report']
    RETURN_TYPES = ('PDF_REPORT',)
    RETURN_NAMES = ('pdf_report',)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'title': ('STRING', {'default': 'BioNodulo Report'})}, 'optional': {'images': ('FILE', {'default': '', 'description': 'Accepted for API compatibility; listed in report'}), 'tables': ('FILE', {'default': '', 'description': 'Comma-separated CSV/TSV tables'}), 'text': ('STRING', {'default': '', 'multiline': True}), 'section_names': ('STRING', {'default': ''}), 'page_size': ('STRING', {'default': 'A4', 'options': ['A4', 'Letter']}), 'orientation': ('STRING', {'default': 'portrait', 'options': ['portrait', 'landscape']}), 'author': ('STRING', {'default': 'BioNodulo'}), 'header_text': ('STRING', {'default': ''})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop('context', None)
        title = str(kwargs.get('title', 'BioNodulo Report') or 'BioNodulo Report')
        author = str(kwargs.get('author', 'BioNodulo') or 'BioNodulo')
        page_size = str(kwargs.get('page_size', 'A4') or 'A4').strip().lower()
        orientation = str(kwargs.get('orientation', 'portrait') or 'portrait').strip().lower()
        tables = _normalise_file_list(kwargs.get('tables', ''))
        images = _normalise_file_list(kwargs.get('images', ''))
        names = _section_names(kwargs.get('section_names', ''))
        lines = [title, f'Generated by {author}']
        header = str(kwargs.get('header_text', '') or '').strip()
        if header:
            lines.append(header)
        lines.append('')
        text = str(kwargs.get('text', '') or '').strip()
        if text:
            for section in text.split('\n---\n'):
                for line in section.strip().splitlines():
                    if line.strip():
                        lines.append(line.strip())
                lines.append('')
        for index, image in enumerate(images):
            name = names[index] if index < len(names) else image.stem
            lines.extend([name, f'Image: {image.name}', ''])
        table_offset = len(images)
        for index, table in enumerate(tables):
            name_index = table_offset + index
            name = names[name_index] if name_index < len(names) else table.stem
            lines.append(name)
            lines.extend(_read_table_lines(table, max_rows=50))
            lines.append('')
        out_dir = _node_output_dir(self, context)
        output_path = out_dir / 'report.pdf'
        _write_simple_pdf(output_path, lines=lines, title=title, author=author, page_size=page_size, orientation=orientation)
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(output_path, label='PDF Report')
        return {'outputs': {'pdf_report': str(output_path)}}
