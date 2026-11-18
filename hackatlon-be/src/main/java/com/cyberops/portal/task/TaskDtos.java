package com.cyberops.portal.task;

import java.time.OffsetDateTime;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Task API DTOs (docs/api-contract.md "Task'lar"). */
public final class TaskDtos {

	private TaskDtos() {
	}

	public record TaskCreate(String title, String description, String severity, String status, List<Long> assigneeIds,
			Long backupAssigneeId, String dueDate) {
	}

	public record StatusRequest(String status) {
	}

	public record TaskSummary(long id, String code, String title, String status, String severity,
			List<UserRef> assignees, UserRef backupAssignee, OffsetDateTime dueDate,
			@JsonProperty("isOverdue") boolean isOverdue, boolean handover, OffsetDateTime modifiedDate) {
	}

	public record TaskDetail(long id, String code, String title, String status, String severity,
			List<UserRef> assignees, UserRef backupAssignee, OffsetDateTime dueDate,
			@JsonProperty("isOverdue") boolean isOverdue, boolean handover, OffsetDateTime modifiedDate,
			String description, UserRef createdBy, OffsetDateTime createDate, UserRef modifiedBy, boolean canEdit,
			boolean canChangeStatus, List<HistoryEntry> history) {
	}

	public record HistoryEntry(long id, String actionType, String actionDescription, UserRef actionBy,
			OffsetDateTime actionDate) {
	}

	public static String code(long id) {
		return String.format("TSK-%04d", id);
	}

	public static String statusLabel(String s) {
		return switch (s) {
			case "OPEN" -> "Açık";
			case "IN_PROGRESS" -> "Devam Ediyor";
			case "DONE" -> "Tamamlandı";
			default -> s;
		};
	}

	public static String severityLabel(String s) {
		return switch (s) {
			case "LOW" -> "Düşük";
			case "MEDIUM" -> "Orta";
			case "HIGH" -> "Yüksek";
			case "CRITICAL" -> "Kritik";
			default -> s;
		};
	}

	public static final List<String> STATUSES = List.of("OPEN", "IN_PROGRESS", "DONE");
	public static final List<String> SEVERITIES = List.of("CRITICAL", "HIGH", "MEDIUM", "LOW");
}
