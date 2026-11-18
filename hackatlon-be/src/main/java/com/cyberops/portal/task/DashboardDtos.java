package com.cyberops.portal.task;

import java.time.OffsetDateTime;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.cyberops.portal.task.TaskDtos.TaskSummary;

public final class DashboardDtos {

	private DashboardDtos() {
	}

	public record Stats(long pending, long inProgress, long done, long overdue, long critical,
			long upcomingActivities) {
	}

	public record ActivitySummary(long id, String name, String description, OffsetDateTime date, String location,
			String type, String participationType, UserRef contactPerson, UserRef createdBy, List<UserRef> attendees,
			boolean joined) {
	}

	public record TeamMember(UserRef user, String title, @JsonProperty("isOnLeave") boolean isOnLeave,
			List<String> permissions, long openCount, long progressCount, long doneCount, long overdueCount) {
	}

	public record Bucket(String key, long count, long percent) {
	}

	public record Report(List<Bucket> bySeverity, List<Bucket> byStatus) {
	}

	public record TaskRef(long id, String code, String title) {
	}

	public record RecentHistory(long id, String actionType, String actionDescription, UserRef actionBy,
			OffsetDateTime actionDate, TaskRef task) {
	}

	public record Dashboard(Stats stats, List<TaskSummary> pendingTasks, List<TaskSummary> doneTasks,
			List<TaskSummary> handoverTasks, List<ActivitySummary> myActivities, List<TeamMember> team,
			Report report, List<RecentHistory> recentHistory) {
	}
}
