package com.cyberops.portal.task;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

/** DuckDB TIMESTAMP columns hold local (server zone) time; API exposes ISO-8601 with offset. */
public final class TimeUtil {

	private static final DateTimeFormatter TR = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm");

	private TimeUtil() {
	}

	public static LocalDateTime now() {
		return LocalDateTime.now().withNano(0);
	}

	public static LocalDateTime local(ResultSet rs, String col) throws SQLException {
		Timestamp ts = rs.getTimestamp(col);
		return ts == null ? null : ts.toLocalDateTime();
	}

	public static OffsetDateTime offset(LocalDateTime ldt) {
		return ldt == null ? null : ldt.atZone(ZoneId.systemDefault()).toOffsetDateTime();
	}

	public static OffsetDateTime offset(ResultSet rs, String col) throws SQLException {
		return offset(local(rs, col));
	}

	public static Timestamp ts(LocalDateTime ldt) {
		return ldt == null ? null : Timestamp.valueOf(ldt);
	}

	public static String tr(LocalDateTime ldt) {
		return ldt == null ? "—" : ldt.format(TR);
	}

	/** Accepts ISO offset date-time, ISO local date-time or ISO date; returns server-local time. */
	public static LocalDateTime parse(Object value) {
		if (value == null) {
			return null;
		}
		String s = value.toString().trim();
		if (s.isEmpty()) {
			return null;
		}
		try {
			return OffsetDateTime.parse(s).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime();
		}
		catch (DateTimeParseException e) {
			// fall through
		}
		try {
			return LocalDateTime.parse(s);
		}
		catch (DateTimeParseException e) {
			// fall through
		}
		try {
			return LocalDate.parse(s).atTime(23, 59);
		}
		catch (DateTimeParseException e) {
			throw new IllegalArgumentException("Geçersiz tarih: " + s);
		}
	}
}
