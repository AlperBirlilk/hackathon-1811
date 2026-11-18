package com.cyberops.portal.notification;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class NotificationRepository {

	private final NamedParameterJdbcTemplate jdbc;

	public NotificationRepository(NamedParameterJdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	public void insert(long userId, Long taskId, String message, LocalDateTime now) {
		jdbc.update("""
				INSERT INTO notification (user_id, task_id, message, is_read, create_date)
				VALUES (:u, :t, :m, FALSE, :now)
				""", new MapSqlParameterSource().addValue("u", userId).addValue("t", taskId).addValue("m", message)
				.addValue("now", Timestamp.valueOf(now)));
	}

	public List<NotificationDtos.Notification> list(long userId, boolean unreadOnly) {
		String sql = "SELECT id, task_id, message, is_read, create_date FROM notification WHERE user_id = :u"
				+ (unreadOnly ? " AND NOT is_read" : "") + " ORDER BY create_date DESC, id DESC LIMIT 20";
		return jdbc.query(sql, new MapSqlParameterSource("u", userId), (rs, i) -> {
			long t = rs.getLong("task_id");
			NotificationDtos.TaskRef task = rs.wasNull() ? null
					: new NotificationDtos.TaskRef(t, String.format("TSK-%04d", t));
			Timestamp ts = rs.getTimestamp("create_date");
			return new NotificationDtos.Notification(rs.getLong("id"), rs.getString("message"), task,
					rs.getBoolean("is_read"),
					ts == null ? null : ts.toLocalDateTime().atZone(ZoneId.systemDefault()).toOffsetDateTime());
		});
	}

	public long unreadCount(long userId) {
		Long c = jdbc.queryForObject("SELECT count(*) FROM notification WHERE user_id = :u AND NOT is_read",
				new MapSqlParameterSource("u", userId), Long.class);
		return c == null ? 0 : c;
	}

	/** @return true if the notification exists and belongs to the user */
	public boolean markRead(long id, long userId) {
		MapSqlParameterSource p = new MapSqlParameterSource().addValue("id", id).addValue("u", userId);
		Long c = jdbc.queryForObject("SELECT count(*) FROM notification WHERE id = :id AND user_id = :u", p,
				Long.class);
		if (c == null || c == 0) {
			return false;
		}
		jdbc.update("UPDATE notification SET is_read = TRUE WHERE id = :id AND user_id = :u AND NOT is_read", p);
		return true;
	}

	public void markAllRead(long userId) {
		jdbc.update("UPDATE notification SET is_read = TRUE WHERE user_id = :u AND NOT is_read",
				new MapSqlParameterSource("u", userId));
	}
}
