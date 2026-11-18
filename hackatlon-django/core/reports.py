"""Task raporları (Excel / PDF). Veri her zaman visible_tasks(user) ile scope edilir."""
import io
import logging
import os

from django.db.models import Q
from django.utils import timezone

from .models import Task
from .views import SEVERITY_RANK, my_tasks_for, overdue_q, visible_tasks

logger = logging.getLogger(__name__)

HEADERS = ['Kod', 'Başlık', 'Durum', 'Önem', 'Sorumlular', 'Yedek', 'Son Tarih', 'Gecikmiş']
_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')
_TRUE_VALUES = {'1', 'true', 'on', 'yes'}


def filter_tasks(user, params):
    """task_list sayfasıyla aynı filtreler (+ overdue), visible_tasks scope'u ile."""
    qs = visible_tasks(user)
    status = (params.get('status') or '').strip()
    severity = (params.get('severity') or '').strip()
    q = (params.get('q') or '').strip()
    if status:
        qs = qs.filter(task_status=status)
    if severity:
        qs = qs.filter(task_severity=severity)
    if q:
        qs = qs.filter(Q(task_title__icontains=q) | Q(task_description__icontains=q))
    if (params.get('overdue') or '').strip().lower() in _TRUE_VALUES:
        qs = qs.filter(overdue_q())
    if (params.get('mine') or '').strip().lower() in _TRUE_VALUES:
        qs = qs.filter(pk__in=my_tasks_for(user).values('pk'))
    return (qs.annotate(sev_rank=SEVERITY_RANK).order_by('sev_rank', '-modified_date')
            .prefetch_related('assignees').select_related('backup_assignee'))


def filters_summary(params):
    """PDF başlığı için uygulanan filtrelerin Türkçe özeti."""
    parts = []
    status = dict(Task.STATUS_CHOICES).get(params.get('status') or '')
    severity = dict(Task.SEVERITY_CHOICES).get(params.get('severity') or '')
    q = (params.get('q') or '').strip()
    if status:
        parts.append(f'Durum: {status}')
    if severity:
        parts.append(f'Önem: {severity}')
    if q:
        parts.append(f'Arama: "{q[:80]}"')
    if (params.get('overdue') or '').strip().lower() in _TRUE_VALUES:
        parts.append('Yalnızca gecikmiş')
    return ', '.join(parts) if parts else 'Yok (tüm görünür işler)'


def sanitize_cell(value):
    """Formül enjeksiyonuna karşı = + - @ \\t \\r ile başlayan metinlerin başına ' ekler."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _format_due(task):
    if not task.due_date:
        return ''
    return timezone.localtime(task.due_date).strftime('%d.%m.%Y %H:%M')


def task_rows(tasks):
    """Her task için kolon sırasında (sanitize edilmiş) string değerler."""
    for t in tasks:
        row = [
            t.code,
            t.task_title,
            t.get_task_status_display(),
            t.get_task_severity_display(),
            ', '.join(a.display_name for a in t.assignees.all()),
            t.backup_assignee.display_name if t.backup_assignee else '',
            _format_due(t),
            'Evet' if t.is_overdue else 'Hayır',
        ]
        yield [sanitize_cell(v) for v in row]


# --------------------------------------------------------------------------- xlsx

def build_xlsx(tasks):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Görevler'
    ws.append(HEADERS)
    header_fill = PatternFill('solid', fgColor='E2F0F1')
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(vertical='center')

    count = 0
    for row in task_rows(tasks):
        ws.append(row)
        count += 1
    # openpyxl, '=' ile başlayan string'leri formül olarak işaretler; sanitize sonrası hepsi düz metin.
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = 's'
        row[1].alignment = Alignment(wrap_text=True, vertical='top')

    widths = [11, 50, 15, 10, 32, 20, 17, 10]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{get_column_letter(len(HEADERS))}{count + 1}'

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------- pdf

_FONT_CANDIDATES = [
    (r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\arialbd.ttf'),
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', None),
]
_fonts_cache = None


def _pdf_fonts():
    """Türkçe karakterler için Unicode TTF'i bir kez kaydeder; (normal, bold) font adlarını döner."""
    global _fonts_cache
    if _fonts_cache is not None:
        return _fonts_cache
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for regular, bold in _FONT_CANDIDATES:
        if not os.path.exists(regular):
            continue
        try:
            pdfmetrics.registerFont(TTFont('PortalSans', regular))
            bold_name = 'PortalSans'
            if bold and os.path.exists(bold):
                pdfmetrics.registerFont(TTFont('PortalSans-Bold', bold))
                bold_name = 'PortalSans-Bold'
            _fonts_cache = ('PortalSans', bold_name)
            return _fonts_cache
        except Exception:  # bozuk / okunamayan font dosyası: sıradakini dene
            logger.exception('PDF font yüklenemedi: %s', regular)
    logger.warning('Unicode TTF font bulunamadı; PDF Helvetica ile üretilecek (Türkçe karakterler bozulabilir).')
    _fonts_cache = ('Helvetica', 'Helvetica-Bold')
    return _fonts_cache


def build_pdf(tasks, filters_text=''):
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font, font_bold = _pdf_fonts()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('t', parent=styles['Title'], fontName=font_bold, fontSize=16, alignment=0)
    meta_style = ParagraphStyle('m', parent=styles['Normal'], fontName=font, fontSize=9,
                                textColor=colors.HexColor('#677382'))
    cell_style = ParagraphStyle('c', parent=styles['Normal'], fontName=font, fontSize=8, leading=10)
    head_style = ParagraphStyle('h', parent=cell_style, fontName=font_bold)

    def p(text, style=cell_style):
        return Paragraph(escape(str(text)), style)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title='Görev Raporu')
    now = timezone.localtime().strftime('%d.%m.%Y %H:%M')
    story = [
        Paragraph('Görev Raporu', title_style),
        p(f'Oluşturulma: {now}', meta_style),
        p(f'Filtreler: {filters_text or "Yok"}', meta_style),
        Spacer(1, 6 * mm),
    ]

    data = [[p(h, head_style) for h in HEADERS]]
    rows = list(task_rows(tasks))
    for row in rows:
        data.append([p(v) for v in row])
    if not rows:
        data.append([p('Filtrelere uyan görev yok.')] + [''] * (len(HEADERS) - 1))

    col_widths = [20 * mm, 85 * mm, 24 * mm, 18 * mm, 50 * mm, 30 * mm, 27 * mm, 18 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2F0F1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#0E6E78')),
        ('LINEBELOW', (0, 1), (-1, -1), 0.25, colors.HexColor('#DCE1E6')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    if not rows:
        style.append(('SPAN', (0, 1), (-1, 1)))
    table.setStyle(TableStyle(style))
    story.append(table)
    doc.build(story)
    return buf.getvalue()
