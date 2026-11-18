package com.cyberops.portal.task;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.stereotype.Service;

import com.cyberops.portal.auth.CurrentUser;
import com.cyberops.portal.common.PermissionCodes;
import com.cyberops.portal.task.DashboardDtos.Bucket;
import com.cyberops.portal.task.DashboardDtos.Dashboard;
import com.cyberops.portal.task.DashboardDtos.Report;
import com.cyberops.portal.task.DashboardDtos.Stats;
import com.cyberops.portal.task.DashboardDtos.TeamMember;
import com.cyberops.portal.task.TaskDtos.TaskSummary;

@Service
public class DashboardService {

	private static final String MINE = "EXISTS (SELECT 1 FROM task_assignee ma WHERE ma.task_id = t.id AND ma.user_id = :me)";

	private final TaskRepository tasks;
	private final TaskService taskService;
	private final DashboardRepository repo;

	public DashboardService(TaskRepository tasks, TaskService taskService, DashboardRepository repo) {
		this.tasks = tasks;
		this.taskService = taskService;
		this.repo = repo;
	}

	public Dashboard get(CurrentUser me) {
		LocalDateTime now = TimeUtil.now();
		long[] s = repo.myTaskStats(me.id(), now);
		Stats stats = new Stats(s[0], s[1], s[2], s[3], s[4], repo.upcomingActivityCount(me.id(), now));

		List<TaskSummary> pending = taskService.summaries(tasks.find(MINE + " AND t.task_status <> 'DONE'",
				new MapSqlParameterSource("me", me.id()), TaskService.DEFAULT_ORDER, 8));
		List<TaskSummary> done = taskService.summaries(tasks.find(MINE + " AND t.task_status = 'DONE'",
				new MapSqlParameterSource("me", me.id()), "t.modified_date DESC, t.id DESC", 8));
		List<TaskSummary> handover = taskService.summaries(tasks.find(
				"t.backup_assignee_id = :me AND t.task_status <> 'DONE' AND EXISTS (SELECT 1 FROM task_assignee hx"
						+ " JOIN app_user hu ON hu.id = hx.user_id WHERE hx.task_id = t.id AND hu.is_on_leave)",
				new MapSqlParameterSource("me", me.id()), TaskService.DEFAULT_ORDER, null));

		List<TeamMember> team = null;
		if (me.hasPerm(PermissionCodes.ROLE_MANAGEMENT)) {
			long total = repo.permissionTypeCount();
			boolean director = total > 0 && me.permissions().size() >= total;
			team = repo.team(me.id(), director, now);
		}

		Report report = null;
		if (me.hasPerm(PermissionCodes.REPORT_ANALYSIS)) {
			MapSqlParameterSource p1 = new MapSqlParameterSource();
			Map<String, Long> bySev = repo.countBy("task_severity", TaskVisibility.where(me, p1), p1);
			MapSqlParameterSource p2 = new MapSqlParameterSource();
			Map<String, Long> bySt = repo.countBy("task_status", TaskVisibility.where(me, p2), p2);
			report = new Report(buckets(TaskDtos.SEVERITIES, bySev), buckets(TaskDtos.STATUSES, bySt));
		}

		MapSqlParameterSource hp = new MapSqlParameterSource();
		String hw = TaskVisibility.where(me, hp);
		return new Dashboard(stats, pending, done, handover, repo.myUpcomingActivities(me.id(), now, 6), team,
				report, repo.recentHistory(hw, hp, 8));
	}

	private static List<Bucket> buckets(List<String> keys, Map<String, Long> counts) {
		long total = counts.values().stream().mapToLong(Long::longValue).sum();
		return keys.stream().map(k -> {
			long c = counts.getOrDefault(k, 0L);
			return new Bucket(k, c, total == 0 ? 0 : Math.round(c * 100.0 / total));
		}).toList();
	}
}
