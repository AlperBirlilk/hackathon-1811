package com.cyberops.portal.report;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.List;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import com.cyberops.portal.auth.CurrentUser;
import com.cyberops.portal.task.TaskVisibility;
import com.cyberops.portal.user.PersonRef;

/** Read-only task query for exports. Applies {@link TaskVisibility} (same rule as /api/tasks). */
@Repository
public class ReportRepository {

	public record ReportRow(long id, String title, String status, String severity, String assignees, String backup,
			LocalDateTime dueDate, boolean overdue) {
	}

	private final NamedParameterJdbcTemplate jdbc;

	public ReportRepository(NamedParameterJdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	public List<ReportRow> tasks(CurrentUser me, String status, String severity, Long assigneeId, Boolean overdue) {
		MapSqlParameterSource p = new MapSqlParameterSource();
		StringBuilder sql = new StringBuilder("""
				SELECT t.id, t.task_title, t.task_status, t.task_severity, t.due_date,
				  (t.task_status <> 'DONE' AND t.due_date IS NOT NULL AND t.due_date < current_localtimestamp()) AS is_overdue,
				  (SELECT string_agg(%s, ', ' ORDER BY u2.id) FROM task_assignee ta2
				     JOIN app_user u2 ON u2.id = ta2.user_id WHERE ta2.task_id = t.id) AS assignees,
				  %s AS backup_name
				FROM task t
				LEFT JOIN app_user b ON b.id = t.backup_assignee_id
				WHERE\s""".formatted(PersonRef.displayNameSql("u2"), "CASE WHEN b.id IS NULL THEN NULL ELSE "
				+ PersonRef.displayNameSql("b") + " END"));
		sql.append(TaskVisibility.where(me, p));
		if (status != null) {
			sql.append(" AND t.task_status = :status");
			p.addValue("status", status);
		}
		if (severity != null) {
			sql.append(" AND t.task_severity = :severity");
			p.addValue("severity", severity);
		}
		if (assigneeId != null) {
			sql.append(" AND EXISTS (SELECT 1 FROM task_assignee ta3 WHERE ta3.task_id = t.id AND ta3.user_id = :assigneeId)");
			p.addValue("assigneeId", assigneeId);
		}
		if (overdue != null) {
			sql.append(overdue ? " AND " : " AND NOT ");
			sql.append("(t.task_status <> 'DONE' AND t.due_date IS NOT NULL AND t.due_date < current_localtimestamp())");
		}
		sql.append(" ORDER BY t.id");
		return jdbc.query(sql.toString(), p, (rs, i) -> {
			Timestamp due = rs.getTimestamp("due_date");
			return new ReportRow(rs.getLong("id"), rs.getString("task_title"), rs.getString("task_status"),
					rs.getString("task_severity"), nz(rs.getString("assignees")), nz(rs.getString("backup_name")),
					due == null ? null : due.toLocalDateTime(), rs.getBoolean("is_overdue"));
		});
	}

	private static String nz(String s) {
		return s == null ? "" : s;
	}
}
