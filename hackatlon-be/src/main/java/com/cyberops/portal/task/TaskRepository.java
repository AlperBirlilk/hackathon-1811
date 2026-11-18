package com.cyberops.portal.task;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import com.cyberops.portal.task.TaskDtos.HistoryEntry;

@Repository
public class TaskRepository {

	/** Raw task row with joined user refs. */
	public record TaskRow(long id, String title, String status, String severity, String description,
			LocalDateTime dueDate, Long backupAssigneeId, UserRef backupAssignee, LocalDateTime createDate,
			Long createdById, UserRef createdBy, LocalDateTime modifiedDate, UserRef modifiedBy, boolean handover) {
	}

	public static final String SEVERITY_ORDER = "CASE t.task_severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1"
			+ " WHEN 'MEDIUM' THEN 2 ELSE 3 END";

	private static final String SELECT = """
			SELECT t.id, t.task_title, t.task_status, t.task_severity, t.task_description, t.due_date,
			       t.backup_assignee_id, t.create_date, t.created_by, t.modified_date, t.modified_by,
			       bu.id AS b_id, bu.username AS b_username, bu.first_name AS b_first_name, bu.last_name AS b_last_name,
			       cu.id AS c_id, cu.username AS c_username, cu.first_name AS c_first_name, cu.last_name AS c_last_name,
			       mu.id AS m_id, mu.username AS m_username, mu.first_name AS m_first_name, mu.last_name AS m_last_name,
			       EXISTS (SELECT 1 FROM task_assignee hx JOIN app_user hu ON hu.id = hx.user_id
			               WHERE hx.task_id = t.id AND hu.is_on_leave) AS handover
			FROM task t
			LEFT JOIN app_user bu ON bu.id = t.backup_assignee_id
			LEFT JOIN app_user cu ON cu.id = t.created_by
			LEFT JOIN app_user mu ON mu.id = t.modified_by
			""";

	private final NamedParameterJdbcTemplate jdbc;

	public TaskRepository(NamedParameterJdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	/**
	 * @param where SQL predicate on alias t built only from constant fragments; values go in {@code p}.
	 * @param orderBy constant ORDER BY expression
	 */
	public List<TaskRow> find(String where, MapSqlParameterSource p, String orderBy, Integer limit) {
		String sql = SELECT + " WHERE " + where + " ORDER BY " + orderBy;
		if (limit != null) {
			sql += " LIMIT :lim";
			p.addValue("lim", limit);
		}
		return jdbc.query(sql, p, (rs, i) -> {
			long b = rs.getLong("backup_assignee_id");
			Long backupId = rs.wasNull() ? null : b;
			long c = rs.getLong("created_by");
			Long createdId = rs.wasNull() ? null : c;
			return new TaskRow(rs.getLong("id"), rs.getString("task_title"), rs.getString("task_status"),
					rs.getString("task_severity"), rs.getString("task_description"), TimeUtil.local(rs, "due_date"),
					backupId, UserRef.map(rs, "b_"), TimeUtil.local(rs, "create_date"), createdId,
					UserRef.map(rs, "c_"), TimeUtil.local(rs, "modified_date"), UserRef.map(rs, "m_"),
					rs.getBoolean("handover"));
		});
	}

	/** task id -> assignees (sorted by display name), one query. */
	public Map<Long, List<UserRef>> assignees(Collection<Long> taskIds) {
		Map<Long, List<UserRef>> out = new HashMap<>();
		if (taskIds.isEmpty()) {
			return out;
		}
		jdbc.query("""
				SELECT ta.task_id, u.id, u.username, u.first_name, u.last_name
				FROM task_assignee ta JOIN app_user u ON u.id = ta.user_id
				WHERE ta.task_id IN (:ids)
				ORDER BY u.first_name, u.last_name, u.username
				""", new MapSqlParameterSource("ids", taskIds), rs -> {
			out.computeIfAbsent(rs.getLong("task_id"), k -> new ArrayList<>()).add(UserRef.map(rs, ""));
		});
		return out;
	}

	public List<HistoryEntry> history(long taskId) {
		return jdbc.query("""
				SELECT h.id AS h_id, h.action_type, h.action_description, h.action_date,
				       u.id, u.username, u.first_name, u.last_name
				FROM task_history h LEFT JOIN app_user u ON u.id = h.action_by
				WHERE h.task_id = :id
				ORDER BY h.action_date DESC, h.id DESC
				""", new MapSqlParameterSource("id", taskId),
				(rs, i) -> new HistoryEntry(rs.getLong("h_id"), rs.getString("action_type"),
						rs.getString("action_description"), UserRef.map(rs, ""), TimeUtil.offset(rs, "action_date")));
	}

	public List<UserRef> activeUsers() {
		return jdbc.query("""
				SELECT id, username, first_name, last_name FROM app_user WHERE is_active
				ORDER BY first_name, last_name, username
				""", new MapSqlParameterSource(), (rs, i) -> UserRef.map(rs, ""));
	}

	/** Active users among the given ids. */
	public Map<Long, UserRef> activeUsersByIds(Collection<Long> ids) {
		Map<Long, UserRef> out = new HashMap<>();
		if (ids.isEmpty()) {
			return out;
		}
		jdbc.query("SELECT id, username, first_name, last_name FROM app_user WHERE is_active AND id IN (:ids)",
				new MapSqlParameterSource("ids", ids), rs -> {
					UserRef u = UserRef.map(rs, "");
					out.put(u.id(), u);
				});
		return out;
	}

	public UserRef user(long id) {
		List<UserRef> l = jdbc.query("SELECT id, username, first_name, last_name FROM app_user WHERE id = :id",
				new MapSqlParameterSource("id", id), (rs, i) -> UserRef.map(rs, ""));
		return l.isEmpty() ? null : l.get(0);
	}

	public long insert(String title, String description, String status, String severity, LocalDateTime dueDate,
			Long backupId, long actorId, LocalDateTime now) {
		MapSqlParameterSource p = new MapSqlParameterSource().addValue("title", title)
				.addValue("descr", description).addValue("status", status).addValue("sev", severity)
				.addValue("due", TimeUtil.ts(dueDate)).addValue("backup", backupId).addValue("actor", actorId)
				.addValue("now", TimeUtil.ts(now));
		Long id = jdbc.queryForObject("""
				INSERT INTO task (task_title, task_description, task_status, task_severity, due_date,
				                  backup_assignee_id, create_date, created_by, modified_date, modified_by)
				VALUES (:title, :descr, :status, :sev, :due, :backup, :now, :actor, :now, :actor)
				RETURNING id
				""", p, Long.class);
		return id;
	}

	public void update(long id, String title, String description, String status, String severity,
			LocalDateTime dueDate, Long backupId, long actorId, LocalDateTime now) {
		jdbc.update("""
				UPDATE task SET task_title = :title, task_description = :descr, task_status = :status,
				       task_severity = :sev, due_date = :due, backup_assignee_id = :backup,
				       modified_date = :now, modified_by = :actor
				WHERE id = :id
				""", new MapSqlParameterSource().addValue("id", id).addValue("title", title)
				.addValue("descr", description).addValue("status", status).addValue("sev", severity)
				.addValue("due", TimeUtil.ts(dueDate)).addValue("backup", backupId).addValue("actor", actorId)
				.addValue("now", TimeUtil.ts(now)));
	}

	public void addAssignee(long taskId, long userId) {
		jdbc.update("INSERT OR IGNORE INTO task_assignee (task_id, user_id) VALUES (:t, :u)",
				new MapSqlParameterSource().addValue("t", taskId).addValue("u", userId));
	}

	public void removeAssignee(long taskId, long userId) {
		jdbc.update("DELETE FROM task_assignee WHERE task_id = :t AND user_id = :u",
				new MapSqlParameterSource().addValue("t", taskId).addValue("u", userId));
	}

	public void addHistory(long taskId, String type, String description, long actorId, LocalDateTime now) {
		jdbc.update("""
				INSERT INTO task_history (task_id, action_type, action_description, action_by, action_date)
				VALUES (:t, :type, :d, :actor, :now)
				""", new MapSqlParameterSource().addValue("t", taskId).addValue("type", type)
				.addValue("d", description).addValue("actor", actorId).addValue("now", TimeUtil.ts(now)));
	}
}
