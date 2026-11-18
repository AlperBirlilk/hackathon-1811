package com.cyberops.portal.report;

import java.awt.Color;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFFont;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.cyberops.portal.auth.CurrentUser;
import com.cyberops.portal.common.ForbiddenException;
import com.cyberops.portal.common.PermissionCodes;
import com.cyberops.portal.report.ReportRepository.ReportRow;
import com.lowagie.text.Document;
import com.lowagie.text.Element;
import com.lowagie.text.Font;
import com.lowagie.text.PageSize;
import com.lowagie.text.Paragraph;
import com.lowagie.text.Phrase;
import com.lowagie.text.pdf.BaseFont;
import com.lowagie.text.pdf.PdfPCell;
import com.lowagie.text.pdf.PdfPTable;
import com.lowagie.text.pdf.PdfWriter;

/** Task export (Excel / PDF). Requires REPORT_ANALYSIS; task visibility applied in ReportRepository. */
@Service
public class ReportService {

	private static final Logger log = LoggerFactory.getLogger(ReportService.class);

	static final String[] HEADERS = { "Kod", "Başlık", "Durum", "Önem", "Sorumlular", "Yedek", "Son Tarih",
			"Gecikmiş" };
	private static final Map<String, String> STATUS_TR = Map.of("OPEN", "Açık", "IN_PROGRESS", "Devam Ediyor", "DONE",
			"Tamamlandı");
	private static final Map<String, String> SEVERITY_TR = Map.of("LOW", "Düşük", "MEDIUM", "Orta", "HIGH", "Yüksek",
			"CRITICAL", "Kritik");
	private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm");
	private static final List<String> FONT_CANDIDATES = List.of(
			"/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
			"/Library/Fonts/Arial Unicode.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
			"/usr/share/fonts/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf");

	private final ReportRepository repo;

	public ReportService(ReportRepository repo) {
		this.repo = repo;
	}

	public record Filters(String status, String severity, Long assigneeId, Boolean overdue) {
	}

	private List<String[]> rows(CurrentUser me, Filters f) {
		if (!me.hasPerm(PermissionCodes.REPORT_ANALYSIS)) {
			throw new ForbiddenException();
		}
		String status = normEnum(f.status(), STATUS_TR.keySet(), "durum");
		String severity = normEnum(f.severity(), SEVERITY_TR.keySet(), "önem");
		return repo.tasks(me, status, severity, f.assigneeId(), f.overdue()).stream().map(this::toCells).toList();
	}

	private String[] toCells(ReportRow r) {
		return new String[] { String.format("TSK-%04d", r.id()), sanitize(r.title()),
				STATUS_TR.getOrDefault(r.status(), r.status()), SEVERITY_TR.getOrDefault(r.severity(), r.severity()),
				sanitize(r.assignees()), sanitize(r.backup()), r.dueDate() == null ? "" : DATE_FMT.format(r.dueDate()),
				r.overdue() ? "Evet" : "Hayır" };
	}

	/** Formula-injection guard: values starting with = + - @ (or tab/CR) are prefixed with a quote. */
	static String sanitize(String v) {
		if (v == null || v.isEmpty()) {
			return "";
		}
		char c = v.charAt(0);
		return (c == '=' || c == '+' || c == '-' || c == '@' || c == '\t' || c == '\r') ? "'" + v : v;
	}

	private static String normEnum(String v, Set<String> allowed, String label) {
		if (v == null || v.isBlank()) {
			return null;
		}
		String u = v.trim().toUpperCase();
		if (!allowed.contains(u)) {
			throw new IllegalArgumentException("Geçersiz " + label + " filtresi: " + v);
		}
		return u;
	}

	public byte[] xlsx(CurrentUser me, Filters f) {
		List<String[]> data = rows(me, f);
		try (XSSFWorkbook wb = new XSSFWorkbook(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
			Sheet sheet = wb.createSheet("Görevler");
			CellStyle headerStyle = wb.createCellStyle();
			XSSFFont bold = wb.createFont();
			bold.setBold(true);
			headerStyle.setFont(bold);
			Row header = sheet.createRow(0);
			for (int i = 0; i < HEADERS.length; i++) {
				Cell c = header.createCell(i);
				c.setCellValue(HEADERS[i]);
				c.setCellStyle(headerStyle);
			}
			int r = 1;
			for (String[] cells : data) {
				Row row = sheet.createRow(r++);
				for (int i = 0; i < cells.length; i++) {
					row.createCell(i).setCellValue(cells[i]); // always string cells, never formulas
				}
			}
			for (int i = 0; i < HEADERS.length; i++) {
				sheet.autoSizeColumn(i);
			}
			wb.write(out);
			return out.toByteArray();
		}
		catch (IOException e) {
			throw new IllegalStateException("Excel oluşturulamadı", e);
		}
	}

	public byte[] pdf(CurrentUser me, Filters f) {
		List<String[]> data = rows(me, f);
		ByteArrayOutputStream out = new ByteArrayOutputStream();
		Document doc = new Document(PageSize.A4.rotate(), 24, 24, 24, 24);
		PdfWriter.getInstance(doc, out);
		doc.open();
		BaseFont bf = baseFont();
		Font titleFont = new Font(bf, 14, Font.BOLD);
		Font headFont = new Font(bf, 9, Font.BOLD, Color.WHITE);
		Font cellFont = new Font(bf, 8);
		doc.add(new Paragraph("Görev Raporu (" + data.size() + " kayıt)", titleFont));
		doc.add(new Paragraph(" ", cellFont));
		PdfPTable table = new PdfPTable(HEADERS.length);
		table.setWidthPercentage(100);
		table.setWidths(new float[] { 7, 24, 9, 7, 18, 12, 11, 7 });
		table.setHeaderRows(1);
		for (String h : HEADERS) {
			PdfPCell c = new PdfPCell(new Phrase(h, headFont));
			c.setBackgroundColor(new Color(40, 55, 80));
			c.setHorizontalAlignment(Element.ALIGN_LEFT);
			table.addCell(c);
		}
		for (String[] cells : data) {
			for (String v : cells) {
				table.addCell(new PdfPCell(new Phrase(v, cellFont)));
			}
		}
		doc.add(table);
		doc.close();
		return out.toByteArray();
	}

	private static BaseFont baseFont() {
		for (String path : FONT_CANDIDATES) {
			if (new File(path).isFile()) {
				try {
					return BaseFont.createFont(path, BaseFont.IDENTITY_H, BaseFont.EMBEDDED);
				}
				catch (Exception e) {
					log.warn("Font yüklenemedi: {}", path, e);
				}
			}
		}
		try {
			return BaseFont.createFont(BaseFont.HELVETICA, BaseFont.CP1252, BaseFont.NOT_EMBEDDED);
		}
		catch (Exception e) {
			throw new IllegalStateException("PDF fontu yüklenemedi", e);
		}
	}
}
