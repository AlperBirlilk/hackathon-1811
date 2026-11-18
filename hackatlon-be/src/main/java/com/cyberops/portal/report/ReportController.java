package com.cyberops.portal.report;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.auth.CurrentUserService;
import com.cyberops.portal.report.ReportService.Filters;

@RestController
public class ReportController {

	private static final MediaType XLSX = MediaType
			.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");

	private final ReportService service;
	private final CurrentUserService currentUser;

	public ReportController(ReportService service, CurrentUserService currentUser) {
		this.service = service;
		this.currentUser = currentUser;
	}

	@GetMapping("/api/reports/tasks.xlsx")
	public ResponseEntity<byte[]> xlsx(@RequestParam(required = false) String status,
			@RequestParam(required = false) String severity, @RequestParam(required = false) Long assigneeId,
			@RequestParam(required = false) Boolean overdue) {
		byte[] body = service.xlsx(currentUser.get(), new Filters(status, severity, assigneeId, overdue));
		return file(body, "xlsx", XLSX);
	}

	@GetMapping("/api/reports/tasks.pdf")
	public ResponseEntity<byte[]> pdf(@RequestParam(required = false) String status,
			@RequestParam(required = false) String severity, @RequestParam(required = false) Long assigneeId,
			@RequestParam(required = false) Boolean overdue) {
		byte[] body = service.pdf(currentUser.get(), new Filters(status, severity, assigneeId, overdue));
		return file(body, "pdf", MediaType.APPLICATION_PDF);
	}

	private static ResponseEntity<byte[]> file(byte[] body, String ext, MediaType type) {
		String name = "gorev-raporu-" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE) + "." + ext;
		return ResponseEntity.ok()
				.header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename(name).build().toString())
				.contentType(type).contentLength(body.length).body(body);
	}
}
