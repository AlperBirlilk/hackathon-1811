package com.cyberops.portal.task;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import com.cyberops.portal.task.DashboardDtos.ActivitySummary;
import com.cyberops.portal.task.DashboardDtos.RecentHistory;
import com.cyberops.portal.task.DashboardDtos.TaskRef;
import com.cyberops.portal.task.DashboardDtos.TeamMember;

/** Read-only dashboard queries (activity / team tables queried directly, no cross-package imports). */
@Repository
public class DashboardRepository {

	private final NamedParameterJdbcTemplate jdbc;

	public DashboardRepository(NamedParameterJdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	/** Counts for tasks where the user is a primary assignee. */
	public long[] myTaskStats(long userId, LocalDateTime now) {
		return jdbc.queryForObject("""
				SELECT
				  count(*) FILTER (WHERE t.task_status = 'OPEN') AS pending,
				  count(*) FILTER (WHERE t.task_status = 'IN_PROGRESS') AS in_progress,
				  count(*) FILTER (WHERE t.task_status = 'DONE') AS done,
				  count(*) FILTER (WHERE t.task_status <> 'DONE' AND t.due_date < :now) AS overdue,
				  count(*) FILTER (WHERE t.task_status <> 'DONE' AND t.task_severity = 'CRITICAL') AS critical
				FROM task t JOIN task_assignee ta ON ta.task_id = t.id AND ta.user_id = :u
				""", new MapSqlParameterSource().addValue("u", userId).addValue("now", TimeUtil.ts(now)),
				(rs, i) -> new long[] { rs.getLong("pending"), rs.getLong("in_progress"), rs.getLong("done"),
						rs.getLong("overdue"), rs.getLong("critical") });
	}

	public long upcomingActivityCount(long userId, LocalDateTime now) {
		Long c = jdbc.queryForObject("""
				SELECT count(*) FROM activity a
				WHERE a.activity_date >= :now
				  AND EXISTS (SELECT 1 FROM activity_attendee aa WHERE aa.activity_id = a.id AND aa.user_id = :u)
				""", new MapSqlParameterSource().addValue("u", userId).addValue("now", TimeUtil.ts(now)), Long.class);
		return c == null ? 0 : c;
	}

	public List<ActivitySummary> myUpcomingActivities(long userId, LocalDateTime now, int limit) {
		MapSqlParameterSource p = new MapSqlParameterSource().addValue("u", userId)
				.addValue("now", TimeUtil.ts(now)).addValue("lim", limit);
		record Row(long id, String name, String description, LocalDateTime date, String location, String type,
				String participationType, UserRef contact, UserRef createdBy) {
		}
		List<Row> rows = jdbc.query("""
				SELECT a.id AS a_id, a.activity_name, a.activity_description, a.activity_date, a.location,
				       a.activity_type, a.participation_type,
				       cp.id AS cp_id, cp.username AS cp_username, cp.first_name AS cp_first_name, cp.last_name AS cp_last_name,
				       cb.id AS cb_id, cb.username AS cb_username, cb.first_name AS cb_first_name, cb.last_name AS cb_last_name
				FROM activity a
				LEFT JOIN app_user cp ON cp.id = a.contact_person_id
				LEFT JOIN app_user cb ON cb.id = a.created_by
				WHERE a.activity_date >= :now
				  AND EXISTS (SELECT 1 FROM activity_attendee aa WHERE aa.activity_id = a.id AND aa.user_id = :u)
				ORDER BY a.activity_date ASC, a.id ASC
				LIMIT :lim
				""", p, (rs, i) -> new Row(rs.getLong("a_id"), rs.getString("activity_name"),
				rs.getString("activity_description"), TimeUtil.local(rs, "activity_date"), rs.getString("location"),
				rs.getString("activity_type"), rs.getString("participation_type"), UserRef.map(rs, "cp_"),
				UserRef.map(rs, "cb_")));
		if (rows.isEmpty()) {
			return List.of();
		}
		Map<Long, List<UserRef>> attendees = new HashMap<>();
		jdbc.query("""
				SELECT aa.activity_id, u.id, u.username, u.first_name, u.last_name
				FROM activity_attendee aa JOIN app_user u ON u.id = aa.user_id
				WHERE aa.activity_id IN (:ids)
				ORDER BY u.first_name, u.last_name, u.username
				""", new MapSqlParameterSource("ids", rows.stream().map(Row::id).toList()), rs -> {
			attendees.computeIfAbsent(rs.getLong("activity_id"), k -> new ArrayList<>()).add(UserRef.map(rs, ""));
		});
		return rows.stream().map(r -> {
			List<UserRef> att = attendees.getOrDefault(r.id(), List.of());
			return new ActivitySummary(r.id(), r.name(), r.description(), TimeUtil.offset(r.date()), r.location(),
					r.type(), r.participationType(), r.contact(), r.createdBy(), att,
					att.stream().anyMatch(u -> u.id() == userId));
		}).toList();
	}

	/** Team members: manager_id = me, or every active user except me when {@code all}. */
	public List<TeamMember> team(long managerId, boolean all, LocalDateTime now) {
		MapSqlParameterSource p = new MapSqlParameterSource().addValue("m", managerId)
				.addValue("now", TimeUtil.ts(now));
		String filter = all ? "u.id <> :m" : "u.manager_id = :m";
		record Row(UserRef user, String title, boolean onLeave, long open, long progress, long done, long overdue) {
		}
		List<Row> rows = jdbc.query("""
				SELECT u.id, u.username, u.first_name, u.last_name, u.title, u.is_on_leave,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status = 'OPEN') AS open_count,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status = 'IN_PROGRESS') AS progress_count,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status = 'DONE') AS done_count,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status <> 'DONE' AND t.due_date < :now) AS overdue_count
				FROM app_user u
				WHERE u.is_active AND """ + " " + filter + """

				ORDER BY u.first_name, u.last_name, u.username
				""", p, (rs, i) -> new Row(UserRef.map(rs, ""), rs.getString("title"), rs.getBoolean("is_on_leave"),
				rs.getLong("open_count"), rs.getLong("progress_count"), rs.getLong("done_count"),
				rs.getLong("overdue_count")));
		if (rows.isEmpty()) {
			return List.of();
		}
		Map<Long, Set<String>> perms = new HashMap<>();
		jdbc.query("""
				SELECT up.user_id, pt.code FROM user_permission up
				JOIN permission_type pt ON pt.id = up.permission_type_id
				WHERE up.user_id IN (:ids)
				""", new MapSqlParameterSource("ids", rows.stream().map(r -> r.user().id()).toList()), rs -> {
			perms.computeIfAbsent(rs.getLong("user_id"), k -> new TreeSet<>()).add(rs.getString("code"));
		});
		return rows.stream().map(r -> new TeamMember(r.user(), r.title(), r.onLeave(),
				List.copyOf(perms.getOrDefault(r.user().id(), Set.of())), r.open(), r.progress(), r.done(),
				r.overdue())).toList();
	}

	public long permissionTypeCount() {
		Long c = jdbc.queryForObject("SELECT count(*) FROM permission_type", new MapSqlParameterSource(), Long.class);
		return c == null ? 0 : c;
	}

	/** Group counts over visible tasks; column is a constant ("task_severity" / "task_status"). */
	public Map<String, Long> countBy(String column, String visibilityWhere, MapSqlParameterSource p) {
		Map<String, Long> out = new LinkedHashMap<>();
		jdbc.query("SELECT t." + column + " AS k, count(*) AS c FROM task t WHERE " + visibilityWhere
				+ " GROUP BY t." + column, p, rs -> {
					out.put(rs.getString("k"), rs.getLong("c"));
				});
		return out;
	}

	public List<RecentHistory> recentHistory(String visibilityWhere, MapSqlParameterSource p, int limit) {
		p.addValue("lim", limit);
		return jdbc.query("""
				SELECT h.id AS h_id, h.action_type, h.action_description, h.action_date,
				       t.id AS t_id, t.task_title,
				       u.id, u.username, u.first_name, u.last_name
				FROM task_history h
				JOIN task t ON t.id = h.task_id
				LEFT JOIN app_user u ON u.id = h.action_by
				WHERE """ + " " + visibilityWhere + """

				ORDER BY h.action_date DESC, h.id DESC
				LIMIT :lim
				""", p, (rs, i) -> {
			long tid = rs.getLong("t_id");
			return new RecentHistory(rs.getLong("h_id"), rs.getString("action_type"),
					rs.getString("action_description"), UserRef.map(rs, ""), TimeUtil.offset(rs, "action_date"),
					new TaskRef(tid, TaskDtos.code(tid), rs.getString("task_title")));
		});
	}
}
